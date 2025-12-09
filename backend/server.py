from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import socketio

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# In-memory store (keeps the project runnable without third-party services)
# ------------------------------------------------------------------------------

USERS: Dict[str, Dict] = {}
SESSIONS: Dict[str, Dict] = {}
PROPERTIES: List[Dict] = []
BOOKINGS: List[Dict] = []
CONVERSATIONS: List[Dict] = []
MESSAGES: List[Dict] = []
PAYMENTS: List[Dict] = []


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def seed_demo_data() -> None:
    """Preload a small, realistic dataset so the UI works out-of-the-box."""
    if PROPERTIES:
        return

    owner_id = generate_id("user")
    USERS[owner_id] = {
        "id": owner_id,
        "email": "owner@estatebook.com",
        "name": "Estate Owner",
        "role": "owner",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    demo_props = [
        {
            "title": "Modern Loft in Downtown",
            "description": "Sun-lit loft with skyline views, private terrace, and smart home controls.",
            "address": "123 Main St, New York, NY",
            "price": 850000,
            "property_type": "apartment",
            "area_sqft": 1200,
            "bedrooms": 2,
            "bathrooms": 2,
            "amenities": ["Gym", "Doorman", "Roof Deck", "Smart Locks"],
            "images": [
                "https://images.unsplash.com/photo-1505691938895-1758d7feb511?auto=format&fit=crop&w=900&q=80"
            ],
        },
        {
            "title": "Family Home with Garden",
            "description": "Quiet tree-lined street, spacious backyard, and renovated kitchen.",
            "address": "45 Oakwood Dr, Austin, TX",
            "price": 620000,
            "property_type": "house",
            "area_sqft": 2200,
            "bedrooms": 4,
            "bathrooms": 3,
            "amenities": ["Garage", "Backyard", "EV Charger", "Playroom"],
            "images": [
                "https://images.unsplash.com/photo-1568605114967-8130f3a36994?auto=format&fit=crop&w=900&q=80"
            ],
        },
        {
            "title": "Beachfront Villa",
            "description": "Wake up to ocean views, infinity pool, and private beach access.",
            "address": "8 Ocean Breeze Rd, Miami, FL",
            "price": 1420000,
            "property_type": "villa",
            "area_sqft": 3500,
            "bedrooms": 5,
            "bathrooms": 4,
            "amenities": ["Pool", "Private Beach", "Outdoor Kitchen", "Guest House"],
            "images": [
                "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80"
            ],
        },
    ]

    for prop in demo_props:
        prop_id = generate_id("prop")
        PROPERTIES.append(
            {
                "id": prop_id,
                "owner_id": owner_id,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "status": "published",
                "created_at": datetime.now(timezone.utc).isoformat(),
                **prop,
            }
        )


seed_demo_data()

# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------


class User(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str = "buyer"
    picture: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoginRequest(BaseModel):
    name: str
    email: EmailStr
    role: str = "buyer"


class PropertyCreate(BaseModel):
    title: str
    description: str
    address: str
    price: float
    property_type: str
    area_sqft: float
    bedrooms: int
    bathrooms: int
    amenities: List[str] = []
    images: List[str] = []
    status: str = "published"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BookingCreate(BaseModel):
    property_id: str
    booking_date: str
    time_slot: str
    deposit_amount: float


class MessageCreate(BaseModel):
    receiver_id: str
    property_id: Optional[str] = None
    message: str
    attachment_url: Optional[str] = None


class SearchQuery(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None


# ------------------------------------------------------------------------------
# FastAPI + Socket.IO setup
# ------------------------------------------------------------------------------

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(title="Real Estate Booking System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ------------------------------------------------------------------------------
# Auth utilities
# ------------------------------------------------------------------------------


def _get_token(authorization: Optional[str], session_token: Optional[str]) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    if session_token:
        return session_token
    raise HTTPException(status_code=401, detail="Not authenticated")


async def get_current_user(
    authorization: Optional[str] = Header(None), session_token: Optional[str] = None
) -> User:
    token = _get_token(authorization, session_token)
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Handle both datetime objects and ISO strings
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_data = USERS.get(session["user_id"])
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return User(**user_data)


def create_session(user_id: str) -> Dict:
    session_token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    session = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),  # Store as ISO string for consistency
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SESSIONS[session_token] = session
    return session


# ------------------------------------------------------------------------------
# Auth Endpoints
# ------------------------------------------------------------------------------


@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    existing = next((u for u in USERS.values() if u["email"] == payload.email), None)
    if existing:
        user_id = existing["id"]
        USERS[user_id].update({"name": payload.name, "role": payload.role})
    else:
        user_id = generate_id("user")
        USERS[user_id] = {
            "id": user_id,
            "email": payload.email,
            "name": payload.name,
            "role": payload.role,
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    session = create_session(user_id)
    return {"session_token": session["session_token"], "user": USERS[user_id]}


@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return user


@app.post("/api/auth/logout")
async def logout(authorization: str = Header(None)):
    token = _get_token(authorization, None)
    if token in SESSIONS:
        del SESSIONS[token]
    return {"message": "Logged out successfully"}


# ------------------------------------------------------------------------------
# Property Endpoints
# ------------------------------------------------------------------------------


@app.get("/api/properties")
async def get_properties(user: User = Depends(get_current_user)):
    return {"properties": [p for p in PROPERTIES if p.get("status") == "published"]}


@app.get("/api/properties/my")
async def get_my_properties(user: User = Depends(get_current_user)):
    return {"properties": [p for p in PROPERTIES if p.get("owner_id") == user.id]}


@app.get("/api/properties/{property_id}")
async def get_property(property_id: str, user: User = Depends(get_current_user)):
    prop = next((p for p in PROPERTIES if p["id"] == property_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@app.post("/api/properties")
async def create_property(prop_data: PropertyCreate, user: User = Depends(get_current_user)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Only owners/agents can create properties")

    prop_id = generate_id("prop")
    new_prop = {
        "id": prop_id,
        "owner_id": user.id,
        "latitude": prop_data.latitude or 40.7128,
        "longitude": prop_data.longitude or -74.0060,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **prop_data.model_dump(),
    }
    PROPERTIES.append(new_prop)
    return {"id": prop_id, "message": "Property created successfully"}


@app.put("/api/properties/{property_id}")
async def update_property(property_id: str, prop_data: PropertyCreate, user: User = Depends(get_current_user)):
    prop = next((p for p in PROPERTIES if p["id"] == property_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop["owner_id"] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    for key, value in prop_data.model_dump().items():
        prop[key] = value
    return {"message": "Property updated successfully"}


@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str, user: User = Depends(get_current_user)):
    idx = next((i for i, p in enumerate(PROPERTIES) if p["id"] == property_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Property not found")
    prop = PROPERTIES[idx]
    if prop["owner_id"] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    PROPERTIES.pop(idx)
    return {"message": "Property deleted successfully"}


@app.post("/api/properties/search")
async def search_properties(query: SearchQuery, user: User = Depends(get_current_user)):
    results = [p for p in PROPERTIES if p.get("status") == "published"]
    if query.min_price is not None:
        results = [p for p in results if p["price"] >= query.min_price]
    if query.max_price is not None:
        results = [p for p in results if p["price"] <= query.max_price]
    if query.property_type:
        results = [p for p in results if p["property_type"] == query.property_type]
    if query.bedrooms is not None:
        results = [p for p in results if p["bedrooms"] >= query.bedrooms]
    if query.bathrooms is not None:
        results = [p for p in results if p["bathrooms"] >= query.bathrooms]
    return {"properties": results}


# ------------------------------------------------------------------------------
# Booking Endpoints
# ------------------------------------------------------------------------------


@app.post("/api/bookings")
async def create_booking(booking_data: BookingCreate, user: User = Depends(get_current_user)):
    prop = next((p for p in PROPERTIES if p["id"] == booking_data.property_id), None)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    booking_id = generate_id("book")
    booking = {
        "id": booking_id,
        "property_id": booking_data.property_id,
        "user_id": user.id,
        "owner_id": prop["owner_id"],
        "booking_date": booking_data.booking_date,
        "time_slot": booking_data.time_slot,
        "status": "pending",
        "payment_status": "pending",
        "deposit_amount": booking_data.deposit_amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    BOOKINGS.append(booking)
    return {"id": booking_id, "message": "Booking request created"}


@app.get("/api/bookings")
async def get_bookings(user: User = Depends(get_current_user)):
    return {"bookings": [b for b in BOOKINGS if b["user_id"] == user.id]}


@app.get("/api/bookings/owner")
async def get_owner_bookings(user: User = Depends(get_current_user)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return {"bookings": [b for b in BOOKINGS if b["owner_id"] == user.id]}


@app.put("/api/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str, user: User = Depends(get_current_user)):
    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["owner_id"] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    if status not in ["confirmed", "rejected", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    booking["status"] = status
    return {"message": f"Booking {status}"}


# ------------------------------------------------------------------------------
# Payments (simulated checkout to keep the demo self contained)
# ------------------------------------------------------------------------------


@app.post("/api/payments/create-checkout")
async def create_checkout(request: Request, user: User = Depends(get_current_user)):
    data = await request.json()
    booking_id = data.get("booking_id")
    origin_url = data.get("origin_url")
    if not booking_id or not origin_url:
        raise HTTPException(status_code=400, detail="Missing required fields")

    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    session_id = generate_id("checkout")
    PAYMENTS.append(
        {
            "session_id": session_id,
            "booking_id": booking_id,
            "user_id": user.id,
            "amount": booking["deposit_amount"],
            "status": "completed",
            "payment_status": "paid",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    booking["payment_status"] = "paid"
    success_url = f"{origin_url}/booking-success?session_id={session_id}"
    return {"url": success_url, "session_id": session_id}


@app.get("/api/payments/status/{session_id}")
async def get_payment_status(session_id: str, user: User = Depends(get_current_user)):
    payment = next((p for p in PAYMENTS if p["session_id"] == session_id), None)
    if not payment:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "status": payment["status"],
        "payment_status": payment["payment_status"],
    }


# ------------------------------------------------------------------------------
# Messaging
# ------------------------------------------------------------------------------


@app.get("/api/conversations")
async def get_conversations(user: User = Depends(get_current_user)):
    return {"conversations": [c for c in CONVERSATIONS if user.id in c["participants"]]}


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: User = Depends(get_current_user)):
    conv = next((c for c in CONVERSATIONS if c["id"] == conversation_id and user.id in c["participants"]), None)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    sorted_msgs = sorted([m for m in MESSAGES if m["conversation_id"] == conversation_id], key=lambda m: m["created_at"])
    return {"messages": sorted_msgs}


@app.post("/api/messages")
async def send_message(message_data: MessageCreate, user: User = Depends(get_current_user)):
    participants = sorted([user.id, message_data.receiver_id])
    conv = next(
        (c for c in CONVERSATIONS if c["participants"] == participants and c.get("property_id") == message_data.property_id),
        None,
    )
    if not conv:
        conv = {
            "id": generate_id("conv"),
            "participants": participants,
            "property_id": message_data.property_id,
            "last_message": message_data.message,
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        CONVERSATIONS.append(conv)
    else:
        conv["last_message"] = message_data.message
        conv["last_message_at"] = datetime.now(timezone.utc).isoformat()

    message_id = generate_id("msg")
    new_message = {
        "id": message_id,
        "conversation_id": conv["id"],
        "sender_id": user.id,
        "receiver_id": message_data.receiver_id,
        "message": message_data.message,
        "attachment_url": message_data.attachment_url,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    MESSAGES.append(new_message)
    await sio.emit("new_message", new_message, room=message_data.receiver_id)
    return {"id": message_id, "conversation_id": conv["id"]}


@app.put("/api/messages/{message_id}/read")
async def mark_message_read(message_id: str, user: User = Depends(get_current_user)):
    msg = next((m for m in MESSAGES if m["id"] == message_id), None)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg["receiver_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    msg["read"] = True
    return {"message": "Message marked as read"}


# ------------------------------------------------------------------------------
# Socket.IO events
# ------------------------------------------------------------------------------


@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def join_room(sid, data):
    user_id = data.get("user_id")
    if user_id:
        sio.enter_room(sid, user_id)


@sio.event
async def send_message(sid, data):
    await sio.emit("new_message", data, room=data.get("receiver_id"))


@sio.event
async def typing(sid, data):
    await sio.emit("user_typing", data, room=data.get("receiver_id"))


# ------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------


@app.get("/api/")
async def root():
    return {"message": "Real Estate Booking System API"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}