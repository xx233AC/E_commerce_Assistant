"""Read-only dependency checks; never prints passwords, tokens or connection URLs."""
import socket
from urllib.parse import urlsplit

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.storage.minio import client


def main():
    settings = get_settings()
    failed = False
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
        print('PostgreSQL: connected')
    except Exception:
        print('PostgreSQL: unavailable; check PG_HOST, PG_PORT and the SSH tunnel')
        failed = True
    try:
        endpoint = urlsplit('//' + settings.minio_endpoint)
        with socket.create_connection((endpoint.hostname, endpoint.port or (443 if settings.minio_secure else 80)), timeout=3):
            pass
        exists = client().bucket_exists(settings.minio_bucket)
        print('MinIO S3 API: connected; app bucket ' + ('exists' if exists else 'will be created on first upload'))
    except Exception:
        print('MinIO S3 API: unavailable; local setup requires port 19000 -> server 9000, not console 9001')
        failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
