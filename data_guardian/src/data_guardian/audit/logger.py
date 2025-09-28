
import json
import logging
import os
import sys
from datetime import datetime, timezone

from ..utils.config import CONFIG

_LOGGER_NAME = "data_guardian"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        for field in ("op", "path", "status", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    level_name = os.getenv("DG_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.propagate = False
    
    handler = logging.StreamHandler(sys.stdout)
    if CONFIG.audit.json_stdout:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s"))
    logger.addHandler(handler)
    return logger
