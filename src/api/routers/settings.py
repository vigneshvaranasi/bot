from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.api.db.session import get_session
from src.api.db.models import Setting
from src.api.auth.dependencies import get_current_user
from src.api.schemas.setting_schemas import SettingCreate, SettingUpdate, SettingResponse, SettingListResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(setting: SettingCreate, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # Check the last setting to avoid creating duplicates
    result = await db.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    last_setting = result.scalars().first()
    
    # Compare with the new setting
    if last_setting and (
        last_setting.deny_words == setting.deny_words and
        last_setting.model == setting.model and
        last_setting.temperature == setting.temperature and
        last_setting.langfuse_enabled == setting.langfuse_enabled and
        last_setting.auth_google_enabled == setting.auth_google_enabled and
        last_setting.auth_github_enabled == setting.auth_github_enabled and
        last_setting.auth_local_enabled == setting.auth_local_enabled
    ):
        # No change, return the existing last setting
        print("No changes detected, returning existing setting with deny_words:", last_setting.deny_words)
        return last_setting
    
    # Create new setting if different
    new_setting = Setting(
        user_id=current_user["user_id"],
        deny_words=setting.deny_words,
        model=setting.model,
        temperature=setting.temperature,
        langfuse_enabled=setting.langfuse_enabled,
        auth_google_enabled=setting.auth_google_enabled,
        auth_github_enabled=setting.auth_github_enabled,
        auth_local_enabled=setting.auth_local_enabled
    )
    db.add(new_setting)
    await db.commit()
    await db.refresh(new_setting)
    print("Created new setting with deny_words:", new_setting.deny_words)
    return new_setting

@router.get("/", response_model=SettingResponse)
async def get_latest_setting(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settings found")
    return setting

@router.get("/all", response_model=SettingListResponse)
async def list_settings(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Setting))
    settings = result.scalars().all()
    return SettingListResponse(settings=settings)

@router.get("/last", response_model=SettingResponse)
async def get_last_setting(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settings found")
    return setting

@router.put("/rollback", response_model=SettingResponse)
async def rollback_setting(db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # Get the latest setting
    result = await db.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settings found")
    
    # Delete the latest setting
    await db.delete(setting)
    await db.commit()
    
    # Get the new latest setting (after deletion)
    result = await db.execute(
        select(Setting)
        .order_by(Setting.updated_at.desc())
        .limit(1)
    )
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No previous settings found")
    return setting


# / -> Get the Global Settings

# /update -> Update the Global Settings

# /rollback -> Rollback to previous settings