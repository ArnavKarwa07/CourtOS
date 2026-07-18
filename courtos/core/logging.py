import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Service class.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None)
        }
        
        # Include exception tracebacks if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        # Add extra dictionary items
        if hasattr(record, "details"):
            details = getattr(record, "details")
            if isinstance(details, dict):
                # Redact payload from INFO and WARNING logs
                if record.levelno in (logging.INFO, logging.WARNING) and "payload" in details:
                    details = dict(details)
                    details["payload"] = "[REDACTED]"
                log_entry["details"] = details
                
        return json.dumps(log_entry)

def configure_logging(log_level: str = "info") -> None:
    logger = logging.getLogger("courtos")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    # Silence default uvicorn loggers so structured logs are clean
    logging.getLogger("uvicorn.access").propagate = False
