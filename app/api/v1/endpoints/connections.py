from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.responses import ok
from app.db.base import get_db
from app.models.user import User
from app.schemas.server import ConnectionTestResponse
from app.services.servers.connection_service import SSHConnectionService
from app.services.servers.server_service import ServerService

router = APIRouter()

@router.post("/test/{server_id}")
async def test_server_connection(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise NotFoundError("Server not found")

    success, message, error_code = await SSHConnectionService.test_connection(server)
    payload = ConnectionTestResponse(success=success, message=message, error_code=error_code)
    return ok(data=payload.model_dump(), message="Connection test completed")
