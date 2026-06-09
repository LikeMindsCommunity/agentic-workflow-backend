from datetime import datetime
from typing import Optional

from beanie import PydanticObjectId

from app.models.user import User


async def find_by_email(email: str) -> Optional[User]:
    return await User.find_one(User.email == email, User.is_deleted == False)


async def find_by_id(user_id: str) -> Optional[User]:
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        return None
    return await User.find_one(User.id == oid, User.is_deleted == False)


async def create(email: str) -> User:
    user = User(email=email)
    await user.insert()
    return user


async def set_verified(user: User) -> None:
    user.is_verified = True
    user.updated_at = datetime.utcnow()
    await user.save()


async def set_last_login(user: User) -> None:
    user.last_login_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    await user.save()
