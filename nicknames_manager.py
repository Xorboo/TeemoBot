

class NicknamesManager:
    def __init__(self, users_storage):
        self.users = users_storage

    def get_combined_nickname(self, member, user_data):
        ingame_nickname = self.get_ingame_nickname(member)
        if not ingame_nickname:
            return None

        base_name = NicknamesManager.get_base_name(member, user_data)
        full_name = NicknamesManager.create_full_name(base_name, ingame_nickname)
        return full_name

    def get_ingame_nickname(self, member):
        user = self.users.get_user(member)
        if user:
            return user.nickname
        return None

    @staticmethod
    def get_base_name(member, user_data):
        base_name = NicknamesManager._clean_name(member.display_name)
        if user_data and user_data.is_cancer:
            base_name = NicknamesManager._add_cancer(base_name)
        return base_name

    @staticmethod
    def create_base_name(name_to_clean, is_cancer):
        clean_name = NicknamesManager._clean_name(name_to_clean)
        if is_cancer:
            clean_name = NicknamesManager._add_cancer(clean_name)
        return clean_name

    @staticmethod
    def _clean_name(name):
        br_open = name.rfind('(')
        br_close = name.rfind(')')
        br_first = min(br_open, br_close)
        if br_first >= 0:
            return (name[:br_first]).strip()
        return name.strip()

    @staticmethod
    def _add_cancer(name):
        if not name.startswith('🦀'):
            name = '🦀 ' + name
        return name

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
