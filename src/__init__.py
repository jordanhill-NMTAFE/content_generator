# This file makes the src directory a Python package

# Set up logging configuration automatically when package is imported
import logging
from logging.handlers import TimedRotatingFileHandler
from os import environ as env

# Only configure logging if it hasn't been configured already
if not logging.getLogger().handlers:
    # Get log level from environment variable, default to INFO if not set
    log_level = env.get("LOG_LEVEL", "INFO")

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
