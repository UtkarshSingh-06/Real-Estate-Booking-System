# MySQL setup (SQLAlchemy async)

1. Install MySQL 8+ or run:
   `docker run --name mysql-realestate -e MYSQL_ROOT_PASSWORD=yourpassword -e MYSQL_DATABASE=realestate_db -p 3306:3306 -d mysql:8.0`

2. Copy `backend/.env.example` to `backend/.env` and set `DB_*` (or `DATABASE_URL`).

3. Install deps and migrate:
   ```bash
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   ```

4. Start:
   `uvicorn server:socket_app --host 0.0.0.0 --port 8001`

Tables are also created on startup via `init_db()` for local convenience; prefer Alembic in shared/staging/production environments.

See the root README for full architecture, auth, Stripe, and Socket.IO notes.
