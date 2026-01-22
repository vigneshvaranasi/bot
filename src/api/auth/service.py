from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from sqlalchemy import func
from ..db.models import User, AuthIdentity, Role, AuthProvider, RevokedToken, UserRole
from ..core.security import get_password_hash, verify_password
from ..core.jwt import create_access_token
from .schemas import UserSignup, UserLogin, TokenResponse
from .providers import get_provider_class
import uuid
import os
from datetime import datetime, timezone

async def revoke_token(jti: str, expires_at: datetime, session: AsyncSession):
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        
    revoked = RevokedToken(jti=jti, expires_at=expires_at)
    session.add(revoked)
    await session.commit()

async def revoke_all_user_tokens(user_id: uuid.UUID, session: AsyncSession):
    # Increment token version to invalidate all previous tokens
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        user.token_version = user.token_version + 1
        await session.commit()

async def get_default_role(session: AsyncSession) -> Role:
    """Get the default role for new users (Basic User)."""
    result = await session.execute(select(Role).where(Role.name == "Basic User"))
    role = result.scalar_one_or_none()
    if role:
        return role

    # Fallback to legacy "user" role for backward compatibility
    result = await session.execute(select(Role).where(Role.name == "user"))
    role = result.scalar_one_or_none()
    if not role:
        # Create a basic user role if none exists
        role = Role(name="Basic User")
        session.add(role)
        await session.commit()
        await session.refresh(role)
    return role

async def signup_user(user_data: UserSignup, session: AsyncSession) -> dict:
    # Check if user exists
    result = await session.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Determine role
    if user_data.role_id:
        role_id = user_data.role_id
    else:
        role = await get_default_role(session)
        role_id = role.id

    # Create User
    new_user = User(
        email=user_data.email,
        role_id=role_id,  # Legacy field for backward compatibility
        is_active=True
    )
    session.add(new_user)
    await session.flush()

    # Create AuthIdentity
    hashed_password = get_password_hash(user_data.password)
    auth_identity = AuthIdentity(
        user_id=new_user.id,
        provider="local",
        password_hash=hashed_password
    )
    session.add(auth_identity)

    # Create UserRole entry
    user_role = UserRole(
        user_id=new_user.id,
        role_id=role_id,
        assigned_at=datetime.utcnow(),
        assigned_by=None
    )
    session.add(user_role)

    await session.commit()

    return {"message": "User created successfully"}

