import pytest
from httpx import AsyncClient
from src.api.main import app
from src.api.db.database import get_session
from src.api.models import User
from src.api.schemas import UserCreate

@pytest.mark.asyncio
async def test_create_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        user_data = {"email": "test@example.com", "password": "password123", "role_id": 1}
        response = await ac.post("/users", json=user_data)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_create_user_duplicate():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        user_data = {"email": "duplicate@example.com", "password": "password123", "role_id": 1}
        await ac.post("/users", json=user_data)
        response = await ac.post("/users", json=user_data)
        assert response.status_code == 400
        assert response.json()["detail"] == "User already exists"

@pytest.mark.asyncio
async def test_get_users():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/users")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
