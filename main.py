import logging
import logging_settings
import sys
from euw_bot import EuwBot


if __name__ == "__main__":
    logging.info('========================================================')
    logging.info('Bot starting...')

    data_folder = sys.argv[1]
    logging.info('Selected data folder: ' + data_folder)

    b = EuwBot(data_folder)
    if b.all_tokens_are_valid:
        b.run()
    else:
        logging.error('Not all tokens are loader properly, quitting. Used data folder: \'%s\'', data_folder)

    # This shouldn't be called
    logging.info('Bot finishing...')
    logging.info('=========================================================================')