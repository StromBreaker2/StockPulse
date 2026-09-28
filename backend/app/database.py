import os
import sys
import socket
import logging
import subprocess
import time
from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy models
Base = declarative_base()

def is_tcp_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def ensure_neon_proxy_if_needed(host: str, port: int = 5432) -> bool:
    """If corporate firewall blocks outbound port 5432, automatically start local WebSocket bridge."""
    if "neon.tech" not in host:
        return False

    # First check if direct connection to Neon on port 5432 succeeds
    if is_tcp_port_open(host, port, timeout=1.5):
        return False  # Direct connection works

    logger.info("Direct TCP port 5432 to Neon is firewalled. Launching local Neon WebSocket proxy...")

    # Check if local proxy is already listening
    if is_tcp_port_open("127.0.0.1", 5432, timeout=0.5):
        return True

    # Start node neon_proxy.js in background
    proxy_script = os.path.join(os.path.dirname(__file__), "neon_proxy.js")
    if os.path.exists(proxy_script):
        try:
            subprocess.Popen(
                ["node", proxy_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            # Wait for local proxy to start
            for _ in range(10):
                time.sleep(0.3)
                if is_tcp_port_open("127.0.0.1", 5432, timeout=0.5):
                    logger.info("Neon WebSocket proxy established on 127.0.0.1:5432")
                    return True
        except Exception as e:
            logger.warning(f"Could not launch automated Neon proxy: {e}")

    return False

def get_database_url() -> str:
    raw_url = settings.database_url.strip() if getattr(settings, "database_url", None) else os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        return "sqlite:///:memory:"

    # Normalize scheme
    if raw_url.startswith("postgres://"):
        norm_url = "postgresql+psycopg://" + raw_url[len("postgres://"):]
    elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
        norm_url = "postgresql+psycopg://" + raw_url[len("postgresql://"):]
    else:
        norm_url = raw_url

    parsed = urlparse(norm_url)
    remote_host = parsed.hostname or ""

    # Check if corporate firewall requires tunneling to Neon
    if "neon.tech" in remote_host:
        proxied = ensure_neon_proxy_if_needed(remote_host, parsed.port or 5432)
        if proxied:
            user_pass = f"{parsed.username}:{parsed.password}@" if parsed.username else ""
            new_netloc = f"{user_pass}127.0.0.1:5432"
            # Strip query params like sslmode=require and channel_binding since outer WSS tunnel handles TLS
            return urlunparse((parsed.scheme, new_netloc, parsed.path, "", "sslmode=disable", ""))

    return norm_url

def create_db_engine():
    db_url = get_database_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        db_url,
        echo=False,  # Never print database queries or credentials
        pool_pre_ping=True if not db_url.startswith("sqlite") else False,
        connect_args=connect_args
    )

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """FastAPI dependency to yield database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()