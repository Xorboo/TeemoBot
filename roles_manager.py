import asyncio
import discord
import logging
from riot import RiotAPI


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

    @staticmethod
    def has_no_role(member):
        for role in member.roles:
            if not role.is_everyone and role.name.lower() != RiotAPI.initial_rank:
                return False
        return True

    @asyncio.coroutine
    def set_user_initial_role(self, client, member):
        role_results = yield from self.set_user_role(client, member, RiotAPI.initial_rank)
        return role_results

    @asyncio.coroutine
    def set_user_role(self, client, member, role_name):

        role = self.get_role(role_name)
        new_roles = self.get_new_user_roles(member.roles, role)

        has_new_roles = self.roles_different(member.roles, new_roles)
        try:
            if has_new_roles:
                self.logger.info('Setting role \'%s\' for \'%s\'', role_name, member)
                yield from client.replace_roles(member, *new_roles)
            return True, role, has_new_roles
        except discord.errors.Forbidden as e:
            self.logger.error('Error setting role: %s', e)
        return False, role, has_new_roles

    def roles_different(self, old_roles, new_roles):
        added_roles = []
        for r in new_roles:
            if r not in old_roles:
                added_roles.append(r)

        removed_roles = []
        for r in old_roles:
            if r not in new_roles:
                removed_roles.append(r)

        has_changed_roles = added_roles or removed_roles
        if has_changed_roles:
            self.logger.info('Changed roles, added: [{0}], removed: [{1}]'
                             .format(', '.join([x.name for x in added_roles]),
                                     ', '.join([x.name for x in removed_roles])))
        return has_changed_roles

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
