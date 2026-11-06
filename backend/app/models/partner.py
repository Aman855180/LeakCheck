from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from app.models.base import Base


class Partner(Base):
    __tablename__ = "partners"

    id = Column(String(64), primary_key=True)  # e.g., 'amazon', 'flipkart', 'delhivery', 'shopify'
    name = Column(String(255), nullable=False)
    partner_type = Column(String(32), nullable=False)  # 'marketplace', 'courier_aggregator', 'd2c_storefront', 'quick_commerce', 'warehouse'
    channel = Column(String(64), nullable=False)       # 'marketplace', 'courier', 'd2c', 'quick_commerce', 'warehouse'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<Partner id={self.id} name={self.name} channel={self.channel}>"
