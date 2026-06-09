from datetime import datetime
from typing import Any, Optional

from beanie import Document
from pydantic import Field


class User(Document):
    email: str
    name: Optional[str] = None
    connectors: list[dict[str, Any]] = Field(default_factory=list)
    tenant_id: Optional[str] = None
    kind: str = "client"  # internal | client
    password_hash: Optional[str] = None
    google_sub: Optional[str] = None
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False
    last_login_at: Optional[datetime] = None

    class Settings:
        collection = "users"
