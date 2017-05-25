import urllib.request
import urllib.error
from urllib.parse import quote
import json
import os


class RiotAPI:
    ranks = {
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
        file_contents = ''
        try:
            f = open(key_full_path, 'r')
            self.riot_api_key = f.read()
            f.close()
            print('Riot API key loaded: ' + self.riot_api_key)
        except IOError as e:
            print('ERROR: Couldn\'t open riot api key file, create file with the api key: ' + key_full_path)
            print(e)

    def send_request(self, text):
        content = None
        try:
            if not self.key_is_valid:
                print('Key is not set');
                return  content
            url = RiotAPI.base_url + text + self.riot_key_request
            print('Request URL: ' + url)
            content = urllib.request.urlopen(url).read().decode()
        except urllib.error.HTTPError as e:
            print(e)
        return content

    def get_user_id(self, nickname):
        nickname = nickname.lower()
        user_content = self.send_request(RiotAPI.summoner_url + 'by-name/' + urllib.parse.quote(nickname))
        if user_content is None:
            print('Couldn\'t find user ' + nickname)
            raise RiotAPI.UserIdNotFoundException('Couldn\'t find a username with nickname {0}'.format(nickname))

        user_data_json = json.loads(user_content)
        return user_data_json['id'], user_data_json['name']

    def get_user_elo(self, nickname):
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
            print('User requested master+, putting him to bronze')
            best_rank = 'bronze'
        return best_rank, user_id, real_name

    class UserIdNotFoundException(Exception):
        pass
