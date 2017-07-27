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

    _base_url = 'https://{0}.api.riotgames.com/'
    _summoner_url = 'lol/summoner/v3/summoners/'
    _league_url = 'lol/league/v3/'

    allowed_regions = 'euw | eune | na | ru | kr | br | oce | jp | tr | lan | las'
    _regions = {
        'euw': {'base': 'euw1', 'league': 'euw'},
        'eune': {'base': 'eun1', 'league': 'eune'},
        'na': {'base': 'na1', 'league': 'na'},
        'ru': {'base': 'ru', 'league': 'ru'},
        'kr': {'base': 'kr', 'league': 'kr'},
        'br': {'base': 'br1', 'league': 'br'},
        'oce': {'base': 'oc1', 'league': 'oce'},
        'jp': {'base': 'jp1', 'league': 'jp'},
        'tr': {'base': 'tr1', 'league': 'tr'},
        'lan': {'base': 'la1', 'league': 'lan'},
        'las': {'base': 'la2', 'league': 'las'}
    }

    def __init__(self, riot_key):
        self.api_key = riot_key
        # self.load_key(data_folder)

    @staticmethod
    def has_region(region):
        return region in RiotAPI._regions

    @staticmethod
    def base_url(region):
        if RiotAPI.has_region(region):
            base_region = RiotAPI._regions[region]['base']
            return RiotAPI._base_url.format(base_region)
        else:
            RiotAPI.logger.error('Requested unknown region for base_url: \'%s\'', region)
            return ''

    @staticmethod
    def summoner_url(_):
        return RiotAPI._summoner_url

    @staticmethod
    def league_url(region):
        if RiotAPI.has_region(region):
            league_region = RiotAPI._regions[region]['league']
            return RiotAPI._league_url.format(league_region)
        else:
            RiotAPI.logger.error('Requested unknown region for league_url: \'%s\'', region)
            return ''

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        self._api_key = value
        self.logger.info('Riot API key loaded: \'%s\'', value)

    @property
    def riot_key_request(self):
        return '?api_key=' + self._api_key

    @property
    def key_is_valid(self):
        return bool(self._api_key)

    def load_key(self, data_folder):
        key_full_path = os.path.join(data_folder, RiotAPI.key_file_name)
        self.logger.info('Loading RiotAPI key from \'%s\'', key_full_path)
        try:
            f = open(key_full_path, 'r')
            self._api_key = f.read()
            f.close()
            self.logger.info('Riot API key loaded: \'%s\'', self._api_key)
        except IOError as e:
            self.logger.error('Couldn\'t open riot api key file, create file with the api key in \'%s\'. Error: \'%s\'',
                              key_full_path, e)

    def send_request(self, request_url, region):
        content = None
        try:
            if not self.key_is_valid:
                self.logger.error('Key is not set, ignoring request \'%s\'', request_url);
                return content
            url = RiotAPI.base_url(region) + request_url + self.riot_key_request
            self.logger.info('Sending request to: \'%s\'', url)
            content = urllib.request.urlopen(url).read().decode()
        except urllib.error.HTTPError as e:
            self.logger.error('Error while sending request to RiotAPI: %s', e)
        return content

    def get_user_id(self, nickname, region):
        nickname = nickname.lower()
        user_id_url = RiotAPI.summoner_url(region) + 'by-name/' + urllib.parse.quote(nickname)
        user_content = self.send_request(user_id_url, region)
        if user_content is None:
            self.logger.info('Couldn\'t find user \'{0}\''.format(nickname).encode('utf-8'))
            raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname {0}'.format(nickname))

        user_data_json = json.loads(user_content)
        return user_data_json['id'], user_data_json['name'].strip()

    def get_user_elo(self, nickname, region):
        self.logger.info('Getting user elo for \'{0}\''.format(nickname).encode('utf-8'))
        user_id, real_name = self.get_user_id(nickname, region)
        user_id_str = str(user_id)

        best_rank = 'unranked'
        ranks_content = self.send_request(RiotAPI.league_url(region) + 'positions/by-summoner/' + user_id_str, region)
        if ranks_content:
            best_rank_id = RiotAPI.ranks[best_rank]

            ranks_data = json.loads(ranks_content)
            # game_modes = ranks_data[user_id_str]
            for mode in ranks_data:
                rank = mode['tier'].lower()
                rank_id = RiotAPI.ranks[rank]
                if rank_id > best_rank_id:
                    best_rank = rank
                    best_rank_id = rank_id

        if best_rank == 'master' or best_rank == 'challenger':
            self.logger.info('User requested master+ using nickname \'{0}\', putting him to bronze'
                             .format(nickname).encode('utf-8'))
            best_rank = 'bronze'
        return best_rank, user_id, real_name

    class UserIdNotFoundException(Exception):
        pass
