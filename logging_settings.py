import sys
import os
import logging
from logging.config import fileConfig

logging.config.fileConfig('logging_config.ini', defaults={'logfilename': 'bot_log.log'})