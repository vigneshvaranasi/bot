from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2 import IntegrityError
from src.api.schemas.auth_schema import UserSignup,UserSignupResponse,UserLogin,LoginResponse
from src.api.utils.auth import get_password_hash,verify_password,create_user_token,get_current_user
from sqlalchemy.future import select
from src.api.db.session import get_session
from src.api.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from asyncpg import IntegrityConstraintViolationError

router = APIRouter()

# signup
@router.post("/signup",response_model=UserSignupResponse)
async def signup(user_data: UserSignup, session: AsyncSession = Depends(get_session)):
    """
    Create a new user account (sign up).
    """
    # todo: Validation of email and Password
    hashed_password = get_password_hash(user_data.password)

    # Create New User
    new_user = User(
        email=user_data.email, password=hashed_password, role_id=user_data.role_id
    )
    try:
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return {
            "success":True,
            "message":"User created successfully"
        }
    except IntegrityConstraintViolationError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

# login
@router.post("/login",response_model=LoginResponse)
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
        message="Login successful",
        jwt=jwt_token,
        email=user.email,
        role_id=str(user.role_id)
    )


# verify
@router.get("/verify",response_model=LoginResponse)
async def verify(current_user: dict = Depends(get_current_user)):
    """
    Verify the JWT token and return user information.
    """
    return LoginResponse(
        success=True,
        message="Token is valid",
        jwt=current_user["jwt"],
        email=current_user["email"],
        id=str(current_user["user_id"]),
        role_id=str(current_user["role_id"])
    )