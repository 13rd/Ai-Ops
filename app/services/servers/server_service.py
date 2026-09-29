from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import get_secrets_manager
from app.models.server import Server, ServerStatus
from app.schemas.server import ServerCreate, ServerUpdate

class ServerService:

    @staticmethod
    async def create_server(db: AsyncSession, server_data: ServerCreate) -> Server:
        secrets = get_secrets_manager()
        server = Server(
            name=server_data.name,
            host=server_data.host,
            port=server_data.port,
            connection_type=server_data.connection_type,
            environment=server_data.environment,
            tags=server_data.tags,
            ssh_username=server_data.ssh_username,
            ssh_password=secrets.encrypt_if_needed(server_data.ssh_password),
            ssh_private_key=secrets.encrypt_if_needed(server_data.ssh_private_key),
            status=ServerStatus.OFFLINE,
        )

        db.add(server)
        await db.commit()
        await db.refresh(server)

        return server

    @staticmethod
    async def get_server_by_id(db: AsyncSession, server_id: int) -> Optional[Server]:
        result = await db.execute(select(Server).where(Server.id == server_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_servers(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: Optional[str] = "desc",
        allowed_server_ids: Optional[set[int]] = None,
    ) -> List[Server]:
        query = select(Server)

        if environment:
            query = query.where(Server.environment == environment)
        if status:
            query = query.where(Server.status == status)
        if tags:
            query = query.where(Server.tags.like(f'%"{tags}"%'))

        if sort_by == "name":
            query = query.order_by(Server.name.asc() if sort_order == "asc" else Server.name.desc())
        elif sort_by == "cpu_usage":
            from app.models.metric import MetricSnapshot

            query = (
                select(Server)
                .outerjoin(MetricSnapshot, Server.id == MetricSnapshot.server_id)
                .order_by(func.coalesce(MetricSnapshot.cpu_usage_percent, 0).desc())
            )
        elif sort_by == "memory_usage":
            from app.models.metric import MetricSnapshot

            query = (
                select(Server)
                .outerjoin(MetricSnapshot, Server.id == MetricSnapshot.server_id)
                .order_by(func.coalesce(MetricSnapshot.memory_usage_percent, 0).desc())
            )
        elif sort_by == "last_seen":
            query = query.order_by(
                Server.last_seen.asc() if sort_order == "asc" else Server.last_seen.desc()
            )
        else:
            query = query.order_by(
                Server.created_at.asc() if sort_order == "asc" else Server.created_at.desc()
            )

        if allowed_server_ids is not None:
            query = query.where(Server.id.in_(allowed_server_ids))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_servers_with_count(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[str] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: Optional[str] = "desc",
        allowed_server_ids: Optional[set[int]] = None,
    ):
        total = await ServerService.count_servers(
            db, environment=environment, status=status, tags=tags,
            allowed_server_ids=allowed_server_ids,
        )
        servers = await ServerService.get_servers(
            db, skip=skip, limit=limit, environment=environment, status=status,
            tags=tags, sort_by=sort_by, sort_order=sort_order,
            allowed_server_ids=allowed_server_ids,
        )
        return servers, total

    @staticmethod
    async def count_servers(
        db: AsyncSession,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[str] = None,
        allowed_server_ids: Optional[set[int]] = None,
    ) -> int:
        query = select(func.count()).select_from(Server)
        if allowed_server_ids is not None:
            query = query.where(Server.id.in_(allowed_server_ids))
        if environment:
            query = query.where(Server.environment == environment)
        if status:
            query = query.where(Server.status == status)
        if tags:
            query = query.where(Server.tags.like(f'%"{tags}"%'))
        result = await db.execute(query)
        return int(result.scalar_one())

    @staticmethod
    async def update_server(
        db: AsyncSession, server_id: int, server_data: ServerUpdate
    ) -> Optional[Server]:
        server = await ServerService.get_server_by_id(db, server_id)
        if not server:
            return None

        update_data = server_data.model_dump(exclude_unset=True)
        secrets = get_secrets_manager()
        for field in ("ssh_password", "ssh_private_key"):
            if field in update_data:
                update_data[field] = secrets.encrypt_if_needed(update_data[field])

        for field, value in update_data.items():
            setattr(server, field, value)

        server.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(server)

        return server

    @staticmethod
    async def delete_server(db: AsyncSession, server_id: int) -> bool:
        result = await db.execute(delete(Server).where(Server.id == server_id))
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_server_status(
        db: AsyncSession,
        server_id: int,
        status: ServerStatus,
        last_seen: Optional[datetime] = None,
    ) -> Optional[Server]:
        server = await ServerService.get_server_by_id(db, server_id)
        if not server:
            return None

        server.status = status
        server.last_seen = last_seen or datetime.utcnow()

        await db.commit()
        await db.refresh(server)

        return server
