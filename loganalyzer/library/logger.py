'''
This is a module constains a custom logger class
'''
import logging


def getCustomLogger(name: str = 'main'):
    formatter = logging.Formatter(
        fmt='%(asctime)s | LOGAI | %(levelname)s | %(module)s | %(message)s')
    logger = logging.getLogger(name)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def setCustomLoggerLevel(logger: logging.Logger, level: str = 'INFO'):
    customLevel = logging.getLevelName(level)
    logger.setLevel(customLevel)
