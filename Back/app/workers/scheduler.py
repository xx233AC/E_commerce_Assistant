"""Optional periodic monitor dispatcher; run separately from the API."""
import time
import logging
from app.db.session import SessionLocal
from app.workers.runtime import context

def main():
    while True:
        try:
            from app.services.competitors import process_due_monitors
            with SessionLocal.begin() as db:process_due_monitors(context(db))
        except Exception as exc:logging.error('Monitor schedule error: %s',type(exc).__name__)
        time.sleep(60)

if __name__=='__main__':main()
