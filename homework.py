import logging
import os
import sys
import time
from http import HTTPStatus
from urllib.error import URLError

import requests
import telebot
from telebot.apihelper import ApiException
from dotenv import load_dotenv

from exceptions import TokensError, KeyError, HomeworkStatusError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

GREETINGS_TEXT = (
    'Привет, я телеграмм-бот который будет оповещать тебя'
    ' о статусе твоей домашней работы!!!'
)

SUCCESSFUL_SENDING_TEXT = 'Сообщение успешно отправлено'

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    source = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    token_list = [token for token in source if not globals()[token]]
    if token_list:
        text_error = (
            'Для дальнейшей работы программы Вам необходимо'
            f' предоставить следующие tokens: {" ".join(token_list)}'
        )
        logging.critical(text_error)
        raise TokensError(text_error)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту с параметрами указанными в timestamp."""
    params = {'from_date': timestamp}
    logger.info(f'Производим запрос к {ENDPOINT} c params={params}')

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error(f'Эндпоинт - {ENDPOINT} недоступен')
            raise URLError(f'Эндпоинт - {ENDPOINT} недоступен')

        logger.info(f'Запрос к {ENDPOINT} c params={params} успешен!')
        return response.json()
    except requests.RequestException as e:
        logger.error(f'Сбой запроса к {ENDPOINT} c params={params}!'
                     'Причина: {str(e)}')
        raise ConnectionError(f'Сбой запроса к {ENDPOINT} c params={params}!')


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    logging.info('Начинаем проверку API-ответа сервера!')
    if not isinstance(response, dict):
        raise TypeError('API структура данных не соответствует заданной')
    if 'homeworks' not in response:
        raise KeyError('В API-ответе, ключ - "homeworks" отсутствует')
    if 'current_date' not in response:
        raise KeyError('В API-ответе, ключ - "current_date" отсутствует')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Полученная структура данных "homeworks" не '
                        'соответствует заданной')
    logging.info('Проверку API-ответа сервера успешна!')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    logging.info('Начинаем проверку статуса домашней работы!')
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Ключ "homework_name" отсутствует')
    status = homework.get('status')
    if not status:
        raise KeyError('Ключ "status" отсутствует')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise HomeworkStatusError('Неизвестный статус домашней работы')
    logging.info('Проверка статуса домашней работы успешна!')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    logging.info('Начинаем отправку сообщения!')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(SUCCESSFUL_SENDING_TEXT)
        return True  # Возвращаем True при успешной отправке
    except ApiException as e:
        logging.error(f'Ошибка отправки сообщений: {e}')
        return False  # Возвращаем False, если возникла ошибка при отправке


def main():
    """Основная логика работы бота."""
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    check_tokens()  # Убедитесь, что токены корректны
    timestamp = int(time.time())
    send_message(bot, GREETINGS_TEXT)
    start_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logging.debug('Нет новых статусов у работ')
            else:
                homework_status = parse_status(homework[0])
                message_sent = send_message(bot, homework_status)
                if message_sent:
                    timestamp = response['current_date']

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if send_message(bot, message) and start_error_message != message:
                start_error_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        encoding='utf-8',
        format='%(asctime)s [%(levelname)s] [функция %(funcName)s '
               'стр.%(lineno)d] - %(message)s'
    )
    logging.StreamHandler(sys.stdout)
    main()