from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.subscriber_service import subscriber_service
from app.models.subscriber import Subscriber


async def get_current_subscriber(
    x_api_key: str = Header(..., description="Your API key"),
    db: AsyncSession = Depends(get_db),
) -> Subscriber:
    subscriber = await subscriber_service.get_subscriber_by_api_key(db, x_api_key)
    if not subscriber:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return subscriber