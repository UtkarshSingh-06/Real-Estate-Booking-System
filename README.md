# Real Estate Booking System

A full-stack real estate booking platform enabling intelligent property discovery, bookings, and real-time communication.

## Features

### Core Functionality

- 🔐 **JWT + Google OAuth Authentication** - Secure user authentication with role-based access control
- 🏠 **Property Management** - Create, search, and manage properties with advanced filters
- 📅 **Booking System** - Schedule property viewings with time slots and status management
- 💳 **Stripe Integration** - Secure deposit payments via Stripe Checkout
- 💬 **Real-time Messaging** - Live chat between buyers and property owners using Socket.IO
- 📱 **Responsive Design** - Fully responsive UI that works on all devices
- 🗺️ **Google Maps Integration** - Geocoding and location services

## Tech Stack

- **Backend**: FastAPI, MongoDB, Socket.IO
- **Frontend**: React, Tailwind CSS, shadcn/ui
- **Authentication**: JWT, Google OAuth
- **Payments**: Stripe
- **Real-time**: Socket.IO

## Prerequisites

- Python 3.8+
- Node.js 16+
- MongoDB (local or cloud instance)
- Google OAuth credentials
- Stripe account (for payments)

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the `backend` directory:
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=realestate_db
JWT_SECRET=your-secret-key-here
STRIPE_API_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
CORS_ORIGINS=http://localhost:3000
REACT_APP_BACKEND_URL=http://localhost:8001
```

5. Start the backend server:
```bash
# For Socket.IO support (recommended):
uvicorn server:socket_app --reload --port 8001 --host 0.0.0.0

# Or for FastAPI only (without Socket.IO):
uvicorn server:app --reload --port 8001
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
yarn install
# or
npm install
```

3. Create a `.env` file in the `frontend` directory:
```env
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
```

4. Start the development server:
```bash
yarn start
# or
npm start
```

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable Google+ API
4. Go to "Credentials" and create OAuth 2.0 Client ID
5. Add authorized JavaScript origins: `http://localhost:3000`
6. Add authorized redirect URIs: `http://localhost:3000`
7. Copy the Client ID to your frontend `.env` file

## Stripe Setup

1. Create a Stripe account at [stripe.com](https://stripe.com)
2. Get your API keys from the Dashboard
3. Add the secret key to your backend `.env` file
4. For webhooks, use Stripe CLI or configure in dashboard:
   ```bash
   stripe listen --forward-to localhost:8001/api/webhook/stripe
   ```

## Environment Variables

### Backend (.env)
- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name
- `JWT_SECRET` - Secret key for JWT tokens
- `STRIPE_API_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret
- `GOOGLE_MAPS_API_KEY` - Google Maps API key
- `CORS_ORIGINS` - Allowed CORS origins (comma-separated)
- `REACT_APP_BACKEND_URL` - Backend URL for webhooks

### Frontend (.env)
- `REACT_APP_BACKEND_URL` - Backend API URL
- `REACT_APP_GOOGLE_CLIENT_ID` - Google OAuth Client ID

## Project Structure

```
Real-Estate-Booking-System/
├── backend/
│   ├── server.py          # FastAPI server
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Backend environment variables
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   └── App.js         # Main app component
│   ├── package.json       # Node dependencies
│   └── .env              # Frontend environment variables
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/google` - Google OAuth login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Logout

### Properties
- `GET /api/properties` - List all properties
- `GET /api/properties/{id}` - Get property details
- `POST /api/properties` - Create property (owner/agent only)
- `POST /api/properties/search` - Search properties

### Bookings
- `POST /api/bookings` - Create booking
- `GET /api/bookings` - Get user bookings
- `PUT /api/bookings/{id}/status` - Update booking status

### Payments
- `POST /api/payments/create-checkout` - Create Stripe checkout session
- `GET /api/payments/status/{session_id}` - Check payment status
- `POST /api/webhook/stripe` - Stripe webhook handler

### Messages
- `GET /api/conversations` - Get user conversations
- `POST /api/messages` - Send message
- `GET /api/conversations/{id}/messages` - Get conversation messages

## Running the Application

1. Start MongoDB (if running locally)
2. Start the backend server (port 8001)
3. Start the frontend server (port 3000)
4. Open http://localhost:3000 in your browser

## Features Implemented

✅ User authentication with Google OAuth  
✅ Property listing and search  
✅ Property creation and management  
✅ Booking system with time slots  
✅ Stripe payment integration  
✅ Real-time messaging  
✅ Responsive design  
✅ User profiles and roles  

## License

This project is open source and available under the MIT License.
