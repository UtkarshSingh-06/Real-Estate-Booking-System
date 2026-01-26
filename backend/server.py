from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
import logging
import socketio
import googlemaps
import stripe
import jwt
import secrets
import hashlib
import aiohttp

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'realestate_db')]

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
async def get_current_user(authorization: Optional[str] = Header(None), session_token: Optional[str] = None):
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
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return User(**user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        # Fallback to session token lookup for backward compatibility
        session = await db.user_sessions.find_one({"session_token": token})
        if not session or datetime.fromisoformat(session['expires_at']) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        user = await db.users.find_one({"id": session['user_id']}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return User(**user)

# Auth Endpoints
@app.post("/api/auth/google")
async def google_auth(request: Request):
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
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if not existing_user:
            # Create new user
            user_id = f"user_{hashlib.sha256(google_id.encode()).hexdigest()[:16]}"
            new_user = {
                "id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "role": "buyer",
                "phone": None,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
        else:
            user_id = existing_user['id']
            # Update user info
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "name": name,
                    "picture": picture
                }}
            )
        
        # Create JWT token
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        jwt_payload = {
            "user_id": user_id,
            "email": email,
            "exp": expires_at.timestamp()
        }
        session_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")
        
        # Also create session for backward compatibility
        new_session = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(new_session)
        
        # Get updated user
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        
        return {
            "session_token": session_token,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "name": user['name'],
                "picture": user.get('picture'),
                "role": user.get('role', 'buyer')
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
async def logout(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    await db.user_sessions.delete_one({"session_token": token})
    return {"message": "Logged out successfully"}

# Property Endpoints
@app.get("/api/properties")
async def get_properties(user: User = Depends(get_current_user)):
    properties = await db.properties.find({"status": "published"}, {"_id": 0}).to_list(100)
    return {"properties": properties}

@app.get("/api/properties/my")
async def get_my_properties(user: User = Depends(get_current_user)):
    properties = await db.properties.find({"owner_id": user.id}, {"_id": 0}).to_list(100)
    return {"properties": properties}

@app.get("/api/properties/{property_id}")
async def get_property(property_id: str, user: User = Depends(get_current_user)):
    prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop

@app.post("/api/properties")
async def create_property(prop_data: PropertyCreate, user: User = Depends(get_current_user)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Only owners/agents can create properties")
    
    # Geocode address if lat/lng not provided
    if not prop_data.latitude or not prop_data.longitude:
        gmaps = get_gmaps_client()
        if gmaps:
            try:
                geocode_result = gmaps.geocode(prop_data.address)
                if geocode_result:
                    location = geocode_result[0]['geometry']['location']
                    prop_data.latitude = location['lat']
                    prop_data.longitude = location['lng']
            except Exception as e:
                logger.error(f"Geocoding error: {str(e)}")
                # Use default location if geocoding fails
                prop_data.latitude = 40.7128
                prop_data.longitude = -74.0060
        else:
            # Default NYC location
            prop_data.latitude = 40.7128
            prop_data.longitude = -74.0060
    
    property_id = f"prop_{datetime.now().timestamp()}"
    new_property = {
        "id": property_id,
        "owner_id": user.id,
        **prop_data.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.properties.insert_one(new_property)
    return {"id": property_id, "message": "Property created successfully"}

@app.put("/api/properties/{property_id}")
async def update_property(property_id: str, prop_data: PropertyCreate, user: User = Depends(get_current_user)):
    prop = await db.properties.find_one({"id": property_id})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    if prop['owner_id'] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = prop_data.model_dump()
    await db.properties.update_one({"id": property_id}, {"$set": update_data})
    return {"message": "Property updated successfully"}

@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str, user: User = Depends(get_current_user)):
    prop = await db.properties.find_one({"id": property_id})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    if prop['owner_id'] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.properties.delete_one({"id": property_id})
    return {"message": "Property deleted successfully"}

@app.post("/api/properties/search")
async def search_properties(query: SearchQuery, user: User = Depends(get_current_user)):
    filter_query: Dict[str, Any] = {"status": "published"}
    
    if query.min_price is not None:
        filter_query["price"] = {"$gte": query.min_price}
    if query.max_price is not None:
        if "price" in filter_query:
            filter_query["price"]["$lte"] = query.max_price
        else:
            filter_query["price"] = {"$lte": query.max_price}
    
    if query.property_type:
        filter_query["property_type"] = query.property_type
    if query.bedrooms is not None:
        filter_query["bedrooms"] = {"$gte": query.bedrooms}
    if query.bathrooms is not None:
        filter_query["bathrooms"] = {"$gte": query.bathrooms}
    
    properties = await db.properties.find(filter_query, {"_id": 0}).to_list(100)
    return {"properties": properties}

# Booking Endpoints
@app.post("/api/bookings")
async def create_booking(booking_data: BookingCreate, user: User = Depends(get_current_user)):
    # Get property
    prop = await db.properties.find_one({"id": booking_data.property_id})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    
    booking_id = f"book_{datetime.now().timestamp()}"
    new_booking = {
        "id": booking_id,
        "property_id": booking_data.property_id,
        "user_id": user.id,
        "owner_id": prop['owner_id'],
        "booking_date": booking_data.booking_date,
        "time_slot": booking_data.time_slot,
        "status": "pending",
        "payment_status": "pending",
        "deposit_amount": booking_data.deposit_amount,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.bookings.insert_one(new_booking)
    return {"id": booking_id, "message": "Booking request created"}

@app.get("/api/bookings")
async def get_bookings(user: User = Depends(get_current_user)):
    bookings = await db.bookings.find({"user_id": user.id}, {"_id": 0}).to_list(100)
    return {"bookings": bookings}

@app.get("/api/bookings/owner")
async def get_owner_bookings(user: User = Depends(get_current_user)):
    if user.role not in ["owner", "agent", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    bookings = await db.bookings.find({"owner_id": user.id}, {"_id": 0}).to_list(100)
    return {"bookings": bookings}

@app.put("/api/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, status: str, user: User = Depends(get_current_user)):
    booking = await db.bookings.find_one({"id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking['owner_id'] != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if status not in ["confirmed", "rejected", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    await db.bookings.update_one({"id": booking_id}, {"$set": {"status": status}})
    return {"message": f"Booking {status}"}

# Payment Endpoints
@app.post("/api/payments/create-checkout")
async def create_checkout(request: Request, user: User = Depends(get_current_user)):
    data = await request.json()
    booking_id = data.get('booking_id')
    origin_url = data.get('origin_url')
    
    if not booking_id or not origin_url:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    booking = await db.bookings.find_one({"id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking['user_id'] != user.id:
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
                    'unit_amount': int(booking['deposit_amount'] * 100),  # Convert to cents
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
        new_transaction = {
            "id": transaction_id,
            "session_id": checkout_session.id,
            "booking_id": booking_id,
            "user_id": user.id,
            "amount": booking['deposit_amount'],
            "currency": "usd",
            "status": "pending",
            "payment_status": "pending",
            "metadata": {"booking_id": booking_id},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.payment_transactions.insert_one(new_transaction)
        
        return {"url": checkout_session.url, "session_id": checkout_session.id}
    except Exception as e:
        logger.error(f"Stripe checkout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating checkout session")

@app.get("/api/payments/status/{session_id}")
async def get_payment_status(session_id: str, user: User = Depends(get_current_user)):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        # Retrieve checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Update transaction
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        if transaction:
            payment_status = 'paid' if checkout_session.payment_status == 'paid' else 'pending'
            
            if transaction['payment_status'] != 'paid' and payment_status == 'paid':
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {"payment_status": "paid", "status": "completed"}}
                )
                # Update booking
                await db.bookings.update_one(
                    {"id": transaction['booking_id']},
                    {"$set": {"payment_status": "paid"}}
                )
        
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
async def stripe_webhook(request: Request):
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
            transaction = await db.payment_transactions.find_one({"session_id": session_id})
            if transaction:
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {"payment_status": "paid", "status": "completed"}}
                )
                # Update booking
                await db.bookings.update_one(
                    {"id": transaction['booking_id']},
                    {"$set": {"payment_status": "paid"}}
                )
                logger.info(f"Payment completed for booking {transaction['booking_id']}")
        
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
async def get_conversations(user: User = Depends(get_current_user)):
    conversations = await db.conversations.find(
        {"participants": user.id},
        {"_id": 0}
    ).to_list(100)
    return {"conversations": conversations}

@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: User = Depends(get_current_user)):
    messages = await db.messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return {"messages": messages}

@app.post("/api/messages")
async def send_message(message_data: MessageCreate, user: User = Depends(get_current_user)):
    # Find or create conversation
    participants = sorted([user.id, message_data.receiver_id])
    conversation = await db.conversations.find_one({
        "participants": {"$all": participants},
        "property_id": message_data.property_id
    })
    
    if not conversation:
        conversation_id = f"conv_{datetime.now().timestamp()}"
        new_conversation = {
            "id": conversation_id,
            "participants": participants,
            "property_id": message_data.property_id,
            "last_message": message_data.message,
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.conversations.insert_one(new_conversation)
    else:
        conversation_id = conversation['id']
        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {
                "last_message": message_data.message,
                "last_message_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    # Create message
    message_id = f"msg_{datetime.now().timestamp()}"
    new_message = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender_id": user.id,
        "receiver_id": message_data.receiver_id,
        "message": message_data.message,
        "attachment_url": message_data.attachment_url,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(new_message)
    
    # Emit via Socket.IO
    await sio.emit('new_message', new_message, room=message_data.receiver_id)
    
    return {"id": message_id, "conversation_id": conversation_id}

@app.put("/api/messages/{message_id}/read")
async def mark_message_read(message_id: str, user: User = Depends(get_current_user)):
    message = await db.messages.find_one({"id": message_id})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message['receiver_id'] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.messages.update_one({"id": message_id}, {"$set": {"read": True}})
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

# Root
@app.get("/api/")
async def root():
    return {"message": "Real Estate Booking System API"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}