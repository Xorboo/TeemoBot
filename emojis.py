import logging


class Emojis:
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.servers = {}

    def update_server(self, server):
        self.logger.info('Updating emojis for server \'%s\'...', server)
        self.servers[server.id] = Emojis.EmojiList(server)

    def remove_server(self, server):
        self.logger.info('Removing emojis for server \'%s\'', server)
        del self.servers[server.id]

    def s(self, server):
        if server.id in self.servers:
            return self.servers[server.id]
        else:
            self.logger.warning('Creating empty EmojiList for server \'%s\'', server)
            return Emojis.EmojiList()

    class EmojiList:
        logger = logging.getLogger(__name__)

        required_emojis = {
            'poro': 'poro',
            'tw_Kappa': 'kappa',
            'amumu': 'amumu',
            'tier_0_unranked': 'unranked',
            'tier_1_bronze': 'bronze',
            'tier_2_silver': 'silver',
            'tier_3_gold': 'gold',
            'tier_4_plat': 'platinum',
            'tier_5_dia': 'diamond',
            'tier_6_master': 'master',
            'tier_7_chal': 'challenger'
        }

        def __init__(self, server=None):
            for em in self.required_emojis:
                em_tag = self.required_emojis[em]
                setattr(self, em_tag, '')

            if server is not None:
                for em in server.emojis:
                    if em.name in self.required_emojis:
                        em_tag = self.required_emojis[em.name]
                        self.logger.info('Found emoji %s for \'%s\'', em, em_tag)
                        setattr(self, em_tag, str(em))
            else:
                self.logger.warning('Creating empty EmojiList')

        def get(self, emoji_name):
            emoji_text = getattr(self, emoji_name, '')
            if not emoji_text:
                self.logger.warning('Couldnt find emoji \'%s\'', emoji_name)
            return emoji_text
