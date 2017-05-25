import json
import os


class Users:
    file_name = 'users.json'

    def __init__(self, data_folder):
        self.users = []
        self.full_path = os.path.join(data_folder, Users.file_name)
        self.load_users(data_folder)

    def load_users(self, data_folder):
        file_contents = ''
        try:
            f = open(self.full_path, 'r')
            file_contents = f.read()
            f.close()
            print('Users data loaded from ' + self.full_path)
            if file_contents:
                self.users = json.loads(file_contents)
                print('Loaded {0} users.'.format(len(self.users)))
        except IOError as e:
            print('WARNING: Couldn\'t open users file, nothing loaded!')
            print(e)

    def get_user(self, member):
        user_id = member.id
        server_id = member.server.id
        user = next((u for u in self.users if u['discord_uID'] == user_id and u['discord_sID'] == server_id), None)
        return user

    def add_user(self, member, game_user_id, nickname, rank):
        if self.users is None:
            self.users = {}

        user = self.get_user(member)
        if user is None:
            user = {
                'discord_uID': member.id,
                'discord_sID': member.server.id
            }
            self.users.append(user)
        user['game_id'] = game_user_id
        user['nickname'] = nickname
        user['rank'] = rank

        self.save_users()

    def save_users(self):
        f = open(self.full_path, 'w')
        file_contents = json.dumps(self.users)
        f.write(file_contents)
        f.close()
