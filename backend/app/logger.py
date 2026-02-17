import logging


# https://alexandra-zaharia.github.io/posts/make-your-own-custom-color-formatter-with-python-logging/
class CustomFormatter(logging.Formatter):
    """Logging colored formatter"""

    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt, datefmt=None):
        super().__init__()
        self.fmt = fmt
        self.datefmt = datefmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset,
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)


# Configure logging
def setup_logger():
    # Create formatters
    fmt = "     %(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Set up handlers
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter(fmt, datefmt))

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers = []

    # Prevent propagation to parent loggers (this fixes the duplicate logs)
    logger.propagate = False

    # Add handlers
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
