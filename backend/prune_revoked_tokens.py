"""Remove token-revocation records after the token's original expiry.

Run periodically using a scheduler in a trusted backend environment.
Never execute against a production database without backups and monitoring.
"""
import time
from sqlalchemy import delete
from app.main import RevokedToken, SessionLocal


def main():
    with SessionLocal() as db:
        result = db.execute(
            delete(RevokedToken).where(RevokedToken.expires_at_epoch < int(time.time()))
        )
        count = result.rowcount
        db.commit()
    print(f"Expired revoked-token records removed: {count}")


if __name__ == "__main__":
    main()
