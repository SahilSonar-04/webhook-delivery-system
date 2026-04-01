from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.subscriber_service import subscriber_service
from app.schemas.subscriber import (
    SubscriberCreate,
    SubscriberResponse,
    SubscriberPublic,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.api.v1.endpoints.deps import get_current_subscriber
from app.models.subscriber import Subscriber
import uuid

router = APIRouter()


@router.post("", response_model=SubscriberResponse, status_code=201)
async def create_subscriber(
    data: SubscriberCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new subscriber. Returns api_key — save it, shown only once."""
    try:
        subscriber = await subscriber_service.create_subscriber(db, data)
        return subscriber
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[SubscriberPublic])
async def list_subscribers(
    db: AsyncSession = Depends(get_db),
):
    return await subscriber_service.get_all_subscribers(db)


@router.post("/{subscriber_id}/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    subscriber_id: uuid.UUID,
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_subscriber: Subscriber = Depends(get_current_subscriber),
):
    """Register a URL to receive a specific event type."""
    if current_subscriber.id != subscriber_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    subscription = await subscriber_service.create_subscription(db, subscriber_id, data)
    return subscription


@router.get("/{subscriber_id}/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    subscriber_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_subscriber: Subscriber = Depends(get_current_subscriber),
):
    if current_subscriber.id != subscriber_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await subscriber_service.get_subscriptions(db, subscriber_id)