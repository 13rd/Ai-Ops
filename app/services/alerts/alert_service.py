import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.alert import Alert, AlertRule, AlertRuleType, AlertSeverity, AlertStatus
from app.models.container import ContainerSnapshot
from app.models.metric import MetricSnapshot
from app.models.server import Server
from app.models.user import User
from app.schemas.alert import CreateAlertRequest

logger = logging.getLogger(__name__)


class AlertService:
    """
    Service for managing alert creation, monitoring, and state management.
    """

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        title: str,
        description: str,
        severity: AlertSeverity,
        rule_type: AlertRuleType,
        server_id: Optional[int] = None,
        container_id: Optional[str] = None,
        metric_type: Optional[str] = None,
        threshold_value: Optional[str] = None,
        current_value: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Alert:
        """
        Create a new alert record.
        """
        alert = Alert(
            title=title,
            description=description,
            severity=severity,
            rule_type=rule_type.value if hasattr(rule_type, "value") else rule_type,
            server_id=server_id,
            container_id=container_id,
            metric_type=metric_type,
            threshold_value=threshold_value,
            current_value=current_value,
            additional_metadata=metadata or {},
            status=AlertStatus.OPEN,
        )

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        return alert

    @staticmethod
    async def get_alerts(
        db: AsyncSession,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        server_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Alert]:
        """
        Get alerts with optional filters.
        """
        query = select(Alert).order_by(desc(Alert.created_at))

        conditions = []
        if status:
            conditions.append(Alert.status == status)
        if severity:
            conditions.append(Alert.severity == severity)
        if server_id:
            conditions.append(Alert.server_id == server_id)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_alert_by_id(db: AsyncSession, alert_id: int) -> Optional[Alert]:
        """
        Get alert by ID.
        """
        query = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def acknowledge_alert(db: AsyncSession, alert_id: int, user_id: int) -> bool:
        """
        Acknowledge an alert.
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False

        if alert.status != AlertStatus.OPEN:
            return False  # Only open alerts can be acknowledged

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by_user_id = user_id

        await db.commit()
        return True

    @staticmethod
    async def resolve_alert(db: AsyncSession, alert_id: int) -> bool:
        """
        Resolve an alert as fixed.
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False

        if alert.status in [AlertStatus.RESOLVED]:
            return False  # Already resolved

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()

        await db.commit()
        return True

    @staticmethod
    async def get_alerts_count(
        db: AsyncSession,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        server_id: Optional[int] = None,
    ) -> int:
        """
        Get count of alerts with optional filters.
        """
        query = select(Alert)

        conditions = []
        if status:
            conditions.append(Alert.status == status)
        if severity:
            conditions.append(Alert.severity == severity)
        if server_id:
            conditions.append(Alert.server_id == server_id)

        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        return len(list(result.scalars().all()))


