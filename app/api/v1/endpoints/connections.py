from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.response import success_response
from app.schemas.server import ConnectionTestResponse
from app.services.servers.connection_service import SSHConnectionService
from app.services.servers.server_service import ServerService

router = APIRouter()


@router.post("/test/{server_id}", response_model=dict)
async def test_server_connection(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test connection to a server.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    success, message, error_code = await SSHConnectionService.test_connection(server)

    response_data = ConnectionTestResponse(
        success=success,
        message=message,
        error_code=error_code,
    )

    return success_response(
        data=response_data.model_dump(),
        message="Connection test completed",
    )
