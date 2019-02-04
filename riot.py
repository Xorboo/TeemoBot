import os
import json
import logging
import urllib.request
import urllib.error
from urllib.parse import quote
from riotwatcher import RiotWatcher, ApiError


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
        self.watcher = RiotWatcher(riot_key)

    @staticmethod
    def _has_region(region):
        return region in RiotAPI._regions

    @staticmethod
    def _get_region_base(region):
        if RiotAPI._has_region(region):
            return RiotAPI._regions[region]['base']
        else:
            return ""

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        self._api_key = value
        # TODO Dont log full api key
        self.logger.info('Riot API key loaded: \'%s\'', value)

    @property
    def riot_key_request(self):
        return '?api_key=' + self._api_key

    @property
    def key_is_valid(self):
        return bool(self._api_key)

    def get_summoner_data(self, region, user_id=None, nickname=None):
        try:
            if nickname:
                nickname = urllib.parse.quote(nickname.lower())

            if user_id:
                # Update older id to a new one
                if len(str(user_id)) < 15 and nickname:
                    user_data = self.watcher.summoner.by_name(RiotAPI._get_region_base(region), nickname)
                else:
                    user_data = self.watcher.summoner.by_id(RiotAPI._get_region_base(region), nickname)
            elif nickname:
                user_data = self.watcher.summoner.by_name(RiotAPI._get_region_base(region), nickname)
            else:
                raise Exception('No user id or nickname provided for RiotAPI')
            return user_data['id'], user_data['name'].strip()

        except ApiError as exc:
            if exc.response.status_code == 404:
                raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname "{0}"'.format(nickname))
            else:
                raise RiotAPI.RiotRequestException('Unknown request response error: {0}'.format(exc.response.status_code), exc.response.status_code)

    def get_user_info(self, region, user_id=None, nickname=None):
        try:
            self.logger.debug('Getting user elo for \'{0}\''.format(nickname).encode('utf-8'))
            encrypted_summoner_id, summoner_name = self.get_summoner_data(region, user_id=user_id, nickname=nickname)
            region = RiotAPI._get_region_base(region)
            summoner_ranks = self.watcher.league.positions_by_summoner(region, encrypted_summoner_id)
            best_rank = RiotAPI._get_best_rank(summoner_ranks)
            return best_rank, encrypted_summoner_id, summoner_name
        except ApiError as exc:
            status_code = exc.response.status_code
            raise RiotAPI.RiotRequestException('Error while getting leagues data for {0}: {1}'
                                               .format(summoner_name, status_code), status_code)

    @staticmethod
    def _get_best_rank(summoner_ranks):
        best_rank = 'unranked'
        best_rank_id = RiotAPI.ranks[best_rank]

        for mode in summoner_ranks:
            queue = mode['queueType']
            if queue != 'RANKED_SOLO_5x5' and queue != 'RANKED_FLEX_SR':
                continue
            rank = mode['tier'].lower()
            rank_id = RiotAPI.ranks[rank]
            if rank_id > best_rank_id:
                best_rank = rank
                best_rank_id = rank_id
        return best_rank

    def check_user_verification(self, encrypted_summoner_id, required_code, region):
        try:
            required_code = required_code.strip()
            region = RiotAPI._get_region_base(region);
            response_code = self.watcher.third_party_code.by_summoner(region, encrypted_summoner_id)
            return response_code == required_code, response_code
        except ApiError as exc:
            if exc.response.status_code == 404:
                return False, "Никакого кода не установлено"
            else:
                return False, 'Ошибка: {0}'.format(exc.response.status_code)

    class UserIdNotFoundException(Exception):
        pass

    class RiotRequestException(Exception):
        def __init__(self, message, code):
            super(RiotAPI.RiotRequestException, self).__init__(message)
            self.error_code = code
