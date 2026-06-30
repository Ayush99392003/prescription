"""Central logging configuration using RichHandler.
"""

from __future__ import annotations

import logging
from rich.logging import RichHandler


def setup_logger() -> logging.Logger:
    """Configure and return the centralized Rich logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    return logging.getLogger("prescription")


logger = setup_logger()
