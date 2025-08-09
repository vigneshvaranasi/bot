from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.models import User
from src.api.schemas import UserCreate, UserResponse
from typing import List

router = APIRouter()

@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    new_user = User(email=user.email, password=user.password, role_id=user.role_id)
    session.add(new_user)
    try:
        await session.commit()
        await session.refresh(new_user)
        return new_user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="User already exists")

@router.get("/users", response_model=List[UserResponse])
async def get_users(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User))
    users = result.scalars().all()
    return users