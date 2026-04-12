from fastapi import APIRouter

from app.api.v1.endpoints import auth, connections, metrics, servers

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(servers.router, prefix="/servers", tags=["servers"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(metrics.router, prefix="/servers", tags=["metrics"])
