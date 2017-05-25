import sys
from euw_bot import EuwBot

if __name__ == "__main__":
    print('========================================================')
    print('Bot starting...')

    data_folder = sys.argv[1]
    print('Selected data folder: ' + data_folder)

    b = EuwBot(data_folder)
    if b.all_tokens_are_valid:
        b.run()
    else:
        print('Not all tokens are loader properly, quitting')

    # This shouldn't be called
    print('Bot finishing...')
    print('=========================================================================')