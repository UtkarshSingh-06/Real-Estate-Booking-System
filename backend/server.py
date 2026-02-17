from pathlib import Path
import os

# Load .env from backend directory before any other imports that use env (e.g. database)
_backend_dir = Path(__file__).resolve().parent
_env_file = _backend_dir / ".env"
# Also try cwd/backend/.env in case process was started from project root
if not _env_file.exists() and Path.cwd().name != "backend":
    _env_file = Path.cwd() / "backend" / ".env"
if not _env_file.exists():
    _env_file = Path.cwd() / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value
from dotenv import load_dotenv
load_dotenv(dotenv_path=_env_file, override=True)

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging
import socketio
import googlemaps
import stripe
import jwt
import secrets
import hashlib
import aiohttp
import json

from database import (
    get_db, init_db, User as DBUser, UserSession as DBUserSession,
    Property as DBProperty, Booking as DBBooking, Conversation as DBConversation,
    Message as DBMessage, PaymentTransaction as DBPaymentTransaction
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Secret
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_urlsafe(32))

# Stripe
stripe.api_key = os.environ.get('STRIPE_API_KEY', '')
stripe_webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Google Maps client (lazy initialization)
gmaps_client = None
def get_gmaps_client():
    global gmaps_client
    if gmaps_client is None and os.environ.get('GOOGLE_MAPS_API_KEY'):
        gmaps_client = googlemaps.Client(key=os.environ.get('GOOGLE_MAPS_API_KEY'))
    return gmaps_client

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# FastAPI app
app = FastAPI(title="Real Estate Booking System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Models
class User(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "buyer"  # buyer, owner, agent, admin
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Property(BaseModel):
    id: str
    owner_id: str
    title: str
    description: str
    address: str
    latitude: float
    longitude: float
    price: float
    property_type: str  # apartment, house, villa, etc
    area_sqft: float
    bedrooms: int
    bathrooms: int
    amenities: List[str] = []
    images: List[str] = []
    status: str = "published"  # draft, published, unavailable
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PropertyCreate(BaseModel):
    title: str
    description: str
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price: float
    property_type: str
    area_sqft: float
    bedrooms: int
    bathrooms: int
    amenities: List[str] = []
    images: List[str] = []
    status: str = "published"

class Booking(BaseModel):
    id: str
    property_id: str
    user_id: str
    owner_id: str
    booking_date: datetime
    time_slot: str
    status: str = "pending"  # pending, confirmed, rejected, cancelled
    payment_status: str = "pending"  # pending, paid, refunded
    deposit_amount: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BookingCreate(BaseModel):
    property_id: str
    booking_date: str
    time_slot: str
    deposit_amount: float

class Message(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    receiver_id: str
    message: str
    attachment_url: Optional[str] = None
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageCreate(BaseModel):
    receiver_id: str
    property_id: Optional[str] = None
    message: str
    attachment_url: Optional[str] = None

class Conversation(BaseModel):
    id: str
    participants: List[str]
    property_id: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SearchQuery(BaseModel):
    query: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    min_area_sqft: Optional[float] = None
    max_area_sqft: Optional[float] = None

class PriceEstimateInput(BaseModel):
    property_type: str
    area_sqft: float
    bedrooms: int
    bathrooms: int
    amenities: List[str] = []

class PaymentTransaction(BaseModel):
    id: str
    session_id: str
    booking_id: str
    user_id: str
    amount: float
    currency: str = "usd"
    status: str = "pending"
    payment_status: str = "pending"
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Auth Helper
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = None
):
    token = None
    
    # Try to get token from Authorization header
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    # Or from session_token parameter (for cookie)
    elif session_token:
        token = session_token
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Verify JWT token
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Find user
        result = await db.execute(select(DBUser).where(DBUser.id == user_id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return User(
            id=db_user.id,
            email=db_user.email,
            name=db_user.name,
            picture=db_user.picture,
            role=db_user.role,
            phone=db_user.phone,
            created_at=db_user.created_at
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        # Fallback to session token lookup for backward compatibility
        result = await db.execute(select(DBUserSession).where(DBUserSession.session_token == token))
        session = result.scalar_one_or_none()
        if not session or session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        result = await db.execute(select(DBUser).where(DBUser.id == session.user_id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return User(
            id=db_user.id,
            email=db_user.email,
            name=db_user.name,
            picture=db_user.picture,
            role=db_user.role,
            phone=db_user.phone,
            created_at=db_user.created_at
        )

# Auth Endpoints
@app.post("/api/auth/google")
async def google_auth(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback"""
    data = await request.json()
    id_token = data.get('id_token')
    access_token = data.get('access_token')
    
    if not id_token:
        raise HTTPException(status_code=400, detail="ID token required")
    
    try:
        # Verify Google ID token
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={id_token}"
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Invalid Google token")
                
                user_data = await response.json()
        
        email = user_data.get('email')
        name = user_data.get('name')
        picture = user_data.get('picture')
        google_id = user_data.get('sub')
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in token")
        
        # Check if user exists
        result = await db.execute(select(DBUser).where(DBUser.email == email))
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            # Create new user
            user_id = f"user_{hashlib.sha256(google_id.encode()).hexdigest()[:16]}"
            new_user = DBUser(
                id=user_id,
                email=email,
                name=name,
                picture=picture,
                role="buyer",
                phone=None,
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user_id = new_user.id
        else:
            user_id = existing_user.id
            # Update user info
            existing_user.name = name
            existing_user.picture = picture
            await db.commit()
            await db.refresh(existing_user)
        
        # Create JWT token
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        jwt_payload = {
            "user_id": user_id,
            "email": email,
            "exp": expires_at.timestamp()
        }
        session_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")
        
        # Also create session for backward compatibility
        new_session = DBUserSession(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_session)
        await db.commit()
        
        # Get updated user
        result = await db.execute(select(DBUser).where(DBUser.id == user_id))
        user = result.scalar_one()
        
        return {
            "session_token": session_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "role": user.role or 'buyer'
            }
        }
    
    except Exception as e:
        logger.error(f"Google auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing authentication")

@app.post("/api/auth/session")
async def process_session(request: Request):
    """Legacy endpoint for backward compatibility"""
    return await google_auth(request)

@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return user

@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    result = await db.execute(select(DBUserSession).where(DBUserSession.session_token == token))
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
    return {"message": "Logged out successfully"}

# Property Endpoints
@app.get("/api/properties")
async def get_properties(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DBProperty).where(DBProperty.status == "published").limit(100)
    )
    properties = result.scalars().all()
    return {
        "properties": [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in properties
        ]
    }

@app.get("/api/properties/my")
async def get_my_properties(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DBProperty).where(DBProperty.owner_id == user.id).limit(100)
    )
    properties = result.scalars().all()
    return {
        "properties": [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in properties
        ]
    }

@app.get("/api/properties/{property_id}")
async def get_property(property_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBProperty).where(DBProperty.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return {
        "id": prop.id,
        "owner_id": prop.owner_id,
        "title": prop.title,
        "description": prop.description,
        "address": prop.address,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "price": prop.price,
        "property_type": prop.property_type,
        "area_sqft": prop.area_sqft,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "amenities": prop.amenities or [],
        "images": prop.images or [],
        "status": prop.status,
        "created_at": prop.created_at.isoformat() if prop.created_at else None
    }

@app.post("/api/properties")
async def create_property(prop_data: PropertyCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Only owners/agents can create properties")
    
    # Geocode address if lat/lng not provided
    latitude = prop_data.latitude
    longitude = prop_data.longitude
    if not latitude or not longitude:
        gmaps = get_gmaps_client()
        if gmaps:
            try:
                geocode_result = gmaps.geocode(prop_data.address)
                if geocode_result:
                    location = geocode_result[0]['geometry']['location']
                    latitude = location['lat']
                    longitude = location['lng']
            except Exception as e:
                logger.error(f"Geocoding error: {str(e)}")
                # Use default location if geocoding fails
                latitude = 40.7128
                longitude = -74.0060
        else:
            # Default NYC location
            latitude = 40.7128
            longitude = -74.0060
    
    property_id = f"prop_{datetime.now().timestamp()}"
    new_property = DBProperty(
        id=property_id,
        owner_id=user.id,
        title=prop_data.title,
        description=prop_data.description,
        address=prop_data.address,
        latitude=latitude,
        longitude=longitude,
        price=prop_data.price,
        property_type=prop_data.property_type,
        area_sqft=prop_data.area_sqft,
        bedrooms=prop_data.bedrooms,
        bathrooms=prop_data.bathrooms,
        amenities=prop_data.amenities,
        images=prop_data.images,
        status=prop_data.status,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_property)
    await db.commit()
    return {"id": property_id, "message": "Property created successfully"}

@app.put("/api/properties/{property_id}")
async def update_property(property_id: str, prop_data: PropertyCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBProperty).where(DBProperty.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    if prop.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update fields
    prop.title = prop_data.title
    prop.description = prop_data.description
    prop.address = prop_data.address
    if prop_data.latitude:
        prop.latitude = prop_data.latitude
    if prop_data.longitude:
        prop.longitude = prop_data.longitude
    prop.price = prop_data.price
    prop.property_type = prop_data.property_type
    prop.area_sqft = prop_data.area_sqft
    prop.bedrooms = prop_data.bedrooms
    prop.bathrooms = prop_data.bathrooms
    prop.amenities = prop_data.amenities
    prop.images = prop_data.images
    prop.status = prop_data.status
    
    await db.commit()
    return {"message": "Property updated successfully"}

@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBProperty).where(DBProperty.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    if prop.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.delete(prop)
    await db.commit()
    return {"message": "Property deleted successfully"}

@app.post("/api/properties/search")
async def search_properties(query: SearchQuery, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conditions = [DBProperty.status == "published"]
    
    if query.min_price is not None:
        conditions.append(DBProperty.price >= query.min_price)
    if query.max_price is not None:
        conditions.append(DBProperty.price <= query.max_price)
    
    if query.property_type:
        conditions.append(DBProperty.property_type == query.property_type)
    if query.bedrooms is not None:
        conditions.append(DBProperty.bedrooms >= query.bedrooms)
    if query.bathrooms is not None:
        conditions.append(DBProperty.bathrooms >= query.bathrooms)
    if query.min_area_sqft is not None:
        conditions.append(DBProperty.area_sqft >= query.min_area_sqft)
    if query.max_area_sqft is not None:
        conditions.append(DBProperty.area_sqft <= query.max_area_sqft)
    
    if query.query and query.query.strip():
        search_term = f"%{query.query.strip()}%"
        conditions.append(
            or_(
                DBProperty.title.like(search_term),
                DBProperty.description.like(search_term),
                DBProperty.address.like(search_term)
            )
        )
    
    stmt = select(DBProperty).where(and_(*conditions)).limit(100)
    result = await db.execute(stmt)
    properties = result.scalars().all()
    
    return {
        "properties": [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in properties
        ]
    }


@app.get("/api/properties/search/realtime")
async def realtime_search(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    property_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    limit: int = 20
):
    """Real-time property search with query params for instant filtering."""
    conditions = [DBProperty.status == "published"]
    
    if min_price is not None:
        conditions.append(DBProperty.price >= min_price)
    if max_price is not None:
        conditions.append(DBProperty.price <= max_price)
    if property_type:
        conditions.append(DBProperty.property_type == property_type)
    if bedrooms is not None:
        conditions.append(DBProperty.bedrooms >= bedrooms)
    if bathrooms is not None:
        conditions.append(DBProperty.bathrooms >= bathrooms)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        conditions.append(
            or_(
                DBProperty.title.like(search_term),
                DBProperty.description.like(search_term),
                DBProperty.address.like(search_term)
            )
        )
    
    stmt = select(DBProperty).where(and_(*conditions)).limit(limit)
    result = await db.execute(stmt)
    properties = result.scalars().all()
    
    return {
        "properties": [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in properties
        ]
    }


# --- AI & Analytics ---

def _estimate_price_from_data(property_type: str, area_sqft: float, bedrooms: int, bathrooms: int) -> float:
    """Estimate price using similar listings (average price per sqft by type, adjusted by beds/baths)."""
    # Use in-memory aggregation from DB in the route; this is a fallback formula
    base_per_sqft = {"apartment": 180, "house": 220, "villa": 350, "condo": 200}
    per_sqft = base_per_sqft.get(property_type.lower(), 200)
    room_factor = 1.0 + (bedrooms - 2) * 0.05 + (bathrooms - 2) * 0.03
    return max(50000, area_sqft * per_sqft * max(0.7, min(1.3, room_factor)))


@app.post("/api/ai/estimate-price")
async def estimate_price(data: PriceEstimateInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """AI-powered price estimation based on property features and market data."""
    stmt = select(DBProperty).where(
        and_(
            DBProperty.status == "published",
            DBProperty.property_type == data.property_type
        )
    ).limit(200)
    result = await db.execute(stmt)
    similar = result.scalars().all()
    
    if similar:
        # Weight by similarity (area, beds, baths)
        prices = []
        for p in similar:
            area_diff = abs(p.area_sqft - data.area_sqft) / max(data.area_sqft, 1)
            bed_diff = abs(p.bedrooms - data.bedrooms)
            bath_diff = abs(p.bathrooms - data.bathrooms)
            weight = 1.0 / (1.0 + area_diff * 0.5 + bed_diff * 0.2 + bath_diff * 0.2)
            prices.append((p.price, weight))
        total_w = sum(w for _, w in prices)
        if total_w > 0:
            estimated = sum(p * w for p, w in prices) / total_w
        else:
            estimated = _estimate_price_from_data(
                data.property_type, data.area_sqft, data.bedrooms, data.bathrooms
            )
    else:
        estimated = _estimate_price_from_data(
            data.property_type, data.area_sqft, data.bedrooms, data.bathrooms
        )
    return {
        "estimated_price": round(estimated, 2),
        "currency": "USD",
        "based_on_listings": len(similar),
        "inputs": data.model_dump()
    }


@app.get("/api/ai/recommendations")
async def get_recommendations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    property_id: Optional[str] = None,
    limit: int = 6
):
    """Real-time recommendations: similar properties or personalized by user bookings."""
    if property_id:
        result = await db.execute(
            select(DBProperty).where(
                and_(DBProperty.id == property_id, DBProperty.status == "published")
            )
        )
        prop = result.scalar_one_or_none()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        # Similar: same type, similar price band and area
        price_low = prop.price * 0.7
        price_high = prop.price * 1.3
        area_low = prop.area_sqft * 0.7
        area_high = prop.area_sqft * 1.3
        stmt = select(DBProperty).where(
            and_(
                DBProperty.status == "published",
                DBProperty.id != property_id,
                DBProperty.property_type == prop.property_type,
                DBProperty.price >= price_low,
                DBProperty.price <= price_high,
                DBProperty.area_sqft >= area_low,
                DBProperty.area_sqft <= area_high
            )
        ).limit(limit)
        result = await db.execute(stmt)
        similar = result.scalars().all()
        
        if len(similar) < limit:
            similar_ids = [p.id for p in similar] + [property_id]
            stmt = select(DBProperty).where(
                and_(
                    DBProperty.status == "published",
                    ~DBProperty.id.in_(similar_ids),
                    DBProperty.property_type == prop.property_type
                )
            ).limit(limit - len(similar))
            result = await db.execute(stmt)
            extra = result.scalars().all()
            similar = list(similar) + list(extra)
            similar = similar[:limit]
        
        return {
            "recommendations": [
                {
                    "id": p.id,
                    "owner_id": p.owner_id,
                    "title": p.title,
                    "description": p.description,
                    "address": p.address,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "price": p.price,
                    "property_type": p.property_type,
                    "area_sqft": p.area_sqft,
                    "bedrooms": p.bedrooms,
                    "bathrooms": p.bathrooms,
                    "amenities": p.amenities or [],
                    "images": p.images or [],
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in similar
            ],
            "type": "similar"
        }
    
    # Personalized: from user's past bookings
    result = await db.execute(
        select(DBBooking.property_id).where(DBBooking.user_id == user.id).limit(50)
    )
    bookings = result.scalars().all()
    
    if not bookings:
        # Fallback: popular (most booked) properties
        stmt = select(
            DBBooking.property_id,
            func.count(DBBooking.id).label('count')
        ).group_by(DBBooking.property_id).order_by(desc('count')).limit(limit * 2)
        result = await db.execute(stmt)
        top_bookings = result.all()
        top_ids = [row[0] for row in top_bookings]
        
        if not top_ids:
            stmt = select(DBProperty).where(DBProperty.status == "published").limit(limit)
            result = await db.execute(stmt)
            props = result.scalars().all()
        else:
            stmt = select(DBProperty).where(
                and_(DBProperty.id.in_(top_ids), DBProperty.status == "published")
            ).limit(limit)
            result = await db.execute(stmt)
            props = result.scalars().all()
        
        return {
            "recommendations": [
                {
                    "id": p.id,
                    "owner_id": p.owner_id,
                    "title": p.title,
                    "description": p.description,
                    "address": p.address,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "price": p.price,
                    "property_type": p.property_type,
                    "area_sqft": p.area_sqft,
                    "bedrooms": p.bedrooms,
                    "bathrooms": p.bathrooms,
                    "amenities": p.amenities or [],
                    "images": p.images or [],
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in props[:limit]
            ],
            "type": "trending"
        }
    
    booked_ids = list(set(bookings))
    stmt = select(DBProperty).where(
        and_(DBProperty.id.in_(booked_ids), DBProperty.status == "published")
    ).limit(20)
    result = await db.execute(stmt)
    booked_props = result.scalars().all()
    
    if not booked_props:
        stmt = select(DBProperty).where(DBProperty.status == "published").limit(limit)
        result = await db.execute(stmt)
        props = result.scalars().all()
        return {
            "recommendations": [
                {
                    "id": p.id,
                    "owner_id": p.owner_id,
                    "title": p.title,
                    "description": p.description,
                    "address": p.address,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "price": p.price,
                    "property_type": p.property_type,
                    "area_sqft": p.area_sqft,
                    "bedrooms": p.bedrooms,
                    "bathrooms": p.bathrooms,
                    "amenities": p.amenities or [],
                    "images": p.images or [],
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in props
            ],
            "type": "trending"
        }
    
    types = [p.property_type for p in booked_props]
    avg_price = sum(p.price for p in booked_props) / len(booked_props)
    stmt = select(DBProperty).where(
        and_(
            DBProperty.status == "published",
            ~DBProperty.id.in_(booked_ids),
            DBProperty.property_type.in_(types),
            DBProperty.price >= avg_price * 0.6,
            DBProperty.price <= avg_price * 1.4
        )
    ).limit(limit)
    result = await db.execute(stmt)
    recs = result.scalars().all()
    
    return {
        "recommendations": [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in recs
        ],
        "type": "personalized"
    }


@app.get("/api/analytics/market-trends")
async def market_trends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Predictive analytics: price and listing trends over time."""
    stmt = select(DBProperty).where(DBProperty.status == "published")
    result = await db.execute(stmt)
    all_props = result.scalars().all()
    
    by_period: Dict[str, List[Dict[str, Any]]] = {}
    for p in all_props:
        created = p.created_at
        if created:
            period = created.strftime("%Y-%m")
        else:
            period = datetime.now(timezone.utc).strftime("%Y-%m")
        by_period.setdefault(period, []).append({
            "price": p.price,
            "property_type": p.property_type or "unknown"
        })
    
    results = []
    for period in sorted(by_period.keys()):
        items = by_period[period]
        avg_price = sum(x["price"] for x in items) / len(items) if items else 0
        results.append({
            "_id": {"year": int(period[:4]), "month": int(period[5:7]), "property_type": "all"},
            "avg_price": round(avg_price, 2),
            "count": len(items)
        })
    return {"market_trends": results}


@app.get("/api/analytics/buyer-behavior")
async def buyer_behavior(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Predictive analytics: booking behavior by property type and popular listings."""
    # Bookings by property type
    stmt = select(
        DBProperty.property_type,
        func.count(DBBooking.id).label('bookings')
    ).join(
        DBBooking, DBBooking.property_id == DBProperty.id
    ).group_by(DBProperty.property_type).order_by(desc('bookings')).limit(20)
    result = await db.execute(stmt)
    by_type = [
        {"_id": row[0], "bookings": row[1]}
        for row in result.all()
    ]
    
    # Top properties by booking count
    stmt = select(
        DBBooking.property_id,
        func.count(DBBooking.id).label('bookings')
    ).group_by(DBBooking.property_id).order_by(desc('bookings')).limit(10)
    result = await db.execute(stmt)
    top_bookings = result.all()
    top_ids = [row[0] for row in top_bookings]
    id_to_count = {row[0]: row[1] for row in top_bookings}
    
    if top_ids:
        stmt = select(DBProperty).where(
            and_(DBProperty.id.in_(top_ids), DBProperty.status == "published")
        )
        result = await db.execute(stmt)
        props = result.scalars().all()
        props_list = [
            {
                "id": p.id,
                "owner_id": p.owner_id,
                "title": p.title,
                "description": p.description,
                "address": p.address,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "price": p.price,
                "property_type": p.property_type,
                "area_sqft": p.area_sqft,
                "bedrooms": p.bedrooms,
                "bathrooms": p.bathrooms,
                "amenities": p.amenities or [],
                "images": p.images or [],
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "booking_count": id_to_count.get(p.id, 0)
            }
            for p in props
        ]
        props_list.sort(key=lambda x: x["booking_count"], reverse=True)
    else:
        props_list = []
    
    return {
        "bookings_by_property_type": by_type,
        "most_popular_properties": props_list
    }


@app.get("/api/analytics/dashboard")
async def analytics_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Summary dashboard for market trends and buyer behavior."""
    total_properties = await db.scalar(
        select(func.count(DBProperty.id)).where(DBProperty.status == "published")
    )
    total_bookings = await db.scalar(select(func.count(DBBooking.id)))
    avg_price = await db.scalar(
        select(func.avg(DBProperty.price)).where(DBProperty.status == "published")
    )
    
    return {
        "total_listings": total_properties or 0,
        "total_bookings": total_bookings or 0,
        "average_listing_price": round(avg_price or 0, 2),
        "currency": "USD"
    }


# Booking Endpoints
@app.post("/api/bookings")
async def create_booking(booking_data: BookingCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Get property
    result = await db.execute(select(DBProperty).where(DBProperty.id == booking_data.property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    booking_id = f"book_{datetime.now().timestamp()}"
    booking_date = datetime.fromisoformat(booking_data.booking_date.replace('Z', '+00:00'))
    
    new_booking = DBBooking(
        id=booking_id,
        property_id=booking_data.property_id,
        user_id=user.id,
        owner_id=prop.owner_id,
        booking_date=booking_date,
        time_slot=booking_data.time_slot,
        status="pending",
        payment_status="pending",
        deposit_amount=booking_data.deposit_amount,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_booking)
    await db.commit()
    return {"id": booking_id, "message": "Booking request created"}

@app.get("/api/bookings")
async def get_bookings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DBBooking).where(DBBooking.user_id == user.id).limit(100)
    )
    bookings = result.scalars().all()
    return {
        "bookings": [
            {
                "id": b.id,
                "property_id": b.property_id,
                "user_id": b.user_id,
                "owner_id": b.owner_id,
                "booking_date": b.booking_date.isoformat() if b.booking_date else None,
                "time_slot": b.time_slot,
                "status": b.status,
                "payment_status": b.payment_status,
                "deposit_amount": b.deposit_amount,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in bookings
        ]
    }

@app.get("/api/bookings/owner")
async def get_owner_bookings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await db.execute(
        select(DBBooking).where(DBBooking.owner_id == user.id).limit(100)
    )
    bookings = result.scalars().all()
    return {
        "bookings": [
            {
                "id": b.id,
                "property_id": b.property_id,
                "user_id": b.user_id,
                "owner_id": b.owner_id,
                "booking_date": b.booking_date.isoformat() if b.booking_date else None,
                "time_slot": b.time_slot,
                "status": b.status,
                "payment_status": b.payment_status,
                "deposit_amount": b.deposit_amount,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in bookings
        ]
    }

@app.put("/api/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBBooking).where(DBBooking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if status not in ["confirmed", "rejected", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    booking.status = status
    await db.commit()
    return {"message": f"Booking {status}"}

# Payment Endpoints
@app.post("/api/payments/create-checkout")
async def create_checkout(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = await request.json()
    booking_id = data.get('booking_id')
    origin_url = data.get('origin_url')
    
    if not booking_id or not origin_url:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    result = await db.execute(select(DBBooking).where(DBBooking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        # Create Stripe checkout session
        success_url = f"{origin_url}/booking-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin_url}/bookings"
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Property Booking Deposit - {booking_id}',
                    },
                    'unit_amount': int(booking.deposit_amount * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'booking_id': booking_id,
                'user_id': user.id
            }
        )
        
        # Create payment transaction
        transaction_id = f"txn_{datetime.now().timestamp()}"
        new_transaction = DBPaymentTransaction(
            id=transaction_id,
            session_id=checkout_session.id,
            booking_id=booking_id,
            user_id=user.id,
            amount=booking.deposit_amount,
            currency="usd",
            status="pending",
            payment_status="pending",
            extra_metadata={"booking_id": booking_id},
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_transaction)
        await db.commit()
        
        return {"url": checkout_session.url, "session_id": checkout_session.id}
    except Exception as e:
        logger.error(f"Stripe checkout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating checkout session")

@app.get("/api/payments/status/{session_id}")
async def get_payment_status(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        # Retrieve checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Update transaction
        result = await db.execute(select(DBPaymentTransaction).where(DBPaymentTransaction.session_id == session_id))
        transaction = result.scalar_one_or_none()
        if transaction:
            payment_status = 'paid' if checkout_session.payment_status == 'paid' else 'pending'
            
            if transaction.payment_status != 'paid' and payment_status == 'paid':
                transaction.payment_status = "paid"
                transaction.status = "completed"
                # Update booking
                result = await db.execute(select(DBBooking).where(DBBooking.id == transaction.booking_id))
                booking = result.scalar_one_or_none()
                if booking:
                    booking.payment_status = "paid"
                await db.commit()
        
        return {
            "session_id": checkout_session.id,
            "payment_status": checkout_session.payment_status,
            "status": checkout_session.status
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking payment status")
    except Exception as e:
        logger.error(f"Payment status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking payment status")

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    if not stripe_webhook_secret:
        logger.warning("Stripe webhook secret not configured")
        return {"received": False}
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            body, signature, stripe_webhook_secret
        )
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            
            # Update transaction
            result = await db.execute(select(DBPaymentTransaction).where(DBPaymentTransaction.session_id == session_id))
            transaction = result.scalar_one_or_none()
            if transaction:
                transaction.payment_status = "paid"
                transaction.status = "completed"
                # Update booking
                result = await db.execute(select(DBBooking).where(DBBooking.id == transaction.booking_id))
                booking = result.scalar_one_or_none()
                if booking:
                    booking.payment_status = "paid"
                await db.commit()
                logger.info(f"Payment completed for booking {transaction.booking_id}")
        
        logger.info(f"Webhook event: {event['type']}")
        return {"received": True}
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook error")

# Message Endpoints
@app.get("/api/conversations")
async def get_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Get all conversations and filter in Python (MySQL JSON_CONTAINS can be tricky)
    stmt = select(DBConversation).limit(100)
    result = await db.execute(stmt)
    all_conversations = result.scalars().all()
    # Filter conversations where user.id is in participants
    conversations = [
        c for c in all_conversations
        if c.participants and user.id in (c.participants if isinstance(c.participants, list) else json.loads(c.participants) if isinstance(c.participants, str) else [])
    ]
    return {
        "conversations": [
            {
                "id": c.id,
                "participants": c.participants if isinstance(c.participants, list) else json.loads(c.participants) if isinstance(c.participants, str) else [],
                "property_id": c.property_id,
                "last_message": c.last_message,
                "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in conversations
        ]
    }

@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(DBMessage).where(
        DBMessage.conversation_id == conversation_id
    ).order_by(asc(DBMessage.created_at)).limit(100)
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return {
        "messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_id": m.sender_id,
                "receiver_id": m.receiver_id,
                "message": m.message,
                "attachment_url": m.attachment_url,
                "read": m.read,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }

@app.post("/api/messages")
async def send_message(message_data: MessageCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Find or create conversation
    participants = sorted([user.id, message_data.receiver_id])
    
    # Check if conversation exists with these participants and property
    # Get all conversations with matching property_id and filter in Python
    stmt = select(DBConversation).where(DBConversation.property_id == message_data.property_id)
    result = await db.execute(stmt)
    potential_conversations = result.scalars().all()
    
    conversation = None
    for conv in potential_conversations:
        conv_participants = conv.participants if isinstance(conv.participants, list) else json.loads(conv.participants) if isinstance(conv.participants, str) else []
        if set(conv_participants) == set(participants):
            conversation = conv
            break
    
    if not conversation:
        conversation_id = f"conv_{datetime.now().timestamp()}"
        new_conversation = DBConversation(
            id=conversation_id,
            participants=participants,
            property_id=message_data.property_id,
            last_message=message_data.message,
            last_message_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_conversation)
        await db.commit()
        await db.refresh(new_conversation)
        conversation_id = new_conversation.id
    else:
        conversation_id = conversation.id
        conversation.last_message = message_data.message
        conversation.last_message_at = datetime.now(timezone.utc)
        await db.commit()
    
    # Create message
    message_id = f"msg_{datetime.now().timestamp()}"
    new_message = DBMessage(
        id=message_id,
        conversation_id=conversation_id,
        sender_id=user.id,
        receiver_id=message_data.receiver_id,
        message=message_data.message,
        attachment_url=message_data.attachment_url,
        read=False,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    # Emit via Socket.IO
    message_dict = {
        "id": new_message.id,
        "conversation_id": new_message.conversation_id,
        "sender_id": new_message.sender_id,
        "receiver_id": new_message.receiver_id,
        "message": new_message.message,
        "attachment_url": new_message.attachment_url,
        "read": new_message.read,
        "created_at": new_message.created_at.isoformat() if new_message.created_at else None
    }
    await sio.emit('new_message', message_dict, room=message_data.receiver_id)
    
    return {"id": message_id, "conversation_id": conversation_id}

@app.put("/api/messages/{message_id}/read")
async def mark_message_read(message_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBMessage).where(DBMessage.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.receiver_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    message.read = True
    await db.commit()
    return {"message": "Message marked as read"}

# Socket.IO Events
@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def join_room(sid, data):
    user_id = data.get('user_id')
    if user_id:
        sio.enter_room(sid, user_id)
        logger.info(f"User {user_id} joined room")

@sio.event
async def send_message(sid, data):
    await sio.emit('new_message', data, room=data.get('receiver_id'))

@sio.event
async def typing(sid, data):
    await sio.emit('user_typing', data, room=data.get('receiver_id'))

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")

# Root
@app.get("/api/")
async def root():
    return {"message": "Real Estate Booking System API"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}