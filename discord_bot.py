# Based on https://github.com/sleibrock/discord-bots/blob/master/bots/Bot.py

import traceback
import sys
import logging
import asyncio
import discord
from discord import Client, Game, Permissions


class DiscordBot:
    logger = logging.getLogger(__name__)

    PREFIX = '!'
    MESSAGE_LISTENERS = list()
    ACTIONS = dict()
    ADMIN_ACTIONS = dict()
    HELPMSGS = dict()
    STATUS = 'with ururus'

    @staticmethod
    def pre_text(msg, lang=None):
        """"Encapsulate a string in a <pre> container"""
        s = "```Markdown\n{}\n```"
        if lang is not None:
            s = s.format(format+"\n{}")
        return s.format(msg.rstrip().strip("\n").replace("\t", ""))

    @staticmethod
    def is_admin(member):
        if type(member) is not discord.Member:
            return False
        return member.server_permissions.administrator

    @staticmethod
    def action(help_msg=''):
        """
        Decorator to register functions into the action map
        This is bound to static as we can't use an instance object's method
        as a decorator (could be a classmethod but who cares)
        """
        def regfunc(func):
            if callable(func):
                if func.__name__ not in DiscordBot.ACTIONS:
                    fname = '{0}{1}'.format(DiscordBot.PREFIX, func.__name__)
                    DiscordBot.ACTIONS[fname] = func
                    DiscordBot.HELPMSGS[fname] = help_msg.strip()
                    return True
            return func
        return regfunc

    @staticmethod
    def admin_action(help_msg=''):
        """
        Decorator to register functions into the action map
        This is bound to static as we can't use an instance object's method
        as a decorator (could be a classmethod but who cares)
        """
        def regfunc(func):
            if callable(func):
                if func.__name__ not in DiscordBot.ADMIN_ACTIONS:
                    fname = '{0}{1}'.format(DiscordBot.PREFIX, func.__name__)
                    DiscordBot.ADMIN_ACTIONS[fname] = func
                    DiscordBot.HELPMSGS[fname] = help_msg.strip()
                    return True
            return func
        return regfunc

    @staticmethod
    def message_listener():
        """
        Decorator to register function which sould be called when message is recieved
        """
        def regfunc(func):
            if callable(func):
                if func.__name__ not in DiscordBot.MESSAGE_LISTENERS:
                    DiscordBot.MESSAGE_LISTENERS.append(func)
                    return True
            return func
        return regfunc

    # Instance methods below
    def __init__(self, token_file_path):
        self.client = Client()
        self.token = DiscordBot.load_token(token_file_path)

    @property
    def token_is_valid(self):
        return bool(self.token)

    @staticmethod
    def load_token(token_file_path):
        token = ''
        try:
            with open(token_file_path, 'r') as token_file:
                token = token_file.read()
                DiscordBot.logger.info('Discord token loaded: \'%s\'', token)
        except IOError as e:
            DiscordBot.logger.error('Couldn\'t open discord token file, '
                                    'create file with the token key in \'%s\', error: %s', token_file_path, e)
        return token

    @asyncio.coroutine
    def message(self, channel, string):
        """
        Shorthand version of client.send_message
        So that we don't have to arbitrarily type
        'self.client.send_message' all the time
        """
        msg = yield from self.client.send_message(channel, string)
        return msg

    def display_invite_link(self):
        """
        Show a link that will let you add the bot to one of your current servers
        """
        url = discord.utils.oauth_url(self.client.user.id)
        self.logger.warning('Bot invite link [no permissions]: %s', url)
        url = discord.utils.oauth_url(self.client.user.id, Permissions.all())
        self.logger.warning('Bot invite link [full permissions]: %s', url)
        return

    @asyncio.coroutine
    def set_status(self, string):
        """Set the client's presence via a Game object"""
        status = yield from self.client.change_presence(game=Game(name=string))
        return status

    def event_ready(self):
        """Change this event to change what happens on login"""
        @asyncio.coroutine
        def on_ready():
            self.display_invite_link()
            yield from self.set_status(self.STATUS)
            self.logger.info('Connection status: {0}'.format(self.client.is_logged_in))
        return on_ready

    def event_error(self):
        """"Change this for better error logging if needed"""
        @asyncio.coroutine
        def on_error(evt, *args, **_):
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.error('Discord error in \'{0}\', {1}'.format(evt, traceback.format_exc()))

            if len(args) > 0:
                args_obj = args[0]
                if hasattr(args_obj, 'channel'):
                    error_message = 'A wild `{0}` appears... It uses `{1}`, It\'s super effective!'\
                        .format(exc_type.__name__, exc_value)
                    yield from self.message(args_obj.channel, error_message)
                else:
                    self.logger.warning('No channel found in exception, object is: %s', type(args_obj))
            else:
                self.logger.warning('No args provided for the exception, can\'t reply in discord channel')

        return on_error

    def event_message(self):
        """Change this to change overall on message behavior"""
        @asyncio.coroutine
        def on_message(msg):
            self.logger.debug('Recieved message: %s', msg)

            # Ignoring our own messages
            if msg.author == self.client.user:
                return

            # Call all message listeners
            [msg_listener(self, msg) for msg_listener in DiscordBot.MESSAGE_LISTENERS]

            # Parse the message for special commands
            args = msg.content.strip().split(' ')
            key = args.pop(0).lower()  # messages sent can't be empty

            # Admin actions
            if self.is_admin(msg.author):
                if key in self.ADMIN_ACTIONS:
                    result = yield from self.ADMIN_ACTIONS[key](self, args, msg)
                    return result

            # Standart actions
            if key in self.ACTIONS:
                result = yield from self.ACTIONS[key](self, args, msg)
                return result
            return
        return on_message

    def setup_events(self):
        """
        Set up all events for the Bot
        You can override each event_*() method in the class def
        """
        self.client.get_all_members()
        self.client.event(self.event_message())
        self.client.event(self.event_error())
        self.client.event(self.event_ready())

    def run(self):
        """
        Main event loop
        Set up all Discord client events and then run the loop
        """
        if not self.token_is_valid:
            DiscordBot.logger.error('Cant run the bot, token is not loaded')
            return

        self.setup_events()
        loop = None
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.client.start(self.token))
        except Exception as e:
            DiscordBot.logger.error('Caught an exception: {0}', e)
        except SystemExit:
            DiscordBot.logger.warning('System Exit signal')
        except KeyboardInterrupt:
            DiscordBot.logger.warning('Keyboard Interrupt signal')
        finally:
            DiscordBot.logger.info('Bot is quitting')
            loop.run_until_complete(self.client.logout())
            loop.stop()
            loop.close()
            quit()
        return
