from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.server import Server, ServerStatus
from app.schemas.server import ServerCreate, ServerUpdate


class ServerService:
    """
    Service for server management operations.
    """

    @staticmethod
    async def create_server(db: AsyncSession, server_data: ServerCreate) -> Server:
        """
        Create a new server.
        """
        # TODO: Encrypt credentials before storing
        server = Server(
            name=server_data.name,
            host=server_data.host,
            port=server_data.port,
            connection_type=server_data.connection_type,
            environment=server_data.environment,
            tags=server_data.tags,
            ssh_username=server_data.ssh_username,
            ssh_password=server_data.ssh_password,
            ssh_private_key=server_data.ssh_private_key,
            status=ServerStatus.OFFLINE,
        )

        db.add(server)
        await db.commit()
        await db.refresh(server)

        return server

    @staticmethod
    async def get_server_by_id(db: AsyncSession, server_id: int) -> Optional[Server]:
        """
        Get server by ID.
        """
        result = await db.execute(select(Server).where(Server.id == server_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_servers(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        environment: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Server]:
        """
        Get list of servers with optional filters.
        """
        query = select(Server)

        if environment:
            query = query.where(Server.environment == environment)

        if status:
            query = query.where(Server.status == status)

        query = query.offset(skip).limit(limit).order_by(Server.created_at.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_server(
        db: AsyncSession, server_id: int, server_data: ServerUpdate
    ) -> Optional[Server]:
        """
        Update server information.
        """
        server = await ServerService.get_server_by_id(db, server_id)
        if not server:
            return None

        update_data = server_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(server, field, value)

        server.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(server)

        return server

    @staticmethod
    async def delete_server(db: AsyncSession, server_id: int) -> bool:
        """
        Delete server by ID.
        Returns True if deleted, False if not found.
        """
        result = await db.execute(delete(Server).where(Server.id == server_id))
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_server_status(
        db: AsyncSession, server_id: int, status: ServerStatus, last_seen: datetime = None
    ) -> Optional[Server]:
        """
        Update server status and last_seen timestamp.
        """
        server = await ServerService.get_server_by_id(db, server_id)
        if not server:
            return None

        server.status = status
        if last_seen:
            server.last_seen = last_seen
        else:
            server.last_seen = datetime.utcnow()

        await db.commit()
        await db.refresh(server)

        return server
