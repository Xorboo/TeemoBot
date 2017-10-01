import os
import logging
from hashlib import md5
import jsonpickle
from riot import RiotAPI


class Users:
    logger = logging.getLogger(__name__)

    salt = 'some_salt'
    file_name = 'users.json'

    def __init__(self, data_folder):
        self.data = ServersData([])
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
                self.data = jsonpickle.decode(file_contents)
                self.logger.info('Loaded %s servers, total %s users.', self.data.total_servers, self.data.total_users)
            else:
                self.logger.warning('No data was loaded from \'%s\'', self.full_path)
        except IOError as e:
            self.logger.warning('Couldn\'t open users file, nothing loaded, error: \'%s\'', e)

    def save_users(self):
        self.logger.info('Saving users data to file \'%s\'', self.full_path)
        f = open(self.full_path, 'w')
        file_contents = jsonpickle.encode(self.data)
        f.write(file_contents)
        f.close()

    def get_user(self, member):
        server = self.data.get_or_create_server(member.server.id)
        return server.get_user(member.id)

    def remove_user(self, member):
        server = self.data.get_or_create_server(member.server.id)
        server.remove_user(member.id)
        self.save_users()

    def get_or_create_user(self, member):
        server = self.data.get_or_create_server(member.server.id)
        return server.get_or_create_user(member.id)

    def update_user(self, user, game_user_id, nickname, rank):
        user.game_id = game_user_id
        user.nickname = nickname
        user.rank = rank
        self.save_users()

    def confirm_user(self, user, server):
        user.confirmed = True
        unconfirmed_users = server.remove_unconfirmed_users(user)
        self.save_users()
        return unconfirmed_users

    def get_or_create_server(self, server_id):
        return self.data.get_or_create_server(server_id)

    def set_server_region(self, server_id, region):
        self.logger.info('Setting region \'%s\' for server \'%s\'', region, server_id)

        server = self.get_or_create_server(server_id)
        if server.parameters.set_region(region):
            self.save_users()
            self.logger.info('Region success')
            return True
        else:
            self.logger.info('Region failure')
            return False


class ServersData(object):
    def __init__(self, servers=[]):
        self.servers = servers

    def has_server(self, server_id):
        return self.get_server(server_id) is not None

    def get_or_create_server(self, server_id):
        server = self.get_server(server_id)
        # We can fix None fields this way, because jsonpickle does not call the constructor at all
        if server is None:
            server = self.create_server(server_id)
        return server

    def get_server(self, server_id):
        server = next((s for s in self.servers if s.server_id == server_id), None)
        if server and not server.parameters:
            server.parameters = ServerParameters()
        return server

    def create_server(self, server_id):
        server = ServerData(server_id)
        self.servers.append(server)
        return server

    @property
    def total_servers(self):
        return len(self.servers)

    @property
    def total_users(self):
        return sum(s.total_users for s in self.servers)


class ServerData(object):
    def __init__(self, server_id, users=[], parameters=None):
        Users.logger.info('Creating server \'%s\' with %s users', server_id, len(users))
        self.server_id = server_id
        self.users = users
        if not parameters:
            parameters = ServerParameters()
        self.parameters = parameters

    def has_user(self, discord_id):
        return self.get_user(discord_id) is not None

    def get_or_create_user(self, discord_id):
        user = self.get_user(discord_id)
        if user is None:
            user = self.create_user(discord_id)
        return user

    def get_user(self, discord_id):
        return next((u for u in self.users if u.discord_id == discord_id), None)

    def remove_user(self, discord_id):
        user = self.get_user(discord_id)
        if user:
            self.users.remove(user)

    def create_user(self, discord_id):
        user = UserData(discord_id)
        self.users.append(user)
        return user

    def find_confirmed_user(self, game_id):
        for u in self.users:
            if u.is_confirmed and u.game_id == game_id:
                return u
        return None

    def remove_unconfirmed_users(self, user):
        user_discord_ids = []
        new_users_list = []

        for u in self.users:
            have_to_delete = False
            if u != user:
                if u.game_id:
                    if u.game_id == user.game_id:
                        have_to_delete = True
                elif u.nickname == user.nickname:
                    have_to_delete = True

            if have_to_delete:
                user_discord_ids.append(u.discord_id)
            else:
                new_users_list.append(u)

        # Thats so un-optimal, i can't even...
        self.users = new_users_list
        return user_discord_ids

    @property
    def total_users(self):
        return len(self.users)


class UserData(object):
    def __init__(self, discord_id, rank='', game_id='', nickname='', confirmed=False):
        # Users.logger.info('Creating user \'%s\' with nickname \'%s\'', discord_id, nickname)
        self.discord_id = discord_id
        self.rank = rank
        self.game_id = game_id
        self.nickname = nickname
        self.confirmed = confirmed

    @property
    def is_confirmed(self):
        if not hasattr(self, 'confirmed'):
            self.confirmed = False
        return self.confirmed

    @property
    def bind_hash(self):
        data = '{0}{1}{2}'.format(self.game_id, Users.salt, self.discord_id)
        m = md5()
        m.update(data.encode('utf-8'))
        bind_hash = m.hexdigest()
        return bind_hash[:10]

    @property
    def has_data(self):
        return self.game_id or self.nickname


class ServerParameters(object):
    def __init__(self, language='eng', is_salty=True, region='euw'):
        self.language = language
        self.is_salty = is_salty
        self.region = region

    def get_region(self):
        if not hasattr(self, 'region'):
            self.region = 'euw'
        return self.region

    def set_region(self, region):
        region = region.lower().strip()
        if RiotAPI.has_region(region):
            self.region = region
            return True
        else:
            return False
