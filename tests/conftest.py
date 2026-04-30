"""
Root conftest: inject dummy environment variables so pydantic-settings does not
raise a ValidationError during test collection for unit tests that do not need
real credentials.
"""

import os

# These must be set before any src.* module is imported (i.e. before collection)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
os.environ.setdefault("GOOGLE_API_KEY", "fake-api-key-for-unit-tests")
