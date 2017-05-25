# Based on https://github.com/sleibrock/discord-bots/blob/master/bots/Bot.py

from sys import exc_info
import asyncio
import discord
from discord import Client, Game


class DiscordBot:
    PREFIX = "!"
    MESSAGE_LISTENERS = list()
    ACTIONS = dict()
    HELPMSGS = dict()
    STATUS = "Ururu"

    @staticmethod
    def pre_text(msg, lang=None):
        """"Encapsulate a string in a <pre> container"""
        s = "```Markdown\n{}\n```"
        if lang is not None:
            s = s.format(format+"\n{}")
        return s.format(msg.rstrip().strip("\n").replace("\t", ""))

    @staticmethod
    def action(help_msg=""):
        """
        Decorator to register functions into the action map
        This is bound to static as we can't use an instance object's method
        as a decorator (could be a classmethod but who cares)
        """
        def regfunc(function):
            if callable(function):
                if function.__name__ not in DiscordBot.ACTIONS:
                    fname = '{0}{1}'.format(DiscordBot.PREFIX, function.__name__)
                    DiscordBot.ACTIONS[fname] = function
                    DiscordBot.HELPMSGS[fname] = help_msg.strip()
                    return True
            return function
        return regfunc

    @staticmethod
    def message_listener():
        """
        Decorator to register function which sould be called when message is recieved
        """
        def regfunc(function):
            if callable(function):
                if function.__name__ not in DiscordBot.MESSAGE_LISTENERS:
                    DiscordBot.MESSAGE_LISTENERS.append(function)
                    return True
            return function
        return regfunc

    # Instance methods below
    def __init__(self, token_file_path):
        self.actions = dict()
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
                print('Discord token loaded: ' + token)
        except IOError as e:
            print('ERROR: Couldn\'t open discord token file, create file with the token key: ' + token_file_path)
            print(e)
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

    def display_no_servers(self):
        """
        If the bot isn't connected to any servers, show a link
        that will let you add the bot to one of your current servers
        """
        if not self.client.servers:
            print("Join link: {0}".format(discord.utils.oauth_url(self.client.user.id)))
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
            self.display_no_servers()
            yield from self.set_status(self.STATUS)
            print("Connection status: {0}".format(self.client.is_logged_in))
        return on_ready

    def event_error(self):
        """"Change this for better error logging if needed"""
        @asyncio.coroutine
        def on_error(evt, *args, **kwargs):
            print("Discord error in '{0}''".format(evt))
            print(exc_info())
        return on_error

    def event_join(self):
        @asyncio.coroutine
        def on_member_join(member):
            print('User {0} joined to the server {1}'.format(member.name, member.server))
        return on_member_join

    def event_message(self):
        """Change this to change overall on message behavior"""
        @asyncio.coroutine
        def on_message(msg):
            # Call all message listeners
            [msg_listener(self, msg) for msg_listener in DiscordBot.MESSAGE_LISTENERS]

            # Parse the message for special commands
            args = msg.content.strip().split(" ")
            key = args.pop(0).lower()  # messages sent can't be empty
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
        self.client.event(self.event_message())
        self.client.event(self.event_error())
        self.client.event(self.event_join())
        self.client.event(self.event_ready())

    def run(self):
        """
        Main event loop
        Set up all Discord client events and then run the loop
        """
        if not self.token_is_valid:
            print('Cant run the bot, token is not loaded')
            return

        self.setup_events()
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.client.start(self.token))
        except Exception as e:
            print("Caught an exception: {0}".format(e))
        except SystemExit:
            print("System Exit signal")
        except KeyboardInterrupt:
            print("Keyboard Interrupt signal")
        finally:
            print("Bot is quitting")
            loop.run_until_complete(self.client.logout())
            loop.stop()
            loop.close()
            quit()
        return
