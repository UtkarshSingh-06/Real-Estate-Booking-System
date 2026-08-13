# Real Estate Booking System

Full-stack property discovery, viewing bookings, Stripe deposits, and realtime messaging.

## Overview

Buyers browse/search listings, request viewing slots, pay deposits via Stripe Checkout, and message owners. Owners manage listings and approve/reject booking requests. The API is FastAPI + MySQL (SQLAlchemy async); the UI is React (CRA/CRACO) + Tailwind/shadcn.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams, booking lifecycle, and security boundaries.

```
frontend (React)  --REST/JWT-->  backend FastAPI
                              --Socket.IO-->  authenticated realtime messaging
                              --webhooks-->  Stripe (payment source of truth)
                              --SQLAlchemy-->  MySQL
```

Backend layout:

```
backend/
  app/
    main.py              # FastAPI + Socket.IO ASGI app
    core/                # config, security, dependencies, enums
    db/                  # session, base, model registry
    models/              # SQLAlchemy models
    schemas/             # Pydantic request/response models
    routers/             # HTTP routes
    services/            # business logic (booking, payments, auth, …)
    websocket/           # authenticated Socket.IO handlers
  alembic/               # DB migrations
  tests/                 # pytest suite (SQLite in-memory)
  server.py              # thin re-export for `uvicorn server:socket_app`
  .env.example
```

## Features

- Google Identity Services login (ID token verified server-side)
- JWT sessions with role-aware authorization
- Property CRUD with soft-archive (historical bookings preserved)
- Search/filter/sort/pagination for listings
- Booking state machine with slot uniqueness + expiration
- **Server-calculated deposits** (default 10% of listing price; client cannot override)
- Stripe Checkout only after owner approval (`payment_pending` status)
- Authenticated Socket.IO messaging (identity from JWT, not client `user_id`)
- Similarity-based price estimator and recommendations (honestly labeled; not ML)
- Market/owner analytics dashboard

## Tech stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Pydantic v2, python-socketio |
| DB | MySQL 8 + SQLAlchemy 2 async (`aiomysql`), Alembic |
| Auth | Google ID tokens (`google-auth`), JWT (`PyJWT`) |
| Payments | Stripe Checkout + webhooks |
| Frontend | React 19, React Router, Axios, Socket.IO client, Tailwind, shadcn/ui |

## Environment variables

Copy examples and fill in real values. **Never commit `.env` files.**

### Backend (`backend/.env`)

See `backend/.env.example`. Required highlights:

- `JWT_SECRET` — long random secret (required)
- `CORS_ORIGINS` — explicit origins, e.g. `http://localhost:3000` (no `*` in production)
- `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME` — or `DATABASE_URL`
- `GOOGLE_CLIENT_ID` — same Web client ID as the frontend
- `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET`
- Optional: `GOOGLE_MAPS_API_KEY`

### Frontend (`frontend/.env`)

See `frontend/.env.example`:

- `REACT_APP_BACKEND_URL=http://localhost:8001`
- `REACT_APP_GOOGLE_CLIENT_ID=...apps.googleusercontent.com`

## Local setup

### 1. Database

MySQL 8+:

```sql
CREATE DATABASE realestate_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or Docker:

```bash
docker run --name mysql-realestate -e MYSQL_ROOT_PASSWORD=yourpassword -e MYSQL_DATABASE=realestate_db -p 3306:3306 -d mysql:8.0
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then edit secrets
```

Run migrations (required in production/staging):

```bash
alembic upgrade head
```

In local development/test, the app may still call `create_all()` on startup when `ENVIRONMENT` is not `production` or `staging`.

Start API + Socket.IO:

```bash
uvicorn server:socket_app --reload --host 0.0.0.0 --port 8001
```

Health: `GET http://localhost:8001/api/health`  
Docs (non-production): `http://localhost:8001/api/docs`

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env   # set backend URL + Google client ID
npm start
```

Open `http://localhost:3000`.

## Authentication

1. Frontend loads Google Identity Services and obtains an ID token.
2. `POST /api/auth/google` with `{ "id_token": "..." }`.
3. Backend verifies the token against `GOOGLE_CLIENT_ID`, upserts the user, returns a JWT.
4. Clients send `Authorization: Bearer <token>` on REST calls.
5. Socket.IO connections pass the same token via `auth: { token }` (server derives `user_id`).

Google Cloud Console: create an OAuth **Web** client, authorized JavaScript origins `http://localhost:3000`.

## Bookings

State machine:

