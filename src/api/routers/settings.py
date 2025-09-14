from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.db_models import Setting, User
from src.api.utils.auth import get_current_user
from src.api.schemas.setting_schemas import SettingCreate, SettingUpdate, SettingResponse, SettingListResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(setting: SettingCreate, db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    # Check the last setting to avoid creating duplicates
    result = await db.execute(select(Setting).order_by(Setting.updated_at.desc()))
    last_setting = result.scalars().first()
    
    
    # Compare with the new setting
    if last_setting and (
        last_setting.deny_words == setting.deny_words and
        last_setting.model == setting.model and
        last_setting.temperature == setting.temperature
    ):
        # No change, return the existing last setting
        return last_setting
    
    # Create new setting if different
    new_setting = Setting(
        user_id=current_user["user_id"],
        deny_words=setting.deny_words,
        model=setting.model,
        temperature=setting.temperature
    )
    db.add(new_setting)
    await db.commit()
    await db.refresh(new_setting)
    return new_setting

@router.get("/", response_model=SettingResponse)
async def get_latest_setting(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Setting).order_by(Setting.updated_at.desc()))
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
    result = await db.execute(select(Setting).order_by(Setting.updated_at.desc()))
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settings found")
    return setting

@router.put("/rollback", response_model=SettingResponse)
async def rollback_setting(db: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    result = await db.execute(select(Setting).order_by(Setting.updated_at.desc()))
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No settings found")
    await db.delete(setting)
    await db.commit()
    result = await db.execute(select(Setting).order_by(Setting.updated_at.desc()))
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No previous settings found")
    return setting

