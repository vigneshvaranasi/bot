from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.core.config import CORS_ORIGINS, CORS_ORIGIN_REGEX

app = FastAPI(title="Support Bot", version="1.0.0")

origins = "https://copilot.xendev.in"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Accept-Language",
        "Content-Language",
        "X-Requested-With",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Methods",
        "Origin",
        "Cache-Control",
        "Pragma"
    ],
    expose_headers=["*"],
    max_age=86400,
)


@app.options("/{full_path:path}")
async def options_handler():
    """Handle preflight OPTIONS requests"""
    return {"message": "OK"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


from src.api.auth.router import router as auth_router
from src.api.admin.router import router as admin_router

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])

from src.api.routers import roles
app.include_router(roles.router, prefix="/roles", tags=["Roles"])

from src.api.routers import chat
app.include_router(chat.router, prefix="/chats", tags=["Chat"])

from src.api.routers import settings
app.include_router(settings.router, prefix="/settings", tags=["Settings"])

from src.api.routers import integrations
app.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])

from src.api.routers import knowledge_base
app.include_router(knowledge_base.router, tags=["Knowledge Base"])

from src.api.routers import llm_providers
app.include_router(llm_providers.router, prefix="/llm-providers", tags=["LLM Providers"])

from src.api.routers import permissions
app.include_router(permissions.router, tags=["Permissions"])

from src.api.routers import feedback
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