`requested → approved/rejected/cancelled/expired`  
`approved → payment_pending` (automatic on owner approve)  
`payment_pending → confirmed` (via Stripe webhook) / `cancelled` / `expired`

Buyers **cannot** start Stripe checkout until the owner has approved and the booking is `payment_pending`. Deposit amounts are computed on the server from the listing price (default 10%).

- Availability is checked under a property row lock.
- Active holds use a unique `slot_key`; cancelled/rejected/expired clear it so the slot frees.
- Unpaid requests expire after `BOOKING_REQUEST_EXPIRE_HOURS` (default 48).

## Stripe

1. Set `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET`.
2. Forward webhooks locally:

```bash
stripe listen --forward-to localhost:8001/api/webhook/stripe
```

3. `POST /api/payments/create-checkout` creates a Checkout Session.
4. **Webhooks** mark payments paid and bookings `confirmed` (idempotent via `processed_webhook_events`).
5. `GET /api/payments/status/{session_id}` is **read-only** for UI polling — it does not mutate booking state.

## Socket.IO messaging

- Connect with JWT in `auth.token`.
- Users join `user:{id}` rooms derived server-side.
- Conversation access is checked before joining `conversation:{id}` or reading messages via REST.
- File attachments are **not** supported (API rejects `attachment_url`).

## Price estimates & recommendations

These are **similarity / heuristic** features based on listing attributes and booking history — not trained ML models. API responses include `method`, `confidence`, and/or `strategy` fields.

## Tests

### Unit tests (SQLite, fast)

```bash
cd backend
.venv\Scripts\activate   # or source .venv/bin/activate
pytest tests -v -m "not integration"
```

### MySQL integration tests

Start test MySQL (Docker):

```bash
docker compose -f docker-compose.test.yml up -d
```

Then:

```bash
cd backend
export RUN_MYSQL_TESTS=1   # PowerShell: $env:RUN_MYSQL_TESTS="1"
export MYSQL_TEST_URL=mysql+aiomysql://root:testpassword@127.0.0.1:3307/realestate_test
pytest tests/integration -v
```

Unit tests use in-memory SQLite and do not require MySQL/Stripe/Google.

Frontend build check:

```bash
cd frontend
npm install
npm run build
```

## API overview

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/auth/google`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Properties | `GET/POST /api/properties`, `GET /api/properties/my`, `GET/PUT/DELETE /api/properties/{id}`, search routes |
| Bookings | `POST/GET /api/bookings`, `GET /api/bookings/owner`, `PUT /api/bookings/{id}/status` |
| Payments | `POST /api/payments/create-checkout`, `GET /api/payments/status/{id}`, `POST /api/webhook/stripe` |
| Messages | `GET /api/conversations`, `GET /api/conversations/{id}/messages`, `POST /api/messages` |
| Insights | `POST /api/ai/estimate-price`, `GET /api/ai/recommendations`, `/api/analytics/*` |

## Deployment notes

- Set `ENVIRONMENT=production`, a strong `JWT_SECRET`, and explicit `CORS_ORIGINS`.
- Run `alembic upgrade head` before serving traffic.
- Serve the React `build/` via CDN/static host; point `REACT_APP_BACKEND_URL` at the API.
- Configure Stripe webhook endpoint to `/api/webhook/stripe`.
- Do not enable API docs in production (disabled automatically when `ENVIRONMENT=production`).
- Rotate any credentials that were ever committed historically (see security notes below).

## Security notes / credential rotation

Tracked sample env files previously contained placeholder values such as `sk_test_emergent` and `yourpassword` — treat them as **non-production placeholders**. If you ever put real Stripe/Google/DB/JWT secrets into git history, **rotate them immediately** in the provider dashboards and purge history if needed.

## Known limitations

- No file upload/attachment storage for chat
- Profile phone edits are local/Google-synced only (no dedicated profile PATCH persistence UI path beyond Google fields)
- Geospatial search is limited to address text + stored lat/lng (no PostGIS)
- Price estimator and recommendations are similarity/heuristic-based, **not trained ML models**
- MySQL integration tests require Docker locally (`RUN_MYSQL_TESTS=1`); CI runs them via GitHub Actions service container

## Portfolio status

Verified (Aug 2026):

| Check | Command / source | Result |
|-------|------------------|--------|
| Backend unit tests | `pytest tests -v -m "not integration"` | 42 passed |
| Alembic clean DB | `alembic upgrade head` | Success |
| Frontend build | `npm run build` | Success |
| MySQL integration | GitHub Actions `backend-mysql` job | Success |
| Full CI | push to `main` | Success |

**Status: FINISHED — PORTFOLIO READY**

## License

MIT
