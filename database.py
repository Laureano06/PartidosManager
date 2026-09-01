import os
from typing import AsyncGenerator
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

RAW_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/soccer_db")

connect_args = {}

if RAW_DATABASE_URL.startswith("sqlite"):
    DATABASE_URL = RAW_DATABASE_URL
    connect_args = {"check_same_thread": False}
else:
    # asyncpg no entiende 'sslmode' ni 'channel_binding' (son sintaxis de
    # psycopg2/libpq). Los sacamos de la URL y el SSL se lo pasamos aparte
    # como connect_args, que es como asyncpg lo espera.
    parts = urlsplit(RAW_DATABASE_URL)
    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query)
        if k not in ("sslmode", "channel_binding")
    ]
    DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment))
    connect_args = {"ssl": "require"}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()