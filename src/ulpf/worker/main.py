import logging
import signal
import time

from ulpf.db import SessionLocal
from ulpf.worker.processor import JobProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ulpf-worker")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received (%s). Finishing current task...", signum)
    running = False


def run_worker_loop():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    processor = JobProcessor()
    logger.info("Worker started with ID: %s. Awaiting jobs...", processor.worker_id)

    while running:
        db = SessionLocal()
        try:
            job = processor.claim_and_process_next(db)
            if job:
                logger.info(
                    "Processed job %s: status=%s total=%d processed=%d failed=%d",
                    job.id,
                    job.status,
                    job.total_records,
                    job.processed_records,
                    job.failed_records,
                )
            else:
                # No job available, idle sleep
                time.sleep(1.0)
        except Exception as err:
            logger.error("Error during worker execution: %s", err, exc_info=True)
            time.sleep(2.0)
        finally:
            db.close()

    logger.info("Worker gracefully stopped.")


if __name__ == "__main__":
    run_worker_loop()
