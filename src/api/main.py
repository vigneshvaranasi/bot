from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api.routers import users, chats, support, auth, roles
from src.api.db.database import engine
from src.api.db_models import Base

# app init
app = FastAPI(title="Support Bot API", version="1.0.0")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dth5w8dq-5173.inc1.devtunnels.ms",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["POST","OPTIONS","GET","PUT","*"],
    allow_headers=["*"],
)

# routing setup
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(roles.router, prefix="/roles", tags=["Roles"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(support.router, prefix="/support", tags=["Support"])


@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return JSONResponse(content={"message": "Preflight OK"})

# startup event
@app.on_event("startup")
async def startup():
    pass

# health check
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}