class AlertEngine:
    """
    Engine for monitoring metrics and containers to generate alerts based on rules.
    """

    @staticmethod
    async def evaluate_server_metrics(
        db: AsyncSession, server: Server, latest_metrics: Optional[MetricSnapshot] = None
    ) -> List[Alert]:
        """
        Evaluate server metrics against alert rules and create alerts if thresholds are exceeded.
        """
        if not latest_metrics:
            # Get latest metrics for this server
            from app.services.collectors.snapshot_service import MetricService

            latest_metrics = await MetricService.get_latest_metrics(db, server.id)

        if not latest_metrics:
            return []

        created_alerts = []

        # Check CPU threshold
        cpu_alert = await AlertEngine._check_cpu_threshold(db, server, latest_metrics)
        if cpu_alert:
            created_alerts.append(cpu_alert)

        # Check memory threshold
        mem_alert = await AlertEngine._check_memory_threshold(db, server, latest_metrics)
        if mem_alert:
            created_alerts.append(mem_alert)

        # Check disk threshold
        disk_alert = await AlertEngine._check_disk_threshold(db, server, latest_metrics)
        if disk_alert:
            created_alerts.append(disk_alert)

        # Check load average (optional - could be configured as rule)
        load_alert = await AlertEngine._check_load_average(db, server, latest_metrics)
        if load_alert:
            created_alerts.append(load_alert)

        return created_alerts

    @staticmethod
    async def _check_cpu_threshold(
        db: AsyncSession, server: Server, metrics: MetricSnapshot
    ) -> Optional[Alert]:
        """
        Check if CPU usage exceeds threshold (default 80%).
        """
        # Get threshold from system defaults (could be configured differently)
        cpu_threshold = 80.0  # Default high CPU usage threshold

        # In a real system, this would come from configured alert rules
        if metrics.cpu_usage_percent and metrics.cpu_usage_percent > cpu_threshold:
            # Check if there's already an open alert for this condition to avoid spam
            existing_alert = await AlertEngine._has_open_alert(
                db, server.id, AlertRuleType.CPU_THRESHOLD
            )

            if not existing_alert:
                return await AlertService.create_alert(
                    db=db,
                    title=f"High CPU Usage on {server.name}",
                    description=f"CPU usage is {metrics.cpu_usage_percent}% on server {server.name} ({server.host}), exceeding threshold of {cpu_threshold}%",
                    severity=AlertSeverity.HIGH,
                    rule_type=AlertRuleType.CPU_THRESHOLD,
                    server_id=server.id,
                    metric_type="cpu_percent",
                    threshold_value=str(cpu_threshold),
                    current_value=str(metrics.cpu_usage_percent),
                    metadata={"server_host": server.host, "cpu_usage": metrics.cpu_usage_percent},
                )
        return None

    @staticmethod
    async def _check_memory_threshold(
        db: AsyncSession, server: Server, metrics: MetricSnapshot
    ) -> Optional[Alert]:
        """
        Check if memory usage exceeds threshold (default 85%).
        """
        memory_threshold = 85.0  # Default memory usage threshold

        if metrics.memory_usage_percent and metrics.memory_usage_percent > memory_threshold:
            existing_alert = await AlertEngine._has_open_alert(
                db, server.id, AlertRuleType.MEMORY_THRESHOLD
            )

            if not existing_alert:
                return await AlertService.create_alert(
                    db=db,
                    title=f"High Memory Usage on {server.name}",
                    description=f"Memory usage is {metrics.memory_usage_percent}% on server {server.name} ({server.host}), exceeding threshold of {memory_threshold}%",
                    severity=AlertSeverity.HIGH,
                    rule_type=AlertRuleType.MEMORY_THRESHOLD,
                    server_id=server.id,
                    metric_type="memory_percent",
                    threshold_value=str(memory_threshold),
                    current_value=str(metrics.memory_usage_percent),
                    metadata={
                        "server_host": server.host,
                        "memory_usage": metrics.memory_usage_percent,
                    },
                )
        return None

    @staticmethod
    async def _check_disk_threshold(
        db: AsyncSession, server: Server, metrics: MetricSnapshot
    ) -> Optional[Alert]:
        """
        Check if disk usage exceeds threshold (default 90%).
        """
        disk_threshold = 90.0  # Default disk usage threshold

        if metrics.disk_usage_percent and metrics.disk_usage_percent > disk_threshold:
            existing_alert = await AlertEngine._has_open_alert(
                db, server.id, AlertRuleType.DISK_THRESHOLD
            )

            if not existing_alert:
                return await AlertService.create_alert(
                    db=db,
                    title=f"High Disk Usage on {server.name}",
                    description=f"Disk usage is {metrics.disk_usage_percent}% on server {server.name} ({server.host}), exceeding threshold of {disk_threshold}%",
                    severity=AlertSeverity.HIGH,
                    rule_type=AlertRuleType.DISK_THRESHOLD,
                    server_id=server.id,
                    metric_type="disk_percent",
                    threshold_value=str(disk_threshold),
                    current_value=str(metrics.disk_usage_percent),
                    metadata={"server_host": server.host, "disk_usage": metrics.disk_usage_percent},
                )
        return None

    @staticmethod
    async def _check_load_average(
        db: AsyncSession, server: Server, metrics: MetricSnapshot
    ) -> Optional[Alert]:
        """
        Check if load average is concerning (high relative to CPU cores).
        For now, we'll check if 1-minute load exceeds 2.0 * CPU cores (just as an example).
        """
        # In a real system, we might get CPU core count from server metadata
        # For now we'll use the 1-minute load average > 4.0 as a trigger point
        load_threshold = 4.0

        if metrics.load_average_1m and metrics.load_average_1m > load_threshold:
            existing_alert = await AlertEngine._has_open_alert(
                db,
                server.id,
                AlertRuleType.CPU_THRESHOLD,  # Using CPU_THRESHOLD as a proxy
            )

            if not existing_alert:
                return await AlertService.create_alert(
                    db=db,
                    title=f"High Load Average on {server.name}",
                    description=f"Load average is {metrics.load_average_1m} on server {server.name} ({server.host}), exceeding threshold of {load_threshold}",
                    severity=AlertSeverity.MEDIUM,
                    rule_type=AlertRuleType.CPU_THRESHOLD,
                    server_id=server.id,
                    metric_type="load_average_1m",
                    threshold_value=str(load_threshold),
                    current_value=str(metrics.load_average_1m),
                    metadata={
                        "server_host": server.host,
                        "load_average_1m": metrics.load_average_1m,
                    },
                )
        return None

    @staticmethod
    async def evaluate_containers(db: AsyncSession, server: Server) -> List[Alert]:
        """
        Check container states and create alerts for problematic containers.
        """
        from app.services.collectors.snapshot_service import ContainerService

        # Get latest containers for this server
        containers = await ContainerService.get_latest_containers(db, server.id)

        created_alerts = []

        for container in containers:
            # Check if container is down/unhealthy
            if container.status and (
                "exited" in container.status.lower() or "dead" in container.status.lower()
            ):
                # Check if there's already an open alert for this container
                existing_alert = await AlertEngine._has_open_container_alert(
                    db, server.id, container.container_id, AlertRuleType.CONTAINER_DOWN
                )

                if not existing_alert:
                    alert = await AlertService.create_alert(
                        db=db,
                        title=f"Container Down on {server.name}: {container.container_name}",
                        description=f"Container {container.container_name} (ID: {container.container_id[:12]}) is in '{container.status}' state",
                        severity=AlertSeverity.HIGH,
                        rule_type=AlertRuleType.CONTAINER_DOWN,
                        server_id=server.id,
                        container_id=container.container_id,
                        current_value=container.status,
                        metadata={
                            "server_host": server.host,
                            "container_name": container.container_name,
                            "container_status": container.status,
                        },
                    )
                    created_alerts.append(alert)

            # Check for health status in extra_data
            if (
                container.extra_data
                and container.extra_data.get("State", {}).get("Health", {}).get("Status")
                == "unhealthy"
            ):
                existing_alert = await AlertEngine._has_open_container_alert(
                    db, server.id, container.container_id, AlertRuleType.CONTAINER_UNHEALTHY
                )

                if not existing_alert:
                    alert = await AlertService.create_alert(
                        db=db,
                        title=f"Unhealthy Container on {server.name}: {container.container_name}",
                        description=f"Container {container.container_name} (ID: {container.container_id[:12]}) is in unhealthy state",
                        severity=AlertSeverity.MEDIUM,
                        rule_type=AlertRuleType.CONTAINER_UNHEALTHY,
                        server_id=server.id,
                        container_id=container.container_id,
                        current_value="unhealthy",
                        metadata={
                            "server_host": server.host,
                            "container_name": container.container_name,
                            "health_status": "unhealthy",
                        },
                    )
                    created_alerts.append(alert)

        return created_alerts

    @staticmethod
    async def check_offline_servers(db: AsyncSession) -> List[Alert]:
        """
        Check for servers that appear to be offline based on last seen time.
        """
        # Define "offline" as not seen in the last 5 minutes
        from datetime import timedelta

        offline_threshold = datetime.utcnow() - timedelta(minutes=5)

        query = select(Server).where(
            and_(
                Server.last_seen < offline_threshold,
                Server.status != "offline",  # Only alert if status wasn't already marked as offline
            )
        )

        result = await db.execute(query)
        offline_servers = result.scalars().all()

        created_alerts = []
        for server in offline_servers:
            # Check if there's already an open alert for this server being offline
            existing_alert = await AlertEngine._has_open_server_offline_alert(db, server.id)

            if not existing_alert:
                alert = await AlertService.create_alert(
                    db=db,
                    title=f"Server Offline: {server.name}",
                    description=f"Server {server.name} ({server.host}) has not been seen since {server.last_seen}",
                    severity=AlertSeverity.CRITICAL,
                    rule_type=AlertRuleType.SERVER_OFFLINE,
                    server_id=server.id,
                    current_value=server.last_seen.isoformat() if server.last_seen else None,
                    metadata={
                        "server_host": server.host,
                        "last_seen": server.last_seen.isoformat() if server.last_seen else None,
                    },
                )
                created_alerts.append(alert)

        return created_alerts

    @staticmethod
    async def _has_open_alert(db: AsyncSession, server_id: int, rule_type: AlertRuleType) -> bool:
        """
        Check if there's already an open alert for this combination of server and rule type.
        """
        query = select(Alert).where(
            and_(
                Alert.server_id == server_id,
                Alert.rule_type == rule_type.value if hasattr(rule_type, "value") else rule_type,
                Alert.status == AlertStatus.OPEN,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def _has_open_container_alert(
        db: AsyncSession, server_id: int, container_id: str, rule_type: AlertRuleType
    ) -> bool:
        """
        Check if there's already an open alert for this container.
        """
        query = select(Alert).where(
            and_(
                Alert.server_id == server_id,
                Alert.container_id == container_id,
                Alert.rule_type == rule_type.value if hasattr(rule_type, "value") else rule_type,
                Alert.status == AlertStatus.OPEN,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def _has_open_server_offline_alert(db: AsyncSession, server_id: int) -> bool:
        """
        Check if there's already an open server offline alert for this server.
        """
        query = select(Alert).where(
            and_(
                Alert.server_id == server_id,
                Alert.rule_type == AlertRuleType.SERVER_OFFLINE.value,
                Alert.status == AlertStatus.OPEN,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def run_alert_evaluation_cycle(db: AsyncSession):
        """
        Run a complete cycle of alert evaluation across all servers.
        This should be called periodically by the scheduler.
        """
        logger.info("Starting alert evaluation cycle")

        # Get all servers
        servers_query = select(Server)
        servers_result = await db.execute(servers_query)
        servers = servers_result.scalars().all()

        total_created = 0

        for server in servers:
            try:
                # Evaluate metrics for this server
                latest_metrics = None
                from app.services.collectors.snapshot_service import MetricService

                latest_metrics = await MetricService.get_latest_metrics(db, server.id)

                created_metrics_alerts = await AlertEngine.evaluate_server_metrics(
                    db, server, latest_metrics
                )
                total_created += len(created_metrics_alerts)

                # Evaluate containers for this server
                created_container_alerts = await AlertEngine.evaluate_containers(db, server)
                total_created += len(created_container_alerts)

            except Exception as e:
                logger.error(f"Error evaluating alerts for server {server.name}: {e}")

        # Check for offline servers
        try:
            offline_alerts = await AlertEngine.check_offline_servers(db)
            total_created += len(offline_alerts)
        except Exception as e:
            logger.error(f"Error checking offline servers: {e}")

        logger.info(f"Alert evaluation cycle completed. Created {total_created} new alerts")
