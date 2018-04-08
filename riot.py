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
    _confirm_url = 'lol/platform/v3/third-party-code/by-summoner'

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
        self._api_key = ""
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
    def confirm_url(region):
        if RiotAPI.has_region(region):
            league_region = RiotAPI._regions[region]['league']
            return RiotAPI._confirm_url.format(league_region)
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
                self.logger.error('Key is not set, ignoring request \'%s\'', request_url)
                return content
            url = RiotAPI.base_url(region) + request_url + self.riot_key_request
            self.logger.debug('Sending request to: \'%s\'', url)
            content = urllib.request.urlopen(url).read().decode()
            return content, None
        except urllib.error.HTTPError as e:
            self.logger.error('Error while sending request to RiotAPI: %s', e)
            return None, e.code

    def get_summoner_data(self, region, user_id=None, nickname=None):
        if user_id:
            api_url = '{0}{1}'.format(RiotAPI.summoner_url(region), user_id)
        elif nickname:
            encoded_nickname = urllib.parse.quote(nickname.lower())
            api_url = '{0}by-name/{1}'.format(RiotAPI.summoner_url(region), encoded_nickname)
        else:
            raise Exception('No user id or nickname provided for RiotAPI')

        user_content, error_code = self.send_request(api_url, region)
        if user_content is None:
            self.logger.info('Couldn\'t find user by \'{0}\' or id \'{1}\''.format(nickname, user_id).encode('utf-8'))
            if error_code == 404:
                raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname {0}'.format(nickname))
            else:
                raise RiotAPI.RiotRequestException('Unknown request response error: {0}'.format(error_code), error_code)

        user_data_json = json.loads(user_content)
        return user_data_json['id'], user_data_json['name'].strip()

    def get_user_info(self, region, user_id=None, nickname=None):
        self.logger.debug('Getting user elo for \'{0}\''.format(nickname).encode('utf-8'))
        real_id, real_name = self.get_summoner_data(region, user_id=user_id, nickname=nickname)

        best_rank = 'unranked'
        url = '{0}positions/by-summoner/{1}'.format(RiotAPI.league_url(region), real_id)
        ranks_content, error_code = self.send_request(url, region)
        if not ranks_content:
            raise RiotAPI.RiotRequestException('Error while getting leagues data for {0}: {1}'
                                               .format(real_name, error_code), error_code)

        best_rank_id = RiotAPI.ranks[best_rank]

        ranks_data = json.loads(ranks_content)
        # game_modes = ranks_data[user_id_str]
        for mode in ranks_data:
            queue = mode['queueType']
            if queue != 'RANKED_SOLO_5x5' and queue != 'RANKED_FLEX_SR':
                continue
            rank = mode['tier'].lower()
            rank_id = RiotAPI.ranks[rank]
            if rank_id > best_rank_id:
                best_rank = rank
                best_rank_id = rank_id
        return best_rank, real_id, real_name

    def check_user_verification(self, summoner_id, required_code, region):
        required_code = required_code.strip()
        url = '{0}/{1}'.format(RiotAPI.confirm_url(region), summoner_id)
        response, error_code = self.send_request(url, region)
        if error_code:
            return False, 'Error: {0}'.format(error_code)
        else:
            response_code = response[1:-1].strip()
            return response_code == required_code, response_code

    class UserIdNotFoundException(Exception):
        pass

    class RiotRequestException(Exception):
        def __init__(self, message, code):
            super(RiotAPI.RiotRequestException, self).__init__(message)
            self.error_code = code
