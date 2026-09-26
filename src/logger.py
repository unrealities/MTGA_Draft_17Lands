import os
import sys
import logging
import logging.handlers


def _get_logger_base_dir():
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return os.path.expanduser("~/Library/Application Support/MTGA_Draft_Tool")
        elif sys.platform == "linux":
            return os.path.expanduser("~/.config/MTGA_Draft_Tool")
        else:
            return os.path.dirname(sys.executable)
    return os.getcwd()


DEBUG_LOG_FOLDER = os.path.join(_get_logger_base_dir(), "Debug")
DEBUG_LOG_FILE = os.path.join(DEBUG_LOG_FOLDER, "debug.log")
DEBUG_LOGGER_NAME = "debug_log"

if not os.path.exists(DEBUG_LOG_FOLDER):
    try:
        os.makedirs(DEBUG_LOG_FOLDER)
    except Exception:
        pass


class CustomFormatter(logging.Formatter):
    """ """

    def __init__(
        self,
        fmt="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="<%m/%d/%Y %H:%M:%S>",
    ):
        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)

    def format(self, record):

        # Remember the original format
        format_orig = self._style._fmt

        if record.levelno == logging.ERROR:
            self._style._fmt = (
                "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s"
            )

        # Calling the original formatter once the style has changed
        result = logging.Formatter.format(self, record)

        # Restore the original format
        self._style._fmt = format_orig

        return result


# Create the shared logger
shared_logger = logging.getLogger(DEBUG_LOGGER_NAME)
shared_logger.setLevel(logging.DEBUG)

# Create a file handler for the shared logger
handlers = {
    logging.handlers.TimedRotatingFileHandler(
        DEBUG_LOG_FILE, when="D", interval=1, backupCount=7, utc=True
    ),
    logging.StreamHandler(sys.stdout),
}

formatter = CustomFormatter()

for handler in handlers:
    handler.setFormatter(formatter)
    shared_logger.addHandler(handler)


def create_logger():
    logger = logging.getLogger(DEBUG_LOGGER_NAME)
    return logger
