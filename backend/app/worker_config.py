"""RQ configuration. Business jobs arrive with document processing."""

import os

REDIS_URL = os.environ["REDIS_URL"]
QUEUES = ["fillable"]
