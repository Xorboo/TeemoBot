import json
import os
import logging


class Users:
    logger = logging.getLogger(__name__)

    file_name = 'users.json'

    def __init__(self, data_folder):
        self.users = []
        self.full_path = os.path.join(data_folder, Users.file_name)
        self.load_users()

    def load_users(self):
        self.logger.info('Loading users list from \'%s\'', self.full_path)
        try:
            f = open(self.full_path, 'r')
            file_contents = f.read()
            f.close()
            self.logger.info('Users data loaded')
            if file_contents:
                self.users = json.loads(file_contents)
                self.logger.info('Loaded %s users.', len(self.users))
            else:
                self.logger.warning('No data was loaded from \'%s\'', self.full_path)
        except IOError as e:
            self.logger.warning('Couldn\'t open users file, nothing loaded, error: \'%s\'', e)

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
            self.logger.info('Adding new user \'%s\', nickname: \'%s\'', member, nickname)
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
        self.logger.info('Saving users data to file \'%s\'', self.full_path)
        f = open(self.full_path, 'w')
        file_contents = json.dumps(self.users)
        f.write(file_contents)
        f.close()
