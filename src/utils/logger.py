import logging
from logging.handlers import TimedRotatingFileHandler
import sys
from os import environ as env

# Get log level from environment variable, default to DEBUG if not set
log_level = getattr(logging, env.get("LOG_LEVEL", "DEBUG"))

logging.basicConfig(
    level=log_level,  # Set logging level from environment
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Set the format for log messages
    handlers=[
        logging.StreamHandler(),  # Console handler
        TimedRotatingFileHandler(  # File handler
            filename="app.log", when="midnight", backupCount=3, encoding="utf-8"
        ),
    ],
)

log = logging.getLogger()
