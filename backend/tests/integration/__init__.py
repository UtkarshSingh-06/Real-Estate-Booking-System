"""MySQL integration tests — run with docker compose and RUN_MYSQL_TESTS=1."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

RUN_MYSQL = os.environ.get("RUN_MYSQL_TESTS", "").lower() in ("1", "true", "yes")

skip_unless_mysql = pytest.mark.skipif(
    not RUN_MYSQL,
    reason="Set RUN_MYSQL_TESTS=1 and start docker-compose.test.yml MySQL",
)
