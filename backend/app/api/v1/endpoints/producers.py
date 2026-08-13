from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.producer_service import producer_service
from app.schemas.producer import ProducerCreate, ProducerResponse, ProducerPublic

router = APIRouter()


@router.post("", response_model=ProducerResponse, status_code=201)
async def create_producer(
    data: ProducerCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        producer = await producer_service.create_producer(db, data)
        return producer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ProducerPublic])
async def list_producers(
    db: AsyncSession = Depends(get_db),
):
    return await producer_service.get_all_producers(db)
