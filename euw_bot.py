import asyncio
import os
import discord
from discord_bot import DiscordBot
from riot import RiotAPI
from users import Users
from answers import Answers


class EuwBot(DiscordBot):
    token_file_name = 'discord_token.txt'

    elo_command_hint = '`!nick свой_ник_на_весте`, например `!nick xXNagibatorXx`'

    def __init__(self, data_folder):
        token_file_path = os.path.join(data_folder, EuwBot.token_file_name)
        super(EuwBot, self).__init__(token_file_path)
        self.riot_api = RiotAPI(data_folder)
        self.users = Users(data_folder)

    @property
    def all_tokens_are_valid(self):
        return self.token_is_valid and self.riot_api.key_is_valid

    # Override from DiscordBot
    def event_join(self):
        @asyncio.coroutine
        def on_member_join(member):
            print('User {0} joined to the server {1}'.format(member.name, member.server))
            channel = member.server

            # Force user to have default gray role
            try:
                roles_manager = RolesManager(channel.roles)
                success, role = yield from roles_manager.set_user_initial_role(self.client, member)
                if not success:
                    print('ERROR: cant set initial role for user {0} (forbidden)'.format(member))
            except RolesManager.RoleNotFoundException as e:
                print('ERROR: Joined user will have default role')

            fmt = 'Привет {0.mention}! :poro: Чтобы установить свое эло и игровой ник, напиши {1}. ' + \
                  'Так людям будет проще тебя найти, да и ник не будет таким серым :tw_Kappa:'
            yield from self.message(channel, fmt.format(member, EuwBot.elo_command_hint))
        return on_member_join

    @DiscordBot.action('<Команда>')
    @asyncio.coroutine
    def help(self, args, mobj):
        """
        Правда? Тебе нужен мануал по мануалу? Свсм упрлс?
        """
        if args:
            key = '{0}{1}'.format(DiscordBot.PREFIX, args[0])
            if key in self.ACTIONS:
                command_help = self.HELPMSGS.get(key, '')
                if command_help:
                    command_help = ' ' + command_help
                command_doc = self.ACTIONS[key].__doc__
                text = self.pre_text('Подсказка для \'{0}{1}\':{2}'.format(key, command_help, command_doc))
                msg = yield from self.message(mobj.channel, text)
                return msg
        output = '# Доступные команды:\n\n'
        for c in ['{0}'.format(k) for k in self.ACTIONS.keys()]:
            output += '* {0} {1}\n'.format(c, self.HELPMSGS.get(c, ""))
        output += '\nВведи \'{0}help <command>\' для получения *большей инфы по каждой команде'.format(DiscordBot.PREFIX)
        msg = yield from self.message(mobj.channel, self.pre_text(output))
        return msg

    @DiscordBot.message_listener()
    def on_message(self, mobj):
        pass

    @DiscordBot.action('<Ник_в_игре (только на EUW)>')
    @asyncio.coroutine
    def nick(self, args, mobj):
        """
        Установить свой игровой ник и эло, чтобы людям было проще тебя найти в игре.
        Например '!nick xXNagibatorXx'
        """
        try:
            nickname = ' '.join(args).strip()
            if not nickname:
                yield from self.message(mobj.channel, 'Ник то напиши, ну...')
                return

            yield from self.client.send_typing(mobj.channel)

            # Getting user elo using RiotAPI
            rank, game_user_id, nickname = self.riot_api.get_user_elo(nickname)

            # Saving user to database
            self.users.add_user(mobj.author, game_user_id, nickname, rank)

            # Updating users role on server
            roles_manager = RolesManager(mobj.channel.server.roles)
            role_success, new_role = yield from roles_manager.set_user_role(self.client, mobj.author, rank)

            # Updating user nickname
            nick_manager = NicknamesManager(self.users)
            new_name = nick_manager.get_combined_nickname(mobj.author)
            if new_name:
                try:
                    print('Setting nickname: ' + new_name)
                    yield from self.client.change_nickname(mobj.author, new_name)
                    nick_success = True
                except discord.errors.Forbidden as e:
                    print('Error setting nickname: {0}'.format(e))
                    nick_success = False

            # Replying
            mention = mobj.author.mention
            if role_success:
                answer = Answers.generate_answer(mobj.author, new_role.name)
                yield from self.message(mobj.channel, answer)
            else:
                yield from self.message(mobj.channel,
                                        'Эй, {0}, у меня недостаточно прав чтобы выставить твою роль, '
                                        'скажи админу чтобы перетащил мою роль выше остальных.'.format(mention))

            if not nick_success:
                yield from self.message(
                    mobj.channel,
                    '{0}, поменяй себе ник на \'{1}\' сам, у меня прав нет.'.format(mention, new_name))

        except RiotAPI.UserIdNotFoundException as e:
            yield from self.message(mobj.channel,
                                    '{0}, ты рак, нет ника \'{1}\' в лиге на весте. '
                                    'Ну или риоты API сломали, попробуй попозже.'.format(mention, nickname))
        except RolesManager.RoleNotFoundException as e:
            yield from self.message(mobj.channel,
                                    'Упс, тут на сервере роли не настроены, не получится тебе роль поставить, {0}. '
                                    'Скажи админу чтобы добавил роль \'{1}\''.format(mention, rank))

    @DiscordBot.action('<Базовый_Ник>')
    @asyncio.coroutine
    def base(self, args, mobj):
        """
        Установить свой базовый ник (тот, что перед скобками). Если он совпадает с игровым ником, то скобок не будет.
        """
        base_name = NicknamesManager.clean_name(' '.join(args))

        nick_manager = NicknamesManager(self.users)
        game_name = nick_manager.get_ingame_nickname(mobj.author)
        if game_name:
            new_name = NicknamesManager.create_full_name(base_name, game_name)
        else:
            new_name = base_name

        try:
            print('Setting nickname: ' + new_name)
            yield from self.client.change_nickname(mobj.author, new_name)
            nick_success = True
        except discord.errors.Forbidden as e:
            print('Error setting nickname: {0}'.format(e))
            nick_success = False

        mention = mobj.author.mention
        if nick_success:
            yield from self.message(mobj.channel, 'Окей, {0}, поменял тебе ник.'.format(mention))
        else:
            yield from self.message(mobj.channel,
                                    '{0}, поменяй себе ник на \'{1}\' сам, у меня прав нет.'.format(mention, new_name))


