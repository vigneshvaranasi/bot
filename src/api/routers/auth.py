import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.db_models import User
from src.api.schemas.auth_schemas import UserSignup, UserLogin, LoginResponse
from src.api.utils.auth import get_current_user, get_password_hash, verify_password, create_user_token

router = APIRouter()

@router.post("/signup", response_model=dict)
async def signup(user_data: UserSignup, session: AsyncSession = Depends(get_session)):
    """
    Create a new user account (sign up).
    """
    # Hash the password before storing
    hashed_password = get_password_hash(user_data.password)
    
    # Create new user with hashed password
    new_user = User(
        email=user_data.email,
        password=hashed_password,
        role_id=user_data.role_id
    )
    
    session.add(new_user)
    
    try:
        await session.commit()
        await session.refresh(new_user)
        
        # Create JWT token for the new user
        jwt_token = create_user_token(new_user.email, new_user.id, new_user.role_id)

        return {
            "success": True,
            "message": "User created successfully",
            "user_id": str(new_user.id),
            "jwt": jwt_token,
            "role_id": str(new_user.role_id),
            "email": new_user.email
        }
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

@router.post("/login", response_model=LoginResponse)
async def login(user_credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    """
    Authenticate user and return JWT token.
    """
    # Find user by email
    result = await session.execute(select(User).where(User.email == user_credentials.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return LoginResponse(
            success=False,
            message="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_credentials.password, user.password):
        return LoginResponse(
            success=False,
            message="Invalid email or password"
        )
    
    # Create JWT token
    jwt_token = create_user_token(user.email, user.id, user.role_id)
    
    return LoginResponse(
        success=True,
        jwt=jwt_token,
        message="Login successful",
        email=user.email,
        id=str(user.id),
        role_id=str(user.role_id)
    )


# Token verification endpoint
@router.get("/verify", response_model=LoginResponse)
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    Verify the JWT token and return user information.
    """
    return LoginResponse(
        success=True,
        jwt=None,
        message="Token is valid",
        email=current_user["email"],
        id=str(current_user["user_id"]),
        role_id=str(current_user["role_id"])
    )