async def login_user(user_credentials: UserLogin, session: AsyncSession) -> TokenResponse:
    # Find User by email
    stmt = select(User).options(
        selectinload(User.role),
        selectinload(User.auth_identities)
    ).where(User.email == user_credentials.email)
    
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Find local auth identity
    local_identity = next((ai for ai in user.auth_identities if ai.provider == "local"), None)
    
    if not local_identity or not local_identity.password_hash:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not verify_password(user_credentials.password, local_identity.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")

    # Prepare JWT data
    role_name = user.role.name
    
    access_token = create_access_token(
        user_id=str(user.id),
        role=role_name,
        auth_provider="local",
        token_version=user.token_version
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=role_name
    )

async def get_user_profile(user_id: uuid.UUID, session: AsyncSession):
    stmt = select(User).options(
        selectinload(User.role),
        selectinload(User.auth_identities)
    ).where(User.id == user_id)
    
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

async def get_provider_instance(provider_name: str, session: AsyncSession):
    result = await session.execute(select(AuthProvider).where(AuthProvider.provider_name == provider_name))
    provider_model = result.scalar_one_or_none()
    
    if not provider_model or not provider_model.enabled:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not enabled")
        
    provider_cls = get_provider_class(provider_name)
    if not provider_cls:
        raise HTTPException(status_code=400, detail=f"Provider {provider_name} not implemented")
    
    # Override config with env vars if available
    config = provider_model.config.copy()
    if provider_name == "google":
        if os.getenv("GOOGLE_CLIENT_ID"): config["client_id"] = os.getenv("GOOGLE_CLIENT_ID")
        if os.getenv("GOOGLE_CLIENT_SECRET"): config["client_secret"] = os.getenv("GOOGLE_CLIENT_SECRET")
        if os.getenv("GOOGLE_REDIRECT_URI"): config["redirect_uri"] = os.getenv("GOOGLE_REDIRECT_URI")
    elif provider_name == "github":
        if os.getenv("GITHUB_CLIENT_ID"): config["client_id"] = os.getenv("GITHUB_CLIENT_ID")
        if os.getenv("GITHUB_CLIENT_SECRET"): config["client_secret"] = os.getenv("GITHUB_CLIENT_SECRET")
        if os.getenv("GITHUB_REDIRECT_URI"): config["redirect_uri"] = os.getenv("GITHUB_REDIRECT_URI")
    elif provider_name == "microsoft":
        if os.getenv("MICROSOFT_CLIENT_ID"): config["client_id"] = os.getenv("MICROSOFT_CLIENT_ID")
        if os.getenv("MICROSOFT_CLIENT_SECRET"): config["client_secret"] = os.getenv("MICROSOFT_CLIENT_SECRET")
        if os.getenv("MICROSOFT_REDIRECT_URI"): config["redirect_uri"] = os.getenv("MICROSOFT_REDIRECT_URI")
        if os.getenv("MICROSOFT_TENANT_ID"): config["tenant"] = os.getenv("MICROSOFT_TENANT_ID")
        
    return provider_cls(config)

async def resolve_oauth_user(profile: dict, session: AsyncSession) -> User:
    # Check if identity exists
    stmt = select(AuthIdentity).options(selectinload(AuthIdentity.user).selectinload(User.role)).where(
        AuthIdentity.provider == profile["provider"],
        AuthIdentity.provider_user_id == profile["provider_user_id"]
    )
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()
    
    if identity:
        return identity.user
        
    # Check if email exists
    if profile.get("email"):
        stmt = select(User).where(User.email == profile["email"])
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Account exists but no identity linked -> Link automatically
            new_identity = AuthIdentity(
                user_id=user.id,
                provider=profile["provider"],
                provider_user_id=profile["provider_user_id"]
            )
            session.add(new_identity)
            await session.commit()
            
            # Reload user with role
            stmt = select(User).options(selectinload(User.role)).where(User.id == user.id)
            result = await session.execute(stmt)
            user = result.scalar_one()
            
            return user
            
    # Create new user
    role = await get_default_role(session)
    new_user = User(
        email=profile.get("email"),
        role_id=role.id,  # Legacy field for backward compatibility
        is_active=True
    )
    session.add(new_user)
    await session.flush()

    new_identity = AuthIdentity(
        user_id=new_user.id,
        provider=profile["provider"],
        provider_user_id=profile["provider_user_id"]
    )
    session.add(new_identity)

    user_role = UserRole(
        user_id=new_user.id,
        role_id=role.id,
        assigned_at=datetime.utcnow(),
        assigned_by=None
    )
    session.add(user_role)

    await session.commit()
    await session.refresh(new_user)
    stmt = select(User).options(selectinload(User.role)).where(User.id == new_user.id)
    result = await session.execute(stmt)
    new_user = result.scalar_one()

    return new_user

async def update_user_password(user_id: uuid.UUID, password: str, session: AsyncSession):
    # Check if local identity exists
    stmt = select(AuthIdentity).where(
        AuthIdentity.user_id == user_id,
        AuthIdentity.provider == "local"
    )
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()
    
    hashed_password = get_password_hash(password)
    
    if identity:
        identity.password_hash = hashed_password
    else:
        # Create local identity
        identity = AuthIdentity(
            user_id=user_id,
            provider="local",
            password_hash=hashed_password
        )
        session.add(identity)
        
    # Revoke all tokens (security best practice on password change)
    await revoke_all_user_tokens(user_id, session)
    
    await session.commit()
    return {"message": "Password updated successfully"}
