import asyncio
import os
import logging
import discord
from discord_bot import DiscordBot
from riot import RiotAPI
from users import Users
from answers import Answers
from emojis import Emojis


class EuwBot(DiscordBot):
    logger = logging.getLogger(__name__)

    token_file_name = 'discord_token.txt'

    elo_command_hint = '`!nick свой_ник_на_весте`, например `!nick xXNagibatorXx`'
    private_message_error = 'Эй, пиши в канал на сервере, чтобы я знал где тебе ник или эло выставлять.'

    def __init__(self, data_folder):
        token_file_path = os.path.join(data_folder, EuwBot.token_file_name)
        super(EuwBot, self).__init__(token_file_path)
        self.riot_api = RiotAPI(data_folder)
        self.users = Users(data_folder)
        self.emoji = Emojis()

    @property
    def all_tokens_are_valid(self):
        return self.token_is_valid and self.riot_api.key_is_valid

    def setup_events(self):
        super().setup_events()

        self.client.event(self.server_join())
        self.client.event(self.server_remove())
        self.client.event(self.event_join())

    def event_ready(self):
        @asyncio.coroutine
        def on_ready():
            self.logger.info('Connection status: %s', self.client.is_logged_in)

            self.display_invite_link()
            yield from self.set_status(self.STATUS)

            for s in self.client.servers:
                self.logger.info('Updating data for server \'%s\'...', s)
                prune_amount = yield from self.client.estimate_pruned_members(s, days=30)
                self.logger.info('Inactive members for the last 30 days: %s/%s.', prune_amount, len(s.members))
                self.emoji.update_server(s)
                yield from self.check_no_elo_members(s)
            self.logger.info('Finished \'on_ready()\'')
        return on_ready

    @asyncio.coroutine
    def check_no_elo_members(self, s):
        self.logger.info('Checking for users with no elo set on server \'%s\'...', s)
        no_elo_members = []
        try:
            roles_manager = RolesManager(s.roles)
            for member in s.members:
                if member != self.client.user and not roles_manager.has_any_role(member):
                    no_elo_members.append(member)
            if no_elo_members:
                current = 1
                total = len(no_elo_members)
                self.logger.info('Found %s members with no elo set, setting their elo...', total)
                for member in no_elo_members:
                    if current % 10 == 0:
                        self.logger.info('Setting for %s/%s...', current, total)
                    yield from roles_manager.set_user_initial_role(self.client, member)
                    current += 1
                self.logger.info('\'No elo\' set for all %s users', total)
            else:
                self.logger.info('No members with no elo found.')
        except RolesManager.RoleNotFoundException as e:
            self.logger.error('Couldnt find default role, not setting it.')

    @asyncio.coroutine
    def check_for_no_elo(self, member, roles_manager):
        if not roles_manager.has_any_role(member):
            self.logger.debug('Setting \'no_elo\' role for %s', member)
            yield from roles_manager.set_user_initial_role(self.client, member)

    def server_join(self):
        @asyncio.coroutine
        def on_server_join(server):
            self.logger.info('Bot joined to the server \'%s\'', server)
            self.emoji.update_server(server)
        return on_server_join

    def server_remove(self):
        @asyncio.coroutine
        def on_server_remove(server):
            self.logger.info('Bot left the server \'%s\'', server)
            self.emoji.remove_server(server)
        return on_server_remove

    def event_join(self):
        @asyncio.coroutine
        def on_member_join(member):
            self.logger.info('User \'%s\' joined to the server \'%s\'', member.name, member.server)
            channel = member.server

            # Force user to have default gray role
            try:
                roles_manager = RolesManager(channel.roles)
                success, role = yield from roles_manager.set_user_initial_role(self.client, member)
                if not success:
                    self.logger.error('Cant set initial role for user \'%s\' (forbidden)', member)
            except RolesManager.RoleNotFoundException as e:
                self.logger.error('Joined user will have default role (no-elo role was not found)')

            fmt = 'Привет {0.mention}! {1} Чтобы установить свое эло и игровой ник, напиши {2}. ' + \
                  'Так людям будет проще тебя найти, да и ник не будет таким серым (как твоя жизнь{3})'
            em = self.emoji.s(channel)
            text = fmt.format(member, em.poro, EuwBot.elo_command_hint, em.kappa)
            yield from self.message(channel, text)
        return on_member_join

    @DiscordBot.action('<Команда>')
    @asyncio.coroutine
    def help(self, args, mobj):
        """
        Правда? Тебе нужен мануал по мануалу? Свсм упрлс?
        """
        if args:
            key = '{0}{1}'.format(DiscordBot.PREFIX, args[0])
            self.logger.info('Sendin help for key \'%s\'', key)
            if key in self.ACTIONS:
                command_help = self.HELPMSGS.get(key, '')
                if command_help:
                    command_help = ' ' + command_help
                command_doc = self.ACTIONS[key].__doc__
                text = self.pre_text('Подсказка для \'{0}{1}\':{2}'.format(key, command_help, command_doc))
                msg = yield from self.message(mobj.channel, text)
                return msg
            else:
                self.logger.info('No help for key \'%s\' found', key)

        self.logger.info('Sending generic help')
        output = '# Доступные команды:\n\n'
        for c in ['{0}'.format(k) for k in self.ACTIONS.keys()]:
            output += '* {0} {1}\n'.format(c, self.HELPMSGS.get(c, ""))
        output += '\nВведи \'{0}help <command>\' для получения *большей инфы по каждой команде.'\
            .format(DiscordBot.PREFIX)
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
            #if mobj.channel.is_private:
            #    self.logger.info('User \'%s\' sent private message \'%s\'', mobj.author.name, mobj.content)
            #    yield from self.message(mobj.channel, self.private_message_error)
            #    return

            mention = mobj.author.mention
            nickname = ' '.join(args).strip()
            self.logger.info('Recieved !nick command for \'%s\'', nickname)

            if not nickname:
                yield from self.message(mobj.channel, 'Ник то напиши после `!nick`, ну...')
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
                    self.logger.info('Setting nickname: \'%s\' for \'%s\'', new_name, mobj.author)
                    yield from self.client.change_nickname(mobj.author, new_name)
                    nick_success = True
                except discord.errors.Forbidden as e:
                    self.logger.error('Error setting nickname: %s', e)
                    nick_success = False

            # Replying
            if role_success:
                answer = Answers.generate_answer(mobj.author, new_role.name, self.emoji.s(mobj.channel.server))
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
                                    '{0}, ты рак, нет такого ника \'{1}\' в лиге на весте. '
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
        if mobj.channel.is_private:
            self.logger.info('User \'%s\' sent private message \'%s\'', mobj.author.name, mobj.content)
            yield from self.message(mobj.channel, self.private_message_error)
            return

        base_name = NicknamesManager.clean_name(' '.join(args))
        self.logger.info('Setting base name \'%s\' for \'%s\'', base_name, mobj.author)

        nick_manager = NicknamesManager(self.users)
        game_name = nick_manager.get_ingame_nickname(mobj.author)
        if game_name:
            new_name = NicknamesManager.create_full_name(base_name, game_name)
        else:
            new_name = base_name

        try:
            self.logger.info('Setting nickname: \'%s\'', new_name)
            yield from self.client.change_nickname(mobj.author, new_name)
            nick_success = True
        except discord.errors.Forbidden as e:
            self.logger.error('Error setting nickname: %s', e)
            nick_success = False

        mention = mobj.author.mention
        if nick_success:
            yield from self.message(mobj.channel, 'Окей, {0}, поменял тебе ник.'.format(mention))
        else:
            yield from self.message(mobj.channel,
                                    '{0}, поменяй себе ник на \'{1}\' сам, у меня прав нет.'.format(mention, new_name))


class RolesManager:
    logger = logging.getLogger(__name__)

    def __init__(self, server_roles):
        # self.logger.info('Parsing server roles...')
        self.rank_roles = []
        self.rank_ids = []
        for r in server_roles:
            role_name = r.name.lower()
            if role_name in RiotAPI.ranks:
                self.rank_roles.insert(0, r)
                self.rank_ids.insert(0, r.id)
        pass

    @asyncio.coroutine
    def set_user_initial_role(self, client, member):
        success, role = yield from self.set_user_role(client, member, RiotAPI.initial_rank)
        return success, role

    @asyncio.coroutine
    def set_user_role(self, client, member, role_name):
        self.logger.info('Setting role \'%s\' for \'%s\'', role_name, member)

        role = self.get_role(role_name)
        new_roles = self.get_new_user_roles(member.roles, role)
        try:
            yield from client.replace_roles(member, *new_roles)
            return True, role
        except discord.errors.Forbidden as e:
            self.logger.error('Error setting role: %s', e)
        return False, role

    def has_any_role(self, member):
        for role in member.roles:
            if role.id in self.rank_ids:
                return True
        return False

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
            return user.nickname
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
