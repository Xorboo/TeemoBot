import sys
import os
import time

import discord
import asyncio

import riot
import answers
import users

keep_working = True
#client = None

while keep_working:
    try:
        print('========================================================')
        print('START')
        time.sleep(5)
        
        # Роли с ранками. Собираем в отдельный список чтобы удалять их у юзера
        rank_roles = None
        rank_ids = None


        elo_command_hint = '`!nick свой_ник_на_весте`'
        base_command_hint = '`!base основной_ник_в_дискорде`'

        help_text = elo_command_hint + '\n    Установить соответствующий ник и эло для себя\n' + \
                    base_command_hint + '\n    Установить базовый ник в дискорде\n'

        #if client is not None:
        #    client.loop.close()
        #    is_closed = client.is_closed
        #    print(str(is_closed))
        #    print('^^^ closed')
        client = discord.Client()


        def parse_roles(roles):
            global rank_roles
            global rank_ids

            rank_roles = []
            rank_ids = []
            for r in roles:
                role_name = r.name.lower()
                if role_name != 'error' and role_name in riot.ranks:
                    rank_roles.insert(0, r)
                    rank_ids.insert(0, r.id)


        def get_role(roles, role):
            global rank_roles
            for r in rank_roles:
                if r.name.lower() == role:
                    return r
            print('ERROR: can\'t find role ' + role + ' on server')
            return None


        def get_new_roles(user_roles, rank_role):
            global rank_ids
            new_roles = [rank_role]
            for role in user_roles:
                if role.id not in rank_ids:
                    new_roles.insert(0, role)
            return new_roles


        def clean_name(name):
            br_open = name.rfind('(')
            br_close = name.rfind(')')
            br_first = min(br_open, br_close)
            if br_first >= 0:
                return (name[:br_first]).strip()
            return name.strip()


        def get_base_name(member):
            return clean_name(member.display_name)


        def create_nickname(base_name, nickname):
            if len(base_name) > 32:
                base_name = base_name[:32]

            if base_name != nickname:
                base_len = len(base_name)
                total_len = base_len + len(nickname) + 3
                if total_len > 32:
                    overhead = total_len - 32
                    base_name = base_name[:base_len - overhead]
                return base_name + ' (' + nickname + ')'
            return base_name


        def get_user_nickname(member):
            if member.id in users.saved_users:
                user = users.saved_users[member.id]
                return True, user['nickname']
            return False, ''


        def update_nickname(member):
            has_nickname, nickname = get_user_nickname(member)
            if has_nickname:
                base_name = get_base_name(member)
                full_name = create_nickname(base_name, nickname)
                return True, full_name

            print('ERROR: updating name of user without rank data: ' + member.display_name)
            return False, get_base_name(member)


        @client.event
        @asyncio.coroutine
        def on_ready():
            print('------------')
            print('Logged in as: ' + client.user.name + ' (' + client.user.id + ')')
            print('------------')


        @client.event
        @asyncio.coroutine
        def on_member_join(member):
            server = member.server
            fmt = 'Привет {0.mention}! Чтобы установить себе эло, напиши ' + elo_command_hint
            yield from client.send_message(server, fmt.format(member))


        @client.event
        @asyncio.coroutine
        def on_message(message):
            global rank_roles
            parse_roles(message.channel.server.roles)

            text = message.content
            text_lower = text.lower()

            # Смена ника в лиге
            if text_lower.startswith('!nick') or text_lower.startswith('!nickname'):
                space_id = text.find(' ')
                nickname = text[(space_id + 1):]
                if space_id > 0 and nickname is not None and nickname != '':
                    yield from client.send_typing(message.channel)

                    rank, nickname = riot.get_user_elo(nickname)
                    if rank != 'error':
                        role = get_role(message.channel.server.roles, rank)
                        if role is not None:
                            # Сохраняем юзера
                            users.add_user(message.author, nickname, role.name)

                            # Обновляем роль
                            new_roles = get_new_roles(message.author.roles, role)
                            yield from client.replace_roles(message.author, *new_roles)

                            # Обновляем ник
                            remind_nickname = False
                            should_update_name, new_name = update_nickname(message.author)
                            if should_update_name:
                                try:
                                    print('Setting nickname: ' + new_name)
                                    yield from client.change_nickname(message.author, new_name)
                                except discord.errors.Forbidden as e:
                                    print(e)
                                    remind_nickname = True

                            # Отвечаем
                            answer = answers.generate_answer(message.author, role.name)
                            yield from client.send_message(message.channel, answer)

                            if remind_nickname:
                                yield from client.send_message(message.channel, 'А вот ник в скобки поставь себе сам')

                            yield from client.send_message(message.channel, 'Повтори эту команду, когда поменяешь ранк. '
                                                                       'Я пока не умею автообновлять их.')
                        else:
                            yield from client.send_message(message.channel, 'Упс, тут на сервере роли не настроены, '
                                                                       'не получится тебе роль поставить')
                    else:
                        yield from client.send_message(message.channel, 'Не ври, рак, нет такого ника в лиге на весте. '
                                                                   'Ну или риоты API сломали, попробуй попозже.')
                else:
                    yield from client.send_message(message.channel, 'Ничего не понял что ты написал, упрлся что ли. '
                                                               'Пиши ' + elo_command_hint + ' и не выпендривайся.')

            # Смена базового ника
            elif text_lower.startswith('!base'):
                space_id = text.find(' ')
                base_name = text[(space_id + 1):]
                if space_id > 0 and base_name is not None and base_name != '':
                    base_name = clean_name(base_name)
                    if base_name != '':
                        has_nickname, nickname = get_user_nickname(message.author)
                        new_name = base_name
                        if has_nickname:
                            new_name = create_nickname(base_name, nickname)

                        try:
                            print('Setting nickname: ' + new_name)
                            yield from client.change_nickname(message.author, new_name)
                        except discord.errors.Forbidden as e:
                            print(e)
                            yield from client.send_message(message.channel, 'Не могу сменить тебе ник почему-то, попробуй сам.')
                    else:
                        yield from client.send_message(message.channel,
                                                       'Не пойдет. Основной ник должен быть без скобок и не пустой')
                else:
                    yield from client.send_message(message.channel, 'Ничего не понял что ты написал, упрлся что ли. '
                                                                    'Пиши ' + base_command_hint + ' и не выпендривайся.')

            # Вывод помощи
            elif text_lower.rstrip() == '!help':
                yield from client.send_message(message.channel, help_text)

            # Представиться
            elif text_lower.startswith('хомяк, представься'):
                yield from client.send_message(
                    message.channel,
                    'Привет :crab:! '
                    'Я хомяк, я автоматически расставляю эло и ники, '
                    'потому что админам надоело делать это вручную. '
                    'Я пока тестовый и могу чуть что ломаться, аккуратнее. '
                    'Потом меня научат автоматически ранги обновлять. `!help` для всех комманд. Умею:\n' +
                    help_text)


        def load_token(folder):
            token_file_name = 'discord_token.txt'
            token_file_path = os.path.join(folder, token_file_name)
            token = ''
            try:
                with open(token_file_path, 'r') as token_file:
                    token = token_file.read()
                    print('Discord token loaded: ' + token)
            except IOError as e:
                print('ERROR: Couldn\'t open discord token file, create file with the token key: ' + token_file_path)
                print(e)
            return token


        data_folder = sys.argv[1]
        print('Selected data folder: ' + data_folder)

        bot_token = load_token(data_folder)
        riot.load_key(data_folder)
        users.load_users(data_folder)

        if not bot_token or not riot.riot_api_key:
            print('Create keys files first and restart the program')
            exit

        client.run(bot_token)
        print('WOW Bot main cycle ends here!')
        print('=========================================================================')
    #except Exception as ex:
    #    template = "An exception of type {0} occured. Arguments:\n{1!r}"
    #    message = template.format(type(ex).__name__, ex.args)
    #    print(message)
    #    print('Continue working')
    except KeyboardInterrupt as ex:
        print('KeyboardInterrupt, quitting')
        keep_working = False
    #except:
    #    print('Oops, some unknown error')
    else:
        print('No errors')
        keep_working = False
        
