"""Start the audits queue, including native Windows spawn support."""

import os

from rq import SpawnWorker, Worker

from app.core.events import redis_client
from app.core.db import init_db


if __name__ == "__main__":
    init_db()
    worker_class = SpawnWorker if os.name == "nt" else Worker
    worker_class(["audits"], connection=redis_client()).work()
