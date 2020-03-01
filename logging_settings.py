import os
import logging
from logging.config import fileConfig


base_dir_path = os.path.dirname(os.path.realpath(__file__))
logging_path = base_dir_path + '/logging_config.ini'
log_file_name = base_dir_path + '/bot_log.log'
logging.config.fileConfig(logging_path, defaults={'logfilename': log_file_name})