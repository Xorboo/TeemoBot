import asyncio
import os
import traceback
import time
import logging
import discord
import json
import types
from discord_bot import DiscordBot
from riot import RiotAPI
from users import Users, UserData
from answers import Answers
from emojis import Emojis
from roles_manager import RolesManager


class EloBot(DiscordBot):
    logger = logging.getLogger(__name__)

    parameters_file_name = 'parameters.json'

    _elo_command_hint = '`!nick свой_ник_в_лиге_на_{0}`, например `!nick xXNagibatorXx`'
    private_message_error = 'Эй, пиши в канал на сервере, чтобы я знал где тебе ник или эло выставлять.'
    region_set_error = 'Введи один регион из `{0}`, например `!region euw`'.format(RiotAPI.allowed_regions)

    api_check_period = 60
    api_check_data = {'name': 'Xorboo', 'region': 'euw'}
    # Ranks that will require account confirmation
    confirmation_ranks = ['diamond', 'master', 'challenger']
    rollback_rank = 'bronze'

    initial_sleep_pause = 3    # Before starting autoupdate
    success_sleep_pause = 4     # After successful update (for Discord limits)
    small_sleep_pause = 1       # After check without update (for RiotAPI limits)
    long_sleep_pause = 300      # If over-limited RiotAPI

    def __init__(self, data_folder):
        self.parameters_file_path = os.path.join(data_folder, EloBot.parameters_file_name)
        with open(self.parameters_file_path) as parameters_file:
            self.parameters_data = json.load(parameters_file)
        self.logger.info('Loaded parameters file from \'%s\'', self.save_parameters())

        super(EloBot, self).__init__(self.parameters_data['discord'])
        self.riot_api = RiotAPI(self.parameters_data['riot_api_key'])
        Users.salt = self.parameters_data['salt']
        self.users = Users(data_folder)
        self.emoji = Emojis()

        self.last_api_check_time = 0
        self.api_is_working = True

    def get_basic_hint(self, server_id):
        region = self.users.get_or_create_server(server_id).parameters.get_region().upper()
        return self._elo_command_hint.format(region)

    def save_parameters(self):
        with open(self.parameters_file_path, 'w') as parameters_file:
            json.dump(self.parameters_data, parameters_file)
        self.logger.info('Saved parameters file to \'%s\'', self.parameters_file_path)

    @property
    def all_tokens_are_valid(self):
        return self.token_is_valid and self.riot_api.key_is_valid

    def setup_events(self):
        super().setup_events()

        self.client.event(self.server_join())
        self.client.event(self.server_remove())
        self.client.event(self.event_join())

        self.client.loop.create_task(self.autoupdate_users_data())

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
    def autoupdate_users_data(self):
        yield from self.client.wait_until_ready()
        yield from asyncio.sleep(self.initial_sleep_pause)

        while not self.client.is_closed:
            try:
                yield from self.autoupdate_from_users()
                yield from asyncio.sleep(self.success_sleep_pause)
                yield from self.autoupdate_from_members()
                yield from asyncio.sleep(self.success_sleep_pause)
            except Exception:
                self.logger.error('Autoupdate loop exception: {0}'.format(traceback.format_exc()))
                yield from asyncio.sleep(self.success_sleep_pause)

    @asyncio.coroutine
    def autoupdate_from_users(self):
        self.logger.info('Autoupdating using USERS data')
        if len(self.client.servers) == 0:
            return

        server_index = 0
        while server_index < self.users.data.total_servers:
            server_data = self.users.data.get_server_by_index(server_index)
            user_index = 0
            while user_index < server_data.total_users:
                user_data = server_data.get_user_by_index(user_index)
                success = False
                try:
                    success = yield from self.autoupdate_user(server_data, user_data)
                except Exception:
                    self.logger.error('Autoupdate user_data exception: {0}'.format(traceback.format_exc()))
                if success:
                    yield from asyncio.sleep(self.success_sleep_pause)
                yield from asyncio.sleep(self.small_sleep_pause)
                user_index += 1
            server_index += 1
        self.logger.info('Autoupdating using USERS data - completed')

    @asyncio.coroutine
    def autoupdate_from_members(self):
        self.logger.info('Autoupdating using MEMBERS data')
        if len(self.client.servers) == 0:
            return

        server_index = 0
        while server_index < len(self.client.servers):
            server = list(self.client.servers)[server_index]
            server_data = self.users.get_or_create_server(server.id)
            channel = next((x for x in server.channels if x.name == 'bots' or x.name == 'bot'), server.default_channel)
            member_index = 0
            while member_index < len(server.members):
                member = list(server.members)[member_index]
                user_data = server_data.get_user(member.id)
                if user_data:
                    success = yield from self.autoupdate_user(server_data, user_data)
                    if success:
                        yield from asyncio.sleep(self.success_sleep_pause)
                else:
                    user_cleared = yield from self.clear_name_and_elo(member, server)
                    if user_cleared:
                        self.logger.info('Cleared data for user %s', member)
                        yield from self.message(channel, '{0}, тебя не было в базе, обнулил твои данные. '
                                                'Повтори `!nick` для возвращения эло.'.format(member.mention))
                        yield from asyncio.sleep(self.success_sleep_pause)
                yield from asyncio.sleep(self.small_sleep_pause)
                member_index += 1
            server_index += 1
        self.logger.info('Autoupdating using MEMBERS data - completed')

    @asyncio.coroutine
    def autoupdate_user(self, server_data, user, force_silent=False):
        server = self.client.get_server(server_data.server_id)
        if not server:
            return False
        member = server.get_member(user.discord_id)
        if not member:
            return False
        channel = next((x for x in server.channels if x.name == 'bots' or x.name == 'bot'), server.default_channel)
        result = yield from self.update_user(
            member, user, channel, check_is_conflicted=True, silent=force_silent, is_new_data=False)
        if result.api_error:
            self.logger.error('Autoupdate request riot API error: %s', result.api_error)
            yield from asyncio.sleep(self.long_sleep_pause)

        # Periodic extra save call in case we have changes
        self.users.save_users(check_if_dirty=True)

        return result.rank or result.name

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
            server = member.server

            server_data = self.users.get_or_create_server(server.id)
            user_data = server_data.get_user(member.id)
            success = False
            if user_data:
                success = yield from self.autoupdate_user(server_data, user_data, force_silent=True)
            # Force user to have default gray role

            if success:
                emojis = self.emoji.s(server)
                rank_text = emojis.get(user_data.rank)
                if not rank_text:
                    rank_text = user_data.rank
                msg = 'Привет {0.mention}! Опять ты выходишь на связь? Поставил тебе {1}'.format(member, rank_text)
                yield from self.message(member.server, msg)
            else:
                yield from self.welcome_default(member)
        return on_member_join

    @asyncio.coroutine
    def welcome_default(self, member):
        server = member.server
        try:
            roles_manager = RolesManager(server.roles)
            role_results = yield from roles_manager.set_user_initial_role(self.client, member)
            success = role_results[0]
            if not success:
                self.logger.error('Cant set initial role for user \'%s\' (forbidden)', member)
        except RolesManager.RoleNotFoundException as e:
            self.logger.error('Joined user will have default role (no-elo role was not found)')

        fmt = 'Привет {0.mention}! {1} Чтобы установить свое эло и игровой ник, напиши {2}. ' + \
              'Так людям будет проще тебя найти, да и ник не будет таким серым (как твоя жизнь{3}). ' \
              'Так же есть `!base` для установки первой части ника, и вообще смотри в `!help`'
        em = self.emoji.s(server)
        text = fmt.format(member, em.poro, self.get_basic_hint(server.id), em.kappa)
        yield from self.message(server, text)

    @DiscordBot.owner_action('<new RiotAPI key>')
    @asyncio.coroutine
    def riot_key(self, args, mobj):
        """
        Установить новый RiotAPI ключ.
        Получить его можно по ссылке: https://developer.riotgames.com/
        """
        new_key = args[0]
        self.logger.info('Updating RiotAPI key to \'%s\' by user: %s', new_key, mobj.author)
        self.parameters_data["riot_api_key"] = new_key
        self.riot_api.api_key = new_key
        self.save_parameters()
        yield from self.message(mobj.channel, 'Окей {0}, обновил ключ RiotAPI'.format(mobj.author.mention))
        if mobj.channel.is_private:
            yield from self.message(mobj.channel, 'Удали свое сообщение с ключом, на всякий случай.')
        else:
            yield from self.client.delete_message(mobj)

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
        prefix = '# Доступные команды:\n\n'
        postfix = '\nВведи \'{0}help <command>\' для получения большей инфы по каждой команде.'\
            .format(DiscordBot.PREFIX)

        full_text = self.get_help_string(prefix, postfix, self.ACTIONS)
        yield from self.message(mobj.channel, full_text)

        if self.is_admin(mobj.author):
            self.logger.info('Sending admin commands help to %s', mobj.author)
            prefix = '# Доступные админские команды:\n\n'
            full_text = self.get_help_string(prefix, postfix, self.ADMIN_ACTIONS)
            yield from self.message(mobj.author, full_text)

        if self.is_owner(mobj.author):
            self.logger.info('Sending owner commands help to %s', mobj.author)
            prefix = '# Доступные команды владельца:\n\n'
            full_text = self.get_help_string(prefix, postfix, self.OWNER_ACTIONS)
            yield from self.message(mobj.author, full_text)

    def get_help_string(self, prefix, postfix, dictionary):
        output = prefix
        for c in ['{0}'.format(k) for k in dictionary.keys()]:
            output += '* {0} {1}\n'.format(c, self.HELPMSGS.get(c, ""))
        output += postfix
        return self.pre_text(output)

    @DiscordBot.message_listener()
    def on_message(self, mobj):
        pass

    @asyncio.coroutine
    def change_member_nickname(self, member, new_name):
        if new_name != member.display_name:
            try:
                self.logger.info('Changing nickname from \'{0}\' to \'{1}\' for \'{2}\''
                                 .format(member.display_name, new_name, member).encode('utf-8'))
                yield from self.client.change_nickname(member, new_name)
                return True, True
            except discord.errors.Forbidden as e:
                self.logger.error('Error setting nickname: %s', e)
                return False, True
        else:
            self.logger.debug('Not changing nickname to \'{0}\' for \'{1}\''.format(new_name, member).encode('utf-8'))
            return True, False

    @asyncio.coroutine
    def update_user(self, member, user, channel, check_is_conflicted=False, silent=False, is_new_data=True):
        result = types.SimpleNamespace()
        result.rank = result.name = False
        result.api_error = None

        self.logger.debug('Update member {0} with game name {1} from channel {2}'.format(member, user.nickname, channel))
        mention = member.mention
        old_rank = user.rank.lower()
        try:
            # Getting user elo using RiotAPI
            server = self.users.get_or_create_server(channel.server.id)
            region = server.parameters.get_region()
            rank, game_user_id, nickname = self.riot_api.get_user_info(
                region, user_id=user.game_id, nickname=user.nickname)
            rank = rank.lower()

            if check_is_conflicted:
                confirmed_user = server.find_confirmed_user(game_user_id)
                if confirmed_user:
                    if confirmed_user.discord_id != user.discord_id:
                        if not silent:
                            error_reply = 'Не могу поставить тебе ник `{0}`, {1}, он уже занят за <@!{2}>'\
                                .format(nickname, mention, confirmed_user.discord_id)
                            yield from self.message(channel, error_reply)
                        return result

                # Changing game nickname - 'unconfirming' user
                if user.game_id != game_user_id:
                    user.confirmed = False

            # Checking high-elo
            if not user.is_confirmed:
                if rank in EloBot.confirmation_ranks:
                    self.logger.debug('User {0} requested {1} using nickname \'{2}\', putting him to {3}'
                                      .format(member, rank, nickname, EloBot.rollback_rank).encode('utf-8'))
                    rank = EloBot.rollback_rank.lower()
                    if not silent and (is_new_data or rank != old_rank):
                        required_hash = UserData.create_hash(game_user_id, member.id)
                        confirm_reply = '{0}, если ты правда с хай-эло - переименуй страницу рун на `{1}` и ' \
                                        'подверди свой ник командой `!confirm`. ' \
                                        'А пока что будешь с таким рангом :3'.format(mention, required_hash)
                        yield from self.message(channel, confirm_reply)
            rank_changed = rank != old_rank

            # Saving user to database
            self.users.update_user(user, game_user_id, nickname, rank)

            # Updating users role on server
            roles_manager = RolesManager(channel.server.roles)
            role_success, new_role, roles_changed = yield from roles_manager.set_user_role(self.client, member, rank)
            result.rank = rank_changed or roles_changed

            # Updating user nickname
            nick_manager = NicknamesManager(self.users)
            new_name = nick_manager.get_combined_nickname(member)
            nick_success = True
            if new_name:
                nick_success, has_new_nickname = yield from self.change_member_nickname(member, new_name)
                result.name = has_new_nickname

            # Replying
            if not silent and (is_new_data or result.rank):
                if role_success:
                    emojis = self.emoji.s(channel.server)
                    if is_new_data:
                        answer = Answers.generate_answer(member, new_role.name, emojis)
                    else:
                        # Replace rank text with emojis
                        rank_old_text = emojis.get(old_rank)
                        if not rank_old_text:
                            rank_old_text = old_rank
                        rank_new_text = emojis.get(rank)
                        if not rank_new_text:
                            rank_new_text = rank

                        # Form a reply
                        if rank_changed:
                            answer = '{0}, твое эло изменилось {1} -> {2}.'\
                                .format(member.mention, rank_old_text, rank_new_text)
                        else:
                            answer = 'Эй {0}, вернулся к нам на канал? Выставил тебе твой ранк {1}'\
                                .format(member.mention, rank_new_text)
                    if answer:
                        yield from self.message(channel, answer)
                else:
                    yield from self.message(channel,
                                            'Эй, {0}, у меня недостаточно прав чтобы выставить твою роль, '
                                            'скажи админу чтобы перетащил мою роль выше остальных.'.format(mention))

                if not nick_success:
                    nick_error_reply = '{0}, поменяй себе ник на `{1}` сам, у меня прав нет.'.format(mention, new_name)
                    yield from self.message(channel, nick_error_reply)

        except RiotAPI.UserIdNotFoundException as _:
            api_working = self.check_api_if_needed()
            if api_working:
                requested_nickname = user.nickname
                yield from self.clear_user_data(member, channel.server)
                if not silent:
                    if is_new_data:
                        error_reply = '{0}, ты рак, нет такого ника `{1}` в лиге на `{2}`. '\
                            .format(member.mention, requested_nickname, region.upper())
                    else:
                        error_reply = '{0}, не нашел твоего ника `{1}` при обновлении, очистил твои данные'\
                            .format(member.mention, requested_nickname)
                    yield from self.message(channel, error_reply)
            else:
                if not silent and is_new_data:
                    api_url = 'https://developer.riotgames.com/api-status/'
                    yield from self.message(channel,
                                            '{0}, судя по всему рито сломали их API. '
                                            'Проверь тут ({1}), если все в порядке - напиши о проблеме `{2}` ({3}). '
                                            'Но вообще я и сам ему напишу...'
                                            .format(member.mention, api_url, self.owner, self.owner.mention))
                    yield from self.message(self.owner, 'Тут на `{0}` юзер `{1}` пытается установить себе ник `{2}`, '
                                                        'а АПИ лежит...'.format(channel.server, member, user.nickname))

        except RiotAPI.RiotRequestException as e:
            result.api_error = e.error_code
            if not silent and is_new_data:
                error_reply = '{0}, произошла ошибка при запросе к RiotAPI, попробуй попозже.'.format(member.mention)
                yield from self.message(channel, error_reply)

        except RolesManager.RoleNotFoundException as _:
            if not silent and is_new_data:
                yield from self.message(channel,
                                        'Упс, тут на сервере роли не настроены, не получится тебе роль поставить, {0}. '
                                        'Скажи админу чтобы добавил роль `{1}`'.format(mention, rank))
        return result

    @asyncio.coroutine
    def change_lol_nickname(self, member, nickname, channel):
        self.logger.info('Recieved !nick command for \'{0}\' on \'{1}\''.format(nickname, channel.server)
                         .encode('utf-8'))

        if not nickname:
            yield from self.message(channel, 'Ник то напиши после `!nick`, ну...')
            return

        yield from self.client.send_typing(channel)

        # Setting new nickname - clearing user data before update
        user = self.users.get_or_create_user(member)
        if user.nickname != nickname:
            user.game_id = None
            user.nickname = nickname
            user.confirmed = False

        yield from self.update_user(member, user, channel, check_is_conflicted=True, silent=False)

    @DiscordBot.action('<Ник_в_игре>')
    @asyncio.coroutine
    def nick(self, args, mobj):
        """
        Установить свой игровой ник и эло, чтобы людям было проще тебя найти в игре.
        Например '!nick xXNagibatorXx'
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        nickname = ' '.join(args).strip()
        yield from self.change_lol_nickname(mobj.author, nickname, mobj.channel)

    @DiscordBot.admin_action('<@упоминание> <Ник_в_игре>')
    @asyncio.coroutine
    def force(self, args, mobj):
        """
        Установить игровой ник определенному игроку.
        Например '!nick @ya_ne_bronze xXNagibatorXx'
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        if len(args) < 2:
            yield from self.message(mobj.channel, 'Укажи @юзера и его ник, смотри !help.')
            return

        if not mobj.mentions:
            yield from self.message(mobj.channel, 'Укажи @юзера, которому поставить ник.')
            return

        user = mobj.mentions[0]
        mention_text = args[0]
        if mention_text != user.mention:
            yield from self.message(mobj.channel, '@юзер должен идти первым, смотри !help.')
            return

        nickname = ' '.join(args[1:]).strip()
        self.logger.info('Force setting nickname \'{0}\' to user \'{1}\', admin: \'{2}\''
                         .format(nickname, user, mobj.author).encode('utf-8'))
        yield from self.change_lol_nickname(user, nickname, mobj.channel)

    @DiscordBot.action('<Базовый_Ник>')
    @asyncio.coroutine
    def base(self, args, mobj):
        """
        Установить свой базовый ник (тот, что перед скобками). Если он совпадает с игровым ником, то скобок не будет.
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        base_name = NicknamesManager.clean_name(' '.join(args))
        self.logger.info('Setting base name \'{0}\' for \'{1}\''.format(base_name, mobj.author).encode('utf-8'))

        nick_manager = NicknamesManager(self.users)
        game_name = nick_manager.get_ingame_nickname(mobj.author)
        if game_name:
            new_name = NicknamesManager.create_full_name(base_name, game_name)
        else:
            new_name = base_name
        nick_success, has_new_nickname = yield from self.change_member_nickname(mobj.author, new_name)

        mention = mobj.author.mention
        if nick_success:
            yield from self.message(mobj.channel, 'Окей, {0}, поменял тебе ник.'.format(mention))
        else:
            yield from self.message(mobj.channel,
                                    '{0}, поменяй себе ник на \'{1}\' сам, у меня прав нет.'.format(mention, new_name))

    @DiscordBot.action('')
    @asyncio.coroutine
    def update(self, _, mobj):
        channel = mobj.channel
        yield from self.client.send_typing(channel)

        member = mobj.author
        user = self.users.get_user(member)
        if user and user.has_data:
            yield from self.update_user(member, user, channel, check_is_conflicted=True, silent=False)
        else:
            yield from self.message(channel, 'Сначала поставь себе ник через `!nick`, {0}'.format(member.mention))

    @DiscordBot.action('')
    @asyncio.coroutine
    def confirm(self, _, mobj):
        """
        Подтвердить свой игровой ник. Подтвежденные ники не могут быть выбраны другими людьми на данном канале
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        yield from self.client.send_typing(mobj.channel)
        server = self.users.get_or_create_server(mobj.channel.server.id)
        user_data = server.get_user(mobj.author.id)
        if not user_data:
            reply = '{0}, у тебя не установлен игровой ник, используй `!nick` для этого'.format(mobj.author.mention)
            yield from self.message(mobj.channel, reply)
            return

        bind_hash = user_data.bind_hash
        region = server.parameters.get_region()
        if not user_data.game_id:
            yield from self.message(mobj.channel, 'У тебя устаревшие данные, выполни сначала команду `!nick'
                                    .format(mobj.author.mention))
            return

        has_required_page = self.riot_api.check_user_runepage(user_data.game_id, bind_hash, region)
        if has_required_page:
            conflicted_user_ids = self.users.confirm_user(user_data, server)
            yield from self.update_user(mobj.author, user_data, mobj.channel, check_is_conflicted=False, silent=True)

            success_reply = 'Окей {0}, подтвердил твой игровой ник `{1}`'\
                .format(mobj.author.mention, user_data.nickname)
            yield from self.message(mobj.channel, success_reply)
            yield from self.remove_conflicted_members(conflicted_user_ids, mobj.channel)
        else:
            fail_reply = '{0}, поменяй имя одной из страниц рун на `{1}` для подтверждения, ' \
                         'подожди минуту и повтори команду.'.format(mobj.author.mention, bind_hash)
            yield from self.message(mobj.channel, fail_reply)

    @DiscordBot.action('')
    @asyncio.coroutine
    def clear(self, _, mobj):
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        self.logger.info('User \'{0}\' in {1} use !clear'.format(mobj.author.name, mobj.channel.server).encode('utf-8'))
        yield from self.clear_user_data(mobj.author, mobj.channel.server)
        yield from self.message(mobj.channel, 'Окей, {0}, обнулил твое эло'.format(mobj.author.mention))

    @asyncio.coroutine
    def clear_user_data(self, member, server):
        self.users.remove_user(member)
        yield from self.clear_name_and_elo(member, server)

    @asyncio.coroutine
    def remove_conflicted_members(self, member_ids, reply_channel):
        conflicted_members = []
        for member_id in member_ids:
            conflicted_member = reply_channel.server.get_member(member_id)
            if conflicted_member:
                conflicted_members.append(conflicted_member)
        if conflicted_members:
            for member in conflicted_members:
                yield from self.clear_name_and_elo(member, reply_channel.server)
            members_mentions = ', '.join([x.mention for x in conflicted_members])
            conflict_reply = '{0}: очистил эло, зачем чужие ники юзать, а?'.format(members_mentions)
            yield from self.message(reply_channel, conflict_reply)

    @asyncio.coroutine
    def clear_name_and_elo(self, member, server):
        roles_manager = RolesManager(server.roles)
        role_results = yield from roles_manager.set_user_initial_role(self.client, member)
        has_new_roles = role_results[2]

        clean_name = NicknamesManager.get_base_name(member)
        nick_success, has_new_nickname = yield from self.change_member_nickname(member, clean_name)
        return has_new_roles or has_new_nickname

    @DiscordBot.action()
    @asyncio.coroutine
    def region(self, _, mobj):
        """
        Установить/Получить регион, по которому будет выставляться эло.
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        current_region = self.users.get_or_create_server(mobj.server.id).parameters.get_region().upper()
        yield from self.message(mobj.channel, 'Текущий регион: `{0}`'.format(current_region))

    @DiscordBot.admin_action('<Регион ({0})>'.format(RiotAPI.allowed_regions))
    @asyncio.coroutine
    def set_region(self, args, mobj):
        """
        Установить/Получить регион, по которому будет выставляться эло.
        """
        if mobj.channel.is_private:
            self.logger.info('User \'{0}\' sent private message \'{1}\''
                             .format(mobj.author.name, mobj.content).encode('utf-8'))
            yield from self.message(mobj.channel, self.private_message_error)
            return

        if len(args) == 1:
            region = args[0].strip().lower()
            self.logger.info('Recieved !region command for \'%s\' on %s', region, mobj.server.name)

            if self.users.set_server_region(mobj.server.id, region):
                yield from self.message(mobj.channel, 'Установил регион `{0}` на сервере.'.format(region.upper()))
            else:
                yield from self.message(mobj.channel,
                                        self.region_set_error + ', `{0}` не подходит'.format(region.upper()))
        else:
            yield from self.message(mobj.channel, self.region_set_error)
            return

    @DiscordBot.owner_action('')
    @asyncio.coroutine
    def halt(self, _, mobj):
        """
        Reboot the bot entirely
        """
        self.logger.info('Owner \'%s\' called full reboot, closing the program.', mobj.author)
        yield from self.message(mobj.channel, 'Слушаюсь, милорд.')
        yield from self.client.close()

    def check_api_if_needed(self):
        current_time = time.time()
        if current_time - self.last_api_check_time < self.api_check_period:
            return self.api_is_working

        self.logger.info('Checking Riot API status...')
        self.last_api_check_time = current_time
        self.api_is_working = False
        try:
            self.riot_api.get_summoner_data(self.api_check_data['region'], nickname=self.api_check_data['name'])
            self.api_is_working = True
            self.logger.info('Riot API is working properly.')
        except RiotAPI.RiotRequestException as e:
            self.logger.warning('Checking RiotAPI failed - api is not working, error: {0}'.format(e.error_code))
        return self.api_is_working


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

        if len(base) > 0 and base.lower() != nick.lower():
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
