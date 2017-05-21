import urllib.request
import urllib.error
from urllib.parse import quote
import json
import os


ranks = {
    'error': -1,
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
key_full_path = ''
riot_api_key = ''
riot_key_request = '?api_key=' + riot_api_key
base_url = 'https://euw1.api.riotgames.com/'
summoner_url = 'lol/summoner/v3/summoners/'
league_url = 'api/lol/euw/v2.5/league/'


def load_key(data_folder):
    global key_full_path, riot_api_key, riot_key_request
    key_full_path = os.path.join(data_folder, key_file_name)
    file_contents = ''
    try:
        f = open(key_full_path, 'r')
        riot_api_key = f.read()
        riot_key_request = '?api_key=' + riot_api_key
        f.close()
        print('Riot API key loaded: ' + riot_api_key)
    except IOError as e:
        print('ERROR: Couldn\'t open riot api key file, create file with the api key: ' + key_full_path)
        print(e)


def send_request(text):
    url = base_url + text + riot_key_request
    print('Request URL: ' + url)
    content = None

    try:
        content = urllib.request.urlopen(url).read().decode()
    except urllib.error.HTTPError as e:
        # print(e.reason)
        print(e)
    # print('Result: ' + str(content))
    return content


def get_user_id(nickname):
    nickname = nickname.lower()
    # url_nickname = nickname.replace(' ', '%20')
    user_content = send_request(summoner_url + 'by-name/' + quote(nickname))
    if user_content is None:
        print('Couldn\'t find user ' + nickname)
        return -1, nickname

    user_data_json = json.loads(user_content)
    return user_data_json['id'], user_data_json['name']


def get_user_elo(nickname):
    user_id, real_name = get_user_id(nickname)
    if user_id == -1:
        return 'error', nickname

    user_id_str = str(user_id)

    ranks_content = send_request(league_url + 'by-summoner/' + user_id_str)
    if ranks_content is None:
        return 'unranked', real_name

    ranks_data = json.loads(ranks_content)

    game_modes = ranks_data[user_id_str]
    best_rank = 'unranked'
    best_rank_id = ranks[best_rank]
    for mode in game_modes:
        rank = mode['tier'].lower()
        rank_id = ranks[rank]
        if rank_id > best_rank_id:
            best_rank = rank
            best_rank_id = rank_id

    if best_rank == 'master' or best_rank == 'challenger':
        best_rank = 'bronze'
    return best_rank, real_name
