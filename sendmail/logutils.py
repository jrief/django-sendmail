import logging
from logging.config import dictConfig


# Taken from https://github.com/nvie/rq/blob/master/rq/logutils.py
def setup_loghandlers(level=None):
    # Setup logging for sendmail if not already configured
    logger = logging.getLogger('sendmail')
    if not logger.handlers:
        dictConfig(
            {
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'sendmail': {
                        'format': '[%(levelname)s]%(asctime)s PID %(process)d: %(message)s',
                        'datefmt': '%Y-%m-%d %H:%M:%S',
                    },
                },
                'handlers': {
                    'sendmail': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'sendmail'},
                },
                'loggers': {'sendmail': {'handlers': ['sendmail'], 'level': level or 'DEBUG'}},
            }
        )
    return logger
