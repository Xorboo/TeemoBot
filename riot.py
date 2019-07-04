import os
import json
import logging
import urllib.request
import urllib.error
from urllib.parse import quote
from riotwatcher import RiotWatcher, ApiError


class RiotAPI:
    logger = logging.getLogger(__name__)

    _allowed_queues = ['RANKED_SOLO_5x5', 'RANKED_FLEX_SR']

    unknown_rank = "no elo"
    _lowest_rank = "unranked"
    ranks = {
        unknown_rank: -1,
        _lowest_rank:  0,
        'iron':        1,
        'bronze':      2,
        'silver':      3,
        'gold':        4,
        'platinum':    5,
        'diamond':     6,
        'master':      7,
        'grandmaster': 8,
        'challenger':  9,
    }

    _regions = {
        'euw': 'euw1',
        'eune': 'eun1',
        'na': 'na1',
        'ru': 'ru',
        'kr': 'kr',
        'br': 'br1',
        'oce': 'oc1',
        'jp': 'jp1',
        'tr': 'tr1',
        'lan': 'la1',
        'las': 'la2'
    }
    allowed_regions = ' | '.join(_regions)

    def __init__(self, riot_key):
        self._api_key = ""
        self.api_key = riot_key
        self.watcher = RiotWatcher(riot_key)

    @staticmethod
    def _get_region_base(region):
        return RiotAPI._regions[region]

    @property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, value):
        self._api_key = value
        # TODO Don't log full api key
        self.logger.info('Riot API key loaded: \'%s\'', value)

    @property
    def key_is_valid(self):
        return bool(self._api_key)

    def get_summoner_data(self, region, user_id=None, nickname=None):
        try:
            if nickname:
                nickname = urllib.parse.quote(nickname.lower())

            if user_id:
                # Update older id to a new one
                if len(str(user_id)) < 15:
                    if nickname:
                        user_data = self.watcher.summoner.by_name(RiotAPI._get_region_base(region), nickname)
                    else:
                        raise Exception('No user id or nickname provided for RiotAPI')
                else:
                    user_data = self.watcher.summoner.by_id(RiotAPI._get_region_base(region), user_id)
            elif nickname:
                user_data = self.watcher.summoner.by_name(RiotAPI._get_region_base(region), nickname)
            else:
                raise Exception('No user id or nickname provided for RiotAPI')
            return user_data['id'], user_data['name'].strip()

        except ApiError as exc:
            if exc.response.status_code == 404:
                raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname "{0}"'.format(nickname))
            else:
                self.logger.error('Summoner data \'{0}\' exception:  {0}'.format(nickname, str(exc)).encode('utf-8'))
                raise RiotAPI.RiotRequestException('Unknown request response error: {0}'
                                                   .format(exc.response.status_code), exc.response.status_code)

    def get_user_info(self, region, user_id=None, nickname=None):
        try:
            self.logger.debug('Getting user elo for \'{0}\''.format(nickname).encode('utf-8'))
            encrypted_summoner_id, summoner_name = self.get_summoner_data(region, user_id=user_id, nickname=nickname)
            region = RiotAPI._get_region_base(region)
            summoner_ranks = self.watcher.league.by_summoner(region, encrypted_summoner_id)
            best_rank = RiotAPI._get_best_rank(summoner_ranks)
            return best_rank, encrypted_summoner_id, summoner_name

        except ApiError as exc:
            self.logger.error('User info \'{0}\' exception:  {0}'.format(nickname, str(exc)).encode('utf-8'))
            status_code = exc.response.status_code
            if status_code == 404:
                raise RiotAPI.UserIdNotFoundException()
            else:
                raise RiotAPI.RiotRequestException('Error while getting leagues data for "{0}": {1}'
                                                   .format(summoner_name, status_code), status_code)

    def check_user_verification(self, encrypted_summoner_id, required_code, region):
        try:
            if len(str(encrypted_summoner_id)) < 15:
                self.logger.error('Bad summoner id during verification:  \'{0}\''.format(encrypted_summoner_id))
                return False, "Сначала обнови свой ник командой !nick"
            required_code = required_code.strip()
            region = RiotAPI._get_region_base(region)
            response_code = self.watcher.third_party_code.by_summoner(region, encrypted_summoner_id)
            return response_code == required_code, response_code
        except ApiError as exc:
            if exc.response.status_code == 404:
                return False, "Никакого кода не установлено"
            else:
                self.logger.error('Verification exception:  \'{0}\''.format(str(exc)))
                return False, 'Ошибка: {0}'.format(exc.response.status_code)

    @staticmethod
    def _get_best_rank(summoner_ranks):
        best_rank = RiotAPI._lowest_rank
        best_rank_id = RiotAPI.ranks[best_rank]

        for mode in summoner_ranks:
            if mode['queueType'] not in RiotAPI._allowed_queues:
                continue

            rank = mode['tier'].lower()
            rank_id = RiotAPI.ranks[rank]
            if rank_id > best_rank_id:
                best_rank = rank
                best_rank_id = rank_id
        return best_rank

    class UserIdNotFoundException(Exception):
        pass

    class RiotRequestException(Exception):
        def __init__(self, message, code):
            super(RiotAPI.RiotRequestException, self).__init__(message)
            self.error_code = code
