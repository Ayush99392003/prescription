"""
Thread-safe in-memory session store with TTL expiry.
Maps session IDs to live PrescriptionSession objects.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from server.core.session import PrescriptionSession

# TTL: sessions expire after 30 minutes of inactivity
_TTL_SECONDS: int = 1800
_lock = threading.Lock()

# sid -> (session, last_access_timestamp)
_STORE: dict[str, tuple[PrescriptionSession, float]] = {}


def create() -> PrescriptionSession:
    """
    Create a new session, register it, and return it.

    Returns:
        The freshly created PrescriptionSession.
    """
    session = PrescriptionSession()
    with _lock:
        _STORE[session.session_id] = (session, time.time())
        _evict_expired()
    return session


def get(sid: str) -> Optional[PrescriptionSession]:
    """
    Look up a session by ID, refreshing its TTL.

    Args:
        sid: Session identifier string.

    Returns:
        The PrescriptionSession, or None if expired/missing.
    """
    with _lock:
        entry = _STORE.get(sid)
        if entry is None:
            return None
        session, _ = entry
        _STORE[sid] = (session, time.time())
        return session


def _evict_expired() -> None:
    """Remove sessions that have exceeded the TTL (call under lock)."""
    now = time.time()
    expired = [
        sid
        for sid, (_, ts) in _STORE.items()
        if now - ts > _TTL_SECONDS
    ]
    for sid in expired:
        del _STORE[sid]
