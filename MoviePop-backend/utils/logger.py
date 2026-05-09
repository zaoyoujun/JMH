import logging
import sys
from pathlib import Path


def setup_logger(name="popcorn_player", include_file_handler=True):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    logger.addHandler(console_handler)
    if include_file_handler:
        from config.app_config import AppConfig
        config = AppConfig()
        log_file = config.DATA_DIR / "app.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    return logger


logger = None


def get_logger():
    global logger
    if logger is None:
        logger = setup_logger()
    return logger


def release_logger_handlers(name="popcorn_player"):
    target = logging.getLogger(name)
    for handler in list(target.handlers):
        try:
            handler.flush()
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass
        target.removeHandler(handler)
    return target


def reconfigure_logger(name="popcorn_player", include_file_handler=True):
    global logger
    release_logger_handlers(name)
    logger = setup_logger(name, include_file_handler=include_file_handler)
    return logger


logger = get_logger()
