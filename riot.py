import os
import json
import logging
import urllib.request
import urllib.error
from urllib.parse import quote


class RiotAPI:
    logger = logging.getLogger(__name__)

    initial_rank = 'no elo'
    ranks = {
        initial_rank: -1,
        'unranked': 0,
        'bronze': 1,
        'silver': 2,
        'gold': 3,
        'platinum': 4,
        'diamond': 5,
        'master': 6,
        'challenger': 7,
    }

    key_file_name = 'riot_api_key.txt'
    base_url = 'https://euw1.api.riotgames.com/'
    summoner_url = 'lol/summoner/v3/summoners/'
    league_url = 'api/lol/euw/v2.5/league/'

    def __init__(self, data_folder):
        self.riot_api_key = ''
        self.load_key(data_folder)

    @property
    def riot_key_request(self):
        return '?api_key=' + self.riot_api_key

    @property
    def key_is_valid(self):
        return bool(self.riot_api_key)

    def load_key(self, data_folder):
        key_full_path = os.path.join(data_folder, RiotAPI.key_file_name)
        self.logger.info('Loading RiotAPI key from \'%s\'', key_full_path)
        try:
            f = open(key_full_path, 'r')
            self.riot_api_key = f.read()
            f.close()
            self.logger.info('Riot API key loaded: \'%s\'', self.riot_api_key)
        except IOError as e:
            self.logger.error('Couldn\'t open riot api key file, create file with the api key in \'%s\'. Error: \'%s\'',
                              key_full_path, e)

    def send_request(self, text):
        content = None
        try:
            if not self.key_is_valid:
                self.logger.error('Key is not set, ignoring request \'%s\'', text);
                return content
            url = RiotAPI.base_url + text + self.riot_key_request
            self.logger.info('Sending request to: \'%s\'', url)
            content = urllib.request.urlopen(url).read().decode()
        except urllib.error.HTTPError as e:
            self.logger.error('Error while sending request to RiotAPI: %s', e)
        return content

    def get_user_id(self, nickname):
        nickname = nickname.lower()
        user_content = self.send_request(RiotAPI.summoner_url + 'by-name/' + urllib.parse.quote(nickname))
        if user_content is None:
            self.logger.info('Couldn\'t find user \'%s\'', nickname)
            raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname {0}'.format(nickname))

        user_data_json = json.loads(user_content)
        return user_data_json['id'], user_data_json['name']

    def get_user_elo(self, nickname):
        self.logger.info('Getting user elo for \'%s\'', nickname)
        user_id, real_name = self.get_user_id(nickname)
        user_id_str = str(user_id)

        ranks_content = self.send_request(RiotAPI.league_url + 'by-summoner/' + user_id_str)
        if ranks_content is None:
            return 'unranked', user_id, real_name

        ranks_data = json.loads(ranks_content)

        game_modes = ranks_data[user_id_str]
        best_rank = 'unranked'
        best_rank_id = RiotAPI.ranks[best_rank]
        for mode in game_modes:
            rank = mode['tier'].lower()
            rank_id = RiotAPI.ranks[rank]
            if rank_id > best_rank_id:
                best_rank = rank
                best_rank_id = rank_id

        if best_rank == 'master' or best_rank == 'challenger':
            self.logger.info('User requested master+ using nickname \'%s\', putting him to bronze', nickname)
            best_rank = 'bronze'
        return best_rank, user_id, real_name

    class UserIdNotFoundException(Exception):
        pass
