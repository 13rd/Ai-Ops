from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ServerBase(BaseModel):
    name: str
    host: str
    port: int = 22
    connection_type: str = "ssh"
    environment: Optional[str] = None
    tags: List[str] = []


class ServerCreate(ServerBase):
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    connection_type: Optional[str] = None
    environment: Optional[str] = None
    tags: Optional[List[str]] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None


class ServerResponse(ServerBase):
    id: int
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectionTestRequest(BaseModel):
    server_id: int


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    error_code: Optional[str] = None
