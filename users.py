import json
import os


# Сохраненные юзеры, потом будем обновлять их автоматически
saved_users = None

file_name = 'users.json'
full_path = file_name


def load_users(data_folder):
    global full_path
    full_path = os.path.join(data_folder, file_name)
    file_contents = ''
    try:
        f = open(full_path, 'r')
        file_contents = f.read()
        f.close()
        print('Users data loaded from ' + full_path)
    except IOError as e:
        print('WARNING: Couldn\'t open users file, nothing loaded!')
        print(e)

    global saved_users
    if file_contents is not None and file_contents != '':
        saved_users = json.loads(file_contents)
        print('Loaded ' + str(len(saved_users)) + ' users.')
    else:
        saved_users = {}


def add_user(member, nickname, rank):
    global full_path
    global saved_users
    if saved_users is None:
        saved_users = {}

    saved_users[member.id] = {
        'nickname': nickname,
        'rank': rank
    }
    f = open(full_path, 'w')
    file_contents = json.dumps(saved_users)
    f.write(file_contents)
    f.close()

