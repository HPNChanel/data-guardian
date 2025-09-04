
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOGGER_NAME = "data_guardian"
_DEFAULT_LEVEL = logging.INFO

def _ensure_log_dir() -> Path:
    #* Save log at ~/.data_guardian/logs
    base = Path.home() / ".data_guardian" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_logger(name: str = _LOGGER_NAME, level: int = _DEFAULT_LEVEL) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  #* Configured

    # Env override
    level_name = os.getenv("DG_LOG_LEVEL")
    if level_name:
        level = getattr(logging, level_name.upper(), level)

    logger.setLevel(level)
    logger.propagate = False
    
    log_dir = _ensure_log_dir()
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s")
    file_handler.setFormatter(fmt)
    stream_handler.setFormatter(fmt)
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logger

log = get_logger() 
