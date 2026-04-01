from app.db.database import Base

# Import all models here so Alembic can detect them
from app.models import subscriber, event, delivery  # noqa: F401