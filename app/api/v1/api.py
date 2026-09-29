from fastapi import APIRouter

from app.api.v1.endpoints import (
    alerts,
    anomalies,
    audit,
    auth,
    connections,
    console,
    containers,
    llm_settings,
    metrics,
    notifications,
    recommendations,
    servers,
    users,
)
from app.api.v1.websocket import console as ws_console
from app.api.v1.websocket import container_logs as ws_container_logs
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(servers.router, prefix="/servers", tags=["servers"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(metrics.router, prefix="/servers", tags=["metrics"])
api_router.include_router(metrics.direct_router, prefix="", tags=["metrics-direct"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(console.router, prefix="/console", tags=["console"])
api_router.include_router(containers.router, prefix="", tags=["containers"])
api_router.include_router(audit.router, prefix="", tags=["audit"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(anomalies.direct_router, prefix="", tags=["anomalies-direct"])
api_router.include_router(
    recommendations.router, prefix="/recommendations", tags=["recommendations"]
)
api_router.include_router(
    recommendations.anomaly_recs_router, prefix="", tags=["recommendations"]
)
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(llm_settings.router, prefix="/llm-settings", tags=["llm-settings"])
api_router.include_router(ws_console.router, prefix="", tags=["console-ws"])
api_router.include_router(ws_container_logs.router, prefix="", tags=["container-logs-ws"])

if settings.DEMO_MODE:
    from app.api.v1.endpoints.demo import router as demo_router

    api_router.include_router(demo_router, prefix="/demo", tags=["demo"])
