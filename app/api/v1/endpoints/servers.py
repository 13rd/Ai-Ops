from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.db.base import get_db
from app.models.user import User
from app.schemas.response import error_response, success_response
from app.schemas.server import ServerCreate, ServerResponse, ServerUpdate
from app.services.servers.server_service import ServerService

router = APIRouter()


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_server(
    server_data: ServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Create a new server. Admin only.
    """
    server = await ServerService.create_server(db, server_data)
    return success_response(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server created successfully",
    )


@router.get("", response_model=dict)
async def list_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Filter by tag"),
    sort_by: str = Query(
        "created_at",
        description="Sort by field: created_at, name, cpu_usage, memory_usage, last_seen",
    ),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of servers with optional filters and sorting.
    """
    # Validate sort parameters
    valid_sort_fields = ["created_at", "name", "cpu_usage", "memory_usage", "last_seen"]
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort field. Valid fields: {valid_sort_fields}",
        )

    if sort_order not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sort order. Use 'asc' or 'desc'",
        )

    servers = await ServerService.get_servers(
        db,
        skip=skip,
        limit=limit,
        environment=environment,
        status=status,
        tags=tags,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return success_response(
        data=[ServerResponse.model_validate(s).model_dump() for s in servers],
        message="Servers retrieved successfully",
    )


@router.get("/{server_id}", response_model=dict)
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get server details by ID.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    return success_response(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server retrieved successfully",
    )


@router.put("/{server_id}", response_model=dict)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Update server information. Admin only.
    """
    server = await ServerService.update_server(db, server_id, server_data)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    return success_response(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server updated successfully",
    )


@router.delete("/{server_id}", response_model=dict)
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Delete server by ID. Admin only.
    """
    deleted = await ServerService.delete_server(db, server_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    return success_response(
        data={"server_id": server_id},
        message="Server deleted successfully",
    )
