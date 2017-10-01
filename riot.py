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
    _runes_url = 'lol/platform/v3/runes/'

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

    @staticmethod
    def runes_url(region):
        if RiotAPI.has_region(region):
            league_region = RiotAPI._regions[region]['league']
            return RiotAPI._runes_url.format(league_region)
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

    def get_summoner_data(self, region, user_id=None, nickname=None):
        if user_id:
            api_url = RiotAPI.summoner_url(region) + 'by-name/' + urllib.parse.quote(nickname)
        elif nickname:
            encoded_nickname = urllib.parse.quote(nickname.lower())
            api_url = '{0}by-name/{1}'.format(RiotAPI.summoner_url(region), encoded_nickname)
        else:
            raise Exception('No user id or nickname provided for RiotAPI')

        user_content = self.send_request(api_url, region)
        if user_content is None:
            self.logger.info('Couldn\'t find user by \'{0}\' or id \'{1}\''.format(nickname, user_id).encode('utf-8'))
            raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname {0}'.format(nickname))

        user_data_json = json.loads(user_content)
        return user_data_json['id'], user_data_json['name'].strip()

    def get_user_info(self, region, user_id=None, nickname=None):
        self.logger.info('Getting user elo for \'{0}\''.format(nickname).encode('utf-8'))
        real_id, real_name = self.get_summoner_data(region, user_id=user_id, nickname=nickname)

        best_rank = 'unranked'
        url = '{0}positions/by-summoner/{1}'.format(RiotAPI.league_url(region), real_id)
        ranks_content = self.send_request(url, region)
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
        return best_rank, real_id, real_name

    def check_user_runepage(self, summoner_id, page_name, region):
        page_name = page_name.strip()
        url = '{0}by-summoner/{1}'.format(RiotAPI.runes_url(region), summoner_id)
        runepages_response = self.send_request(url, region)
        runepages = json.loads(runepages_response)['pages']
        for runepage in runepages:
            if runepage['name'].strip() == page_name:
                return True
        return False

    class UserIdNotFoundException(Exception):
        pass
