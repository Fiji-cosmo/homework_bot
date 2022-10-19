import logging
import os
import sys
import time

import requests
import telegram

from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import RequestError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message):
    """Отправка сообщения в Telegram."""
    try:
        logging.info(f'Бот отправил сообщение: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(error)


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logging.info(f'Отправка запроса к {ENDPOINT} с параметрами {params}')
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        raise RequestError(response)
    return response.json()


def check_response(response):
    """Проверяем ответ API на корректность."""
    if not response:
        logging.error('в ответе пустой словарь.')
        raise KeyError()

    if type(response) is not dict:
        logging.error('Некорректный тип данных, ожидался словарь')
        raise TypeError

    if 'homeworks' not in response:
        logging.error('Отсутствует необоходимый ключ homeworks')
        raise KeyError

    if type(response['homeworks']) is not list:
        logging.error('Некорректный тип данных, ожидался список.')
        raise TypeError

    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе.
    И статус этой работы.
    """
    homework_name = homework.get('homework_name')
    if not homework_name:
        logging.error(f'Поле {homework_name} отсутсвует или пустое')
        raise KeyError

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'Статус {homework_status} не определен')
        raise KeyError

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения.
    Если отсутсвует хотя бы одна переменная должно возвращаться False.
    """
    return all((TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения')
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug('Статус работы не изменился')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )
    main()
