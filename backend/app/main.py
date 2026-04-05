from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.db.database import engine, Base
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Webhook Delivery System",
    version="1.0.0",
    description="Reliable async webhook delivery with AI failure analysis",
    lifespan=lifespan,
)

# FRONTEND_URL accepts comma-separated values so you can whitelist
# both your Vercel production URL and preview URLs without redeploying.
# e.g. FRONTEND_URL=https://myapp.vercel.app,https://myapp-git-main-user.vercel.app
_extra = [u.strip() for u in os.getenv("FRONTEND_URL", "").split(",") if u.strip()]

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    *_extra,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}