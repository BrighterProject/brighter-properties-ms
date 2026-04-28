import os

db_url = os.environ.get("DB_URL", "sqlite://:memory:")
users_ms_url = os.environ.get("USERS_MS_URL", "http://localhost:8000")
bookings_ms_url = os.environ.get("BOOKINGS_MS_URL", "http://localhost:8002")
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

notifications_ms_url = os.environ.get("NOTIFICATIONS_MS_URL", "http://localhost:8004")
DEFAULT_LOCALE = "bg"

# Cloudflare R2
r2_account_id = os.environ.get("R2_ACCOUNT_ID", "")
r2_access_key_id = os.environ.get("R2_ACCESS_KEY_ID", "")
r2_secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
r2_bucket_name = os.environ.get("R2_BUCKET_NAME", "")
r2_public_url = os.environ.get("R2_PUBLIC_URL", "")
