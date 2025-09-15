import pytest
import json
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.main import app
from src.api.db.database import get_session
from src.api.db_models import Base, Setting, User
from src.api.schemas.setting_schemas import SettingCreate, SettingResponse, SettingListResponse
from src.api.utils.auth import get_current_user
from sqlalchemy.future import select
from uuid import uuid4


@pytest.fixture
async def client():
    mock_user = {"user_id": uuid4(), "email": ""}
    
    async def mock_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client
    
    app.dependency_overrides = {}


@pytest.fixture
async def db_session():
    async for session in get_session():
        yield session


@pytest.fixture
def denylist():
    with open("/Users/pavan/Projects/jpmc/bot/data/denylist.json", "r") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_create_setting(client: AsyncClient, db_session: AsyncSession, denylist):
    deny_words_str = ",".join(denylist)
    setting_data = {
        "deny_words": deny_words_str,
        "model": "gemini-2.5-flash",
        "temperature": "0.5"
    }
    
    response = await client.post("/settings/", json=setting_data)
    assert response.status_code == 201
    data = response.json()
    assert data["deny_words"] == deny_words_str
    assert data["model"] == "gemini-2.5-flash"
    assert data["temperature"] == "0.5"
    assert "id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_get_latest_setting(client: AsyncClient, db_session: AsyncSession, denylist):
    deny_words_str = ",".join(denylist[:10])
    setting_data = {
        "deny_words": deny_words_str,
        "model": "gemini-2.0-flash",
        "temperature": "0.7"
    }
    await client.post("/settings/", json=setting_data)
    
    response = await client.get("/settings/")
    assert response.status_code == 200
    data = response.json()
    assert data["deny_words"] == deny_words_str
    assert data["model"] == "gemini-2.0-flash"
    assert data["temperature"] == "0.7"


@pytest.mark.asyncio
async def test_get_all_settings(client: AsyncClient, db_session: AsyncSession, denylist):
    settings_data = [
        {
            "deny_words": ",".join(denylist[:5]),
            "model": "gemini-2.5-flash",
            "temperature": "0.1"
        },
        {
            "deny_words": ",".join(denylist[5:10]),
            "model": "gemini-2.0-flash",
            "temperature": "0.2"
        }
    ]
    
    for setting in settings_data:
        await client.post("/settings/", json=setting)
    
    response = await client.get("/settings/all")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data
    assert len(data["settings"]) >= 2 
    latest = data["settings"][0]
    assert latest["deny_words"] == ",".join(denylist[5:10])