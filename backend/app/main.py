from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import engine, Base, AsyncSessionLocal
from app.services.delivery_service import delivery_service
import logging


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        recovered = await delivery_service.recover_stuck_deliveries(session)
        await session.commit()
        if recovered:
            logger.warning(f"Recovered {recovered} stuck delivery attempt(s) on startup")

    yield
    await engine.dispose()

app = FastAPI(
    title="Webhook Delivery System",
    version="1.0.0",
    description="Reliable async webhook delivery with AI failure analysis",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}
