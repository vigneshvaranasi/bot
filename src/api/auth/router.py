import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.session import get_session
from .schemas import UserSignup, UserLogin, TokenResponse, UserResponse, PasswordUpdate
from .service import signup_user, login_user, get_user_profile, get_provider_instance, resolve_oauth_user, revoke_token, update_user_password
from .dependencies import get_current_user
from ..core.jwt import create_access_token, create_oauth_state, decode_oauth_state
from ..db.models import Setting

logger = logging.getLogger(__name__)

router = APIRouter()

async def check_auth_enabled(provider: str, session: AsyncSession):
    result = await session.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    if not setting:
        return 
    
    if provider == "local" and setting.auth_local_enabled is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local authentication is disabled")
    if provider == "google" and setting.auth_google_enabled is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google authentication is disabled")
    if provider == "github" and setting.auth_github_enabled is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub authentication is disabled")
    if provider == "microsoft" and setting.auth_microsoft_enabled is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Microsoft authentication is disabled")

@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    jti = current_user.get("jti")
    exp = current_user.get("exp")
    if jti and exp:
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        await revoke_token(jti, expires_at, session)
    return {"message": "Logged out successfully"}

@router.post("/password")
async def set_password(
    data: PasswordUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    user_id = uuid.UUID(current_user["user_id"])
    return await update_user_password(user_id, data.password, session)

@router.post("/signup")
async def signup(user_data: UserSignup, session: AsyncSession = Depends(get_session)):
    await check_auth_enabled("local", session)
    return await signup_user(user_data, session)

@router.post("/login", response_model=TokenResponse)
async def login(user_credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    await check_auth_enabled("local", session)
    return await login_user(user_credentials, session)

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    user_id = uuid.UUID(current_user["user_id"])
    user = await get_user_profile(user_id, session)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role.name,
        auth_identities=[ai.provider for ai in user.auth_identities]
    )

@router.get("/providers")
async def list_providers(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    providers = []
    if not setting:
        providers = ["local", "google", "github", "microsoft"]
    else:
        if setting.auth_local_enabled is not False:
            providers.append("local")
        if setting.auth_google_enabled is not False:
            providers.append("google")
        if setting.auth_github_enabled is not False:
            providers.append("github")
        if setting.auth_microsoft_enabled is not False:
            providers.append("microsoft")
    return {"providers": providers}

@router.get("/oauth/{provider}")
async def oauth_login(provider: str, session: AsyncSession = Depends(get_session)):
    await check_auth_enabled(provider, session)
    # 1. Get provider instance
    provider_instance = await get_provider_instance(provider, session)
    
    # 2. Generate state
    state = create_oauth_state(provider=provider, purpose="login")
    
    # 3. Get auth URL
    auth_url = await provider_instance.get_authorization_url(state)
    
    return {"authorization_url": auth_url, "state": state}

@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(provider: str, code: str, state: str, session: AsyncSession = Depends(get_session)):
    logger.debug("OAuth callback received for %s", provider)
    await check_auth_enabled(provider, session)
    # 1. Validate state
    payload = decode_oauth_state(state)
    if not payload:
        logger.debug("OAuth state decoding failed for %s", provider)
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if payload.get("purpose") != "login":
        logger.debug("OAuth invalid purpose for %s: %s", provider, payload.get("purpose"))
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if payload.get("provider") != provider:
        logger.debug("OAuth provider mismatch: expected %s, got %s", provider, payload.get("provider"))
        raise HTTPException(status_code=400, detail="Provider mismatch")

    # 2. Get provider instance
    provider_instance = await get_provider_instance(provider, session)

    # 3. Exchange code
    try:
        token_data = await provider_instance.exchange_code_for_token(code)
    except httpx.HTTPStatusError as e:
        logger.exception("OAuth token exchange failed for %s", provider)
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    # 4. Fetch profile
    try:
        profile = await provider_instance.fetch_user_profile(token_data)
    except Exception as e:
        logger.exception("OAuth fetch profile failed for %s", provider)
        raise HTTPException(status_code=500, detail="Authentication failed")
    
    # 5. Resolve user
    user = await resolve_oauth_user(profile, session)
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
        

    # 6. give JWT
    role_name = user.role.name
    
    access_token = create_access_token(
        user_id=str(user.id),
        role=role_name,
        auth_provider=provider,
        token_version=user.token_version
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=role_name
    )