class RolesManager:
    def __init__(self, server_roles):
        self.rank_roles = []
        self.rank_ids = []
        for r in server_roles:
            role_name = r.name.lower()
            if role_name in RiotAPI.ranks:
                self.rank_roles.insert(0, r)
                self.rank_ids.insert(0, r.id)
        pass

    @asyncio.coroutine
    def set_user_initial_role(self, client, author):
        success, role = yield from self.set_user_role(client, author, RiotAPI.initial_rank)
        return success, role

    @asyncio.coroutine
    def set_user_role(self, client, author, role_name):
        role = self.get_role(role_name)
        new_roles = self.get_new_user_roles(author.roles, role)
        try:
            yield from client.replace_roles(author, *new_roles)
            return True, role
        except discord.errors.Forbidden as e:
            print('Error setting role: {0}'.format(e))
        return False, role

    def get_role(self, role_name):
        role_name = role_name.lower()
        for r in self.rank_roles:
            if r.name.lower() == role_name:
                return r
        raise RolesManager.RoleNotFoundException('Can\'t find role {0} on server'.format(role_name))

    def get_new_user_roles(self, current_roles, new_role):
        new_roles = [new_role]
        for role in current_roles:
            if role.id not in self.rank_ids:
                new_roles.insert(0, role)
        return new_roles

    class RoleNotFoundException(Exception):
        pass


class NicknamesManager:
    def __init__(self, users_storage):
        self.users = users_storage

    def get_combined_nickname(self, member):
        ingame_nickname = self.get_ingame_nickname(member)
        if not ingame_nickname:
            return None

        base_name = NicknamesManager.get_base_name(member)
        full_name = NicknamesManager.create_full_name(base_name, ingame_nickname)
        return full_name

    def get_ingame_nickname(self, member):
        user = self.users.get_user(member)
        if user:
            return user['nickname']
        return None

    @staticmethod
    def get_base_name(member):
        return NicknamesManager.clean_name(member.display_name)

    @staticmethod
    def clean_name(name):
        br_open = name.rfind('(')
        br_close = name.rfind(')')
        br_first = min(br_open, br_close)
        if br_first >= 0:
            return (name[:br_first]).strip()
        return name.strip()

    @staticmethod
    def create_full_name(base, nick):
        max_len = 32
        over_text = '...'

        # Trim both names in case they are too long
        if len(base) > max_len:
            base = base[:max_len - len(over_text)] + over_text
        if len(nick) > max_len:
            nick = nick[:max_len - len(over_text)] + over_text

        if base.lower() != nick.lower():
            # Combine names if they are not equal
            total_len = len(base) + len(nick) + len(' ()')
            if total_len > max_len:
                # Combined name is too long, trimming base name so it will fit
                base_overhead = (total_len - max_len) + len(over_text)
                if len(base) > base_overhead:
                    # Can still fit some of the base name with '...' after it
                    base = base[:-base_overhead] + over_text
                else:
                    # Can't fit base name at all, returning plain nickname
                    return nick
            return '{0} ({1})'.format(base, nick)
        else:
            # Names are equal
            return nick