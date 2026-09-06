"""Private JSON-only RQ queue for bounded document processing."""

import os

REDIS_URL = os.environ["REDIS_URL"]
QUEUES = ["fillable"]
