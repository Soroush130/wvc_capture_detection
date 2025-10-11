import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'True').lower() == 'true'
LOG_DIR = os.getenv('LOG_DIR', 'logs')


def setup_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # File
    if LOG_TO_FILE:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(LOG_DIR, f'app_{today}.log')

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    return setup_logger(name)