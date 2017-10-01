from logging_settings import logging
import sys
from elo_bot import EloBot
# from users_c import UsersC


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    logger.info('========================================================')
    logger.info('Bot starting...')

    data_folder = sys.argv[1]
    logger.info('Selected data folder: %s', data_folder)

    # users = UsersC(data_folder)
    # if False:

    b = EloBot(data_folder)
    if b.all_tokens_are_valid:
        b.run()
    else:
        logger.error('Not all tokens are loader properly, quitting. Used data folder: \'%s\'', data_folder)

    # This shouldn't be called
        logger.info('Bot finishing...')
        logger.info('=========================================================================')