import logging
import time
from concurrent.futures import ThreadPoolExecutor
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.workers.runtime import claim,run_job,context,sweep_timeouts


def run_import(batch_id):
    from app.workers.handlers.imports import process_import
    with SessionLocal() as db:
        process_import(context(db),batch_id)


def main():
    logging.basicConfig(level=logging.INFO)
    active={};last_sweep=0
    with ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            try:
                for key,future in list(active.items()):
                    if future.done():
                        if future.exception(): logging.error('Worker failed: %s',type(future.exception()).__name__)
                        del active[key]
                if time.monotonic()-last_sweep>30:
                    with SessionLocal.begin() as db:sweep_timeouts(context(db))
                    last_sweep=time.monotonic()
                if len(active)<8:
                    claimed=claim()
                    if claimed: active[claimed[0]]=pool.submit(run_job,*claimed)
                if len(active)<8:
                    with SessionLocal() as db:
                        batches=context(db).repo.list('ImportBatch',{'status':['validating','committing']},limit=8)
                    for batch in batches:
                        if batch['id'] not in active and len(active)<8:
                            active[batch['id']]=pool.submit(run_import,batch['id'])
            except Exception as exc:
                logging.error('Worker loop error: %s',type(exc).__name__)
            time.sleep(get_settings().worker_poll_seconds)

if __name__=='__main__':main()
