from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Support Bot", version="1.0.0")

origins = [
    "https://dth5w8dq-5173.inc1.devtunnels.ms",
    "http://localhost:5173",
    "http://localhost:3000",
    "https://localhost:5173",
    "https://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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


from src.api.routers import auth
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

from src.api.routers import roles
app.include_router(roles.router, prefix="/roles", tags=["Roles"])