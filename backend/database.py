"""Database configuration and models for MySQL using SQLAlchemy."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey
from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load .env from backend directory (BACKEND_DIR set by run script, or this file's dir)
_backend_dir = Path(os.environ.get("BACKEND_DIR", str(Path(__file__).resolve().parent))).resolve()
_env_path = (_backend_dir / ".env") if _backend_dir.is_dir() else (Path(__file__).resolve().parent / ".env")
# Always parse .env file directly so we get correct values regardless of cwd/import order
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k.startswith("DB_"):
                    os.environ[k] = v
load_dotenv(dotenv_path=_env_path, override=True)

# Database URL - MySQL format: mysql+aiomysql://user:password@host:port/database
# quote_plus so passwords with @, :, etc. work
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '3306')
DB_NAME = os.environ.get('DB_NAME', 'realestate_db')

DATABASE_URL = f"mysql+aiomysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture = Column(String(500), nullable=True)
    role = Column(String(20), default="buyer", nullable=False)  # buyer, owner, agent, admin
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    properties = relationship("Property", back_populates="owner")
    bookings = relationship("Booking", back_populates="user")
    owner_bookings = relationship("Booking", foreign_keys="Booking.owner_id", back_populates="owner")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")


class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Property(Base):
    __tablename__ = "properties"
    
    id = Column(String(50), primary_key=True)
    owner_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    address = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    price = Column(Float, nullable=False, index=True)
    property_type = Column(String(50), nullable=False, index=True)  # apartment, house, villa, etc
    area_sqft = Column(Float, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer, nullable=False)
    amenities = Column(JSON, default=list)  # List of strings stored as JSON
    images = Column(JSON, default=list)  # List of strings stored as JSON
    status = Column(String(20), default="published", nullable=False, index=True)  # draft, published, unavailable
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="properties")
    bookings = relationship("Booking", back_populates="property")


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(String(50), primary_key=True)
    property_id = Column(String(50), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_date = Column(DateTime(timezone=True), nullable=False)
    time_slot = Column(String(50), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, confirmed, rejected, cancelled
    payment_status = Column(String(20), default="pending", nullable=False)  # pending, paid, refunded
    deposit_amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    property = relationship("Property", back_populates="bookings")
    user = relationship("User", foreign_keys=[user_id], back_populates="bookings")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owner_bookings")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(50), primary_key=True)
    participants = Column(JSON, nullable=False)  # List of user IDs stored as JSON
    property_id = Column(String(50), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True)
    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String(50), primary_key=True)
    conversation_id = Column(String(50), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    attachment_url = Column(String(500), nullable=True)
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(String(50), primary_key=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    booking_id = Column(String(50), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="usd", nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    payment_status = Column(String(20), default="pending", nullable=False)
    extra_metadata = Column(JSON, default=dict)  # renamed from 'metadata' (reserved in SQLAlchemy)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# Dependency to get database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Initialize database (create tables)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
