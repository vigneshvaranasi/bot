from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from ..db.models import User, AuthIdentity, Role, AuthProvider, RevokedToken, UserRole
from ..core.security import get_password_hash, verify_password
from ..core.jwt import create_access_token
from .schemas import UserSignup, UserLogin, TokenResponse
from .providers import get_provider_class
import uuid
import os
from datetime import datetime, timezone, UTC

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
        await session.flush()

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
        await session.flush()
        await session.refresh(role)
    return role

async def signup_user(user_data: UserSignup, session: AsyncSession) -> dict:
    # Check if user exists
    result = await session.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # If the user was soft-deleted, reactivate the account
        if existing_user.deleted_at is not None:
            role = await get_default_role(session)
            existing_user.is_active = True
            existing_user.deleted_at = None
            existing_user.role_id = role.id
            existing_user.token_version = existing_user.token_version + 1

            # Update or create local auth identity with new password
            hashed_password = get_password_hash(user_data.password)
            stmt = select(AuthIdentity).where(
                AuthIdentity.user_id == existing_user.id,
                AuthIdentity.provider == "local"
            )
            result = await session.execute(stmt)
            local_identity = result.scalar_one_or_none()
            if local_identity:
                local_identity.password_hash = hashed_password
            else:
                session.add(AuthIdentity(
                    user_id=existing_user.id,
                    provider="local",
                    password_hash=hashed_password
                ))

            await session.commit()
            return {"message": "User created successfully"}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Always assign default role — role assignment is admin-only
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
        assigned_at=datetime.now(UTC).replace(tzinfo=None),
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
    ).where(User.email == user_credentials.email, User.deleted_at.is_(None))
    
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
    ).where(User.id == user_id, User.deleted_at.is_(None))
    
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
        user = identity.user
        # Reactivate if the linked user account was soft-deleted
        if user.deleted_at is not None:
            role = await get_default_role(session)
            user.is_active = True
            user.deleted_at = None
            user.role_id = role.id
            user.token_version = user.token_version + 1
            await session.commit()
            await session.refresh(user)
            # Re-fetch with role loaded
            stmt = select(User).options(selectinload(User.role)).where(User.id == user.id)
            result = await session.execute(stmt)
            user = result.scalar_one()
        return user

    # Check if email is already in use by another active account
    if profile.get("email"):
        stmt = select(User).where(User.email == profile["email"], User.deleted_at.is_(None))
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists. Please log in to that account and link this provider from Account Settings."
            )
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
        assigned_at=datetime.now(UTC).replace(tzinfo=None),
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
    # Get all local identities for this user
    stmt = select(AuthIdentity).where(
        AuthIdentity.user_id == user_id,
        AuthIdentity.provider == "local"
    )
    result = await session.execute(stmt)
    identities = list(result.scalars().all())
    
    hashed_password = get_password_hash(password)
    
    if identities:
        for identity in identities:
            identity.password_hash = hashed_password
    else:
        session.add(AuthIdentity(
            user_id=user_id,
            provider="local",
            password_hash=hashed_password
        ))
        
    # Revoke all tokens (security best practice on password change)
    await revoke_all_user_tokens(user_id, session)
    
    await session.commit()
    return {"message": "Password updated successfully"}


async def link_oauth_identity(user_id: uuid.UUID, profile: dict, session: AsyncSession) -> dict:
    """Link an OAuth identity to an existing authenticated user."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = select(AuthIdentity).where(
        AuthIdentity.provider == profile["provider"],
        AuthIdentity.provider_user_id == profile["provider_user_id"]
    )
    result = await session.execute(stmt)
    existing_identity = result.scalar_one_or_none()

    if existing_identity:
        if existing_identity.user_id == user_id:
            return {"message": f"{profile['provider']} is already linked to your account"}
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This {profile['provider']} account is already linked to a different user"
            )

    stmt = select(AuthIdentity).where(
        AuthIdentity.user_id == user_id,
        AuthIdentity.provider == profile["provider"]
    )
    result = await session.execute(stmt)
    user_provider_identity = result.scalar_one_or_none()

    if user_provider_identity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a {profile['provider']} account linked. Unlink it first to link a different one."
        )

    new_identity = AuthIdentity(
        user_id=user_id,
        provider=profile["provider"],
        provider_user_id=profile["provider_user_id"]
    )
    session.add(new_identity)
    await session.commit()

    return {"message": f"{profile['provider']} account linked successfully"}


async def unlink_identity(user_id: uuid.UUID, provider: str, session: AsyncSession) -> dict:
    """Unlink an auth identity from a user. Cannot remove the last identity."""
    stmt = select(AuthIdentity).where(AuthIdentity.user_id == user_id)
    result = await session.execute(stmt)
    identities = result.scalars().all()

    if len(identities) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your last authentication method. Link another provider first."
        )

    target = next((i for i in identities if i.provider == provider), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} identity linked to your account"
        )

    await session.delete(target)
    await session.commit()

    return {"message": f"{provider} account unlinked successfully"}
