# MySQL Database Setup Guide

The backend has been migrated from MongoDB to MySQL. Follow these steps to set up the database.

## Prerequisites

1. **Install MySQL Server**
   - Download from: https://dev.mysql.com/downloads/mysql/
   - Or use Docker: `docker run --name mysql-realestate -e MYSQL_ROOT_PASSWORD=yourpassword -p 3306:3306 -d mysql:8.0`

2. **Create Database**
   ```sql
   CREATE DATABASE realestate_db;
   ```

## Environment Variables

Update your `.env` file with MySQL connection details:

```env
# MySQL Database Configuration
DB_USER=root
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=3306
DB_NAME=realestate_db

# Other existing variables...
JWT_SECRET=your_jwt_secret
STRIPE_API_KEY=your_stripe_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
```

## Installation

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   Key new dependencies:
   - `sqlalchemy==2.0.23` - SQL toolkit and ORM
   - `aiomysql==0.2.0` - Async MySQL driver

2. **Database Tables**
   Tables are automatically created on server startup via the `init_db()` function in `database.py`.

## Running the Server

```bash
python -m uvicorn server:socket_app --host 0.0.0.0 --port 8001
```

The server will automatically create all required tables on first startup.

## Database Schema

The following tables are created:

- **users** - User accounts
- **user_sessions** - JWT session tokens
- **properties** - Real estate listings
- **bookings** - Property viewing bookings
- **conversations** - Message conversations
- **messages** - Individual messages
- **payment_transactions** - Stripe payment records

## Migration Notes

- All MongoDB queries have been converted to SQLAlchemy ORM queries
- JSON fields (amenities, images, participants, metadata) are stored as JSON in MySQL
- All async operations use SQLAlchemy's async session
- Database connection pooling is configured automatically

## Troubleshooting

1. **Connection Error**: Ensure MySQL server is running and credentials are correct
2. **Table Creation Error**: Check MySQL user has CREATE TABLE permissions
3. **JSON Field Issues**: MySQL 5.7+ required for JSON data type support
