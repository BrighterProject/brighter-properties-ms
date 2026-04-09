import os

db_url = os.environ.get("DB_URL", "sqlite://:memory:")
users_ms_url = os.environ.get("USERS_MS_URL", "http://localhost:8000")
bookings_ms_url = os.environ.get("BOOKINGS_MS_URL", "http://localhost:8002")
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
