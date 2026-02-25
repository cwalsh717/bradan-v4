"""Auth sync endpoint."""

import jwt
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.users import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

bearer_scheme = HTTPBearer()


class UserResponse(BaseModel):
    id: int
    clerk_id: str
    email: str
    display_name: Optional[str] = None

    model_config = {"from_attributes": True}


@router.post("/sync", response_model=UserResponse)
async def sync_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
):
    """Create or update local user from Clerk JWT."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.CLERK_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        clerk_id = payload["sub"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Clerk stores email in different claims depending on version
    email = payload.get("email", payload.get("primary_email_address", ""))
    display_name = payload.get("name", payload.get("first_name"))

    # Upsert: find existing or create new
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user is None:
        user = User(
            clerk_id=clerk_id,
            email=email,
            display_name=display_name,
            last_login=now,
        )
        session.add(user)
    else:
        user.email = email
        if display_name:
            user.display_name = display_name
        user.last_login = now

    await session.flush()
    await session.commit()

    return user
