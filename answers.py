import random
import logging


class Answers:
    logger = logging.getLogger(__name__)

    role_answers = {
        'Unranked': [
            ', теперь ты Unranked.',
            ', теперь ты анранкед.',
            ', ты у нас без ранка оказывается.'
        ],
        'Bronze': [
            ', теперь ты Bronze.',
            ', теперь ты бронза.',
            ', ты у нас бронзовый.'
        ],
        'Silver': [
            ', теперь ты Silver.',
            ', теперь ты сильвер.',
            ', ты у нас выходит сильвер?'
        ],
        'Gold': [
            ', теперь ты Gold.',
            ', теперь ты голда.',
            ', ты у нас голда, среднячок, молодец.'
        ],
        'Platinum': [
            ', теперь ты Platinum.',
            ', теперь ты платина.',
            ', теперь ты платка.',
            ', ты платиновый, неплохо.'
        ],
        'Diamond': [
            ', теперь ты Diamond.',
            ', теперь ты даймонд.',
            ', ты у нас даймонд говоришь?'
        ],
        'Master': [
            ', теперь ты Master!',
            ', теперь ты мастер!',
            ', у нас тут мастер есть!'
        ],
        'Challanger': [
            ', теперь ты Challanger!',
            ', теперь ты чалик!',
            ', у нас тут чалик есть!'
        ],
    }

    role_comments = {
        'Unranked': [
            'Что, трайхардить не любишь?',
            'В ранкедах обижают? :3',
            'И правильно, мы отдыхать в лигу ходим, а не задротить.',
            'И правильно, играть надо для фана.'
        ],
        'Bronze': [
            'Если бы не тиммейты - голдой бы был, я уверен.',
            'Твой первый сезон в ранкедах?',
            'Это все лаги, я уверен.',
            'Ранкеды вечерком под пивасик неплохо идут, согласен.',
            'You Are Special!'
        ],
        'Silver': [
            'Как ты из бронзы вылез?',
            'Тиммейты продолжают на дно тащить?',
            'Неплохо, что.'
        ],
        'Gold': [
            'А чего в платку не вылезаешь?',
            'Был бы даймондом, если бы не лаги.',
            'Был бы даймондом, если бы не тролли-тиммейты.',
            'Скинец дадут, молодец.'
        ],
        'Platinum': [
            'Самый соленый ранк.',
            'Как ты этих раков терпишь вообще?',
            'Вылезай оттуда лучше, фу.'
        ],
        'Diamond': [
            'Кто забустил?',
            'Бущеный наверняка :3',
            'Хоть не пятый даймонд то? Хуже платины ведь',
            '\"Выше только звезды\"? :3',
            'Work while they all play?',
            'Get a life, nerd.'
        ],
        'Master': [
            'Не верю!',
            'Охренеть!',
            'Сколько за такой буст заплатил?',
            'Врешь ведь?',
            'И не стыдно врать?'
        ],
        'Challanger': [
            'Не верю!',
            'Охренеть!',
            'Сколько за такой буст заплатил?',
            'Неплохо у тебя друг играет',
            'Врешь ведь?',
            'И не стыдно врать?'
        ],
    }

    @staticmethod
    def __main_answer(role, emoji):
        possible = Answers.role_answers[role]
        answer = random.choice(possible)
        emoji_name = role.lower()
        if emoji_name == 'unranked':
            emoji_name = 'amumu'
        return answer + emoji.get(emoji_name)

    @staticmethod
    def __comment_answer(role):
        possible = Answers.role_comments[role]
        if random.randrange(0, 100) > 30:
            return ' {0}'.format(random.choice(possible))
        return ''

    @staticmethod
    def generate_answer(member, role, emoji):
        Answers.logger.debug('Generating answer for role \'%s\'', role)
        main_answer = Answers.__main_answer(role, emoji)
        comment = Answers.__comment_answer(role)
        answer = 'Окей, {0}{1}{2}'.format(member.mention, main_answer, comment)
        return answer
