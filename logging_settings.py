import os
import logging
from logging.config import fileConfig


logging.config.fileConfig(os.path.realpath('logging_config.ini'), defaults={'logfilename': 'bot_log.log'})
