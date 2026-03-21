"""
logging_config.py
-----------------
Centralised logging setup.  Call configure() once from main.py.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """
    Configure the root logger.

    Parameters
    ----------
    level    : str   Logging level name (DEBUG, INFO, WARNING, ERROR).
    log_file : path  Optional file path for a rotating log file.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)-8s %(name)s – %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        from logging.handlers import RotatingFileHandler
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
        )

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )
    logging.getLogger("vtkmodules").setLevel(logging.WARNING)
    logging.getLogger("nibabel").setLevel(logging.WARNING)
    logging.getLogger("pydicom").setLevel(logging.WARNING)