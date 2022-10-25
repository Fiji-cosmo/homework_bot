import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import APIConnectionError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS_LIST = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HW_STATUS_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        raise SystemError(
            f'Сообщение в чат {TELEGRAM_CHAT_ID} не отправилось: {error}'
        )
    else:
        logging.info(
            f'Бот отправил сообщение в чат {TELEGRAM_CHAT_ID}: {message}'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }
    logging.info(
        f'Отправка запроса к эндпоинту с параметрами: {request_params}'
    )
    try:
        response = requests.get(**request_params)
    except Exception as error:
        raise ConnectionError(
            f'Ошибка при отправке запроса к API: {error}, '
            f'с параметрами: {request_params}'
        )

    if response.status_code != HTTPStatus.OK:
        raise APIConnectionError(
            f'Не удалось подключиться к API '
            f'код ответа: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяем ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Некорректный тип данных: {type(response)}, ожидался словарь.'
        )

    if 'homeworks' not in response:
        raise KeyError('Отсутствует необоходимый ключ homeworks')

    homework_list = response['homeworks']
    if not isinstance(homework_list, list):
        raise TypeError(
            f'Некорректный тип данных: '
            f'{type(response["homeworks"])}, ожидался список.'
        )

    return homework_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе.
    И статус этой работы.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name"')
    homework_name = homework['homework_name']

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status"')
    homework_status = homework['status']

    if homework_status not in HW_STATUS_VERDICTS:
        raise KeyError(
            f'Пришел неизвестный статус работы: {homework_status}'
        )

    verdict = HW_STATUS_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения.
    Если отсутсвует хотя бы одна переменная должно возвращаться False.
    """
    tokens = True
    for token in TOKENS_LIST:
        if not globals().get(token):
            tokens = False
            logging.info(f'Отсутвует токен: {token}')
    return tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_msg = 'Отсутствует обязательная переменная окружения'
        logging.critical(error_msg)
        raise SystemExit(error_msg)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_msg = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Статус работы не изменился')
                continue
            msg = parse_status(homeworks[0])
            if last_msg != msg:
                send_message(bot, msg)
                last_msg = msg
            current_timestamp = response.get(
                'current_date', current_timestamp
            )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if last_msg != message:
                send_message(bot, message)
                last_msg = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            RotatingFileHandler(
                filename=os.path.join(os.path.dirname(__file__), 'main.log'),
                maxBytes=50000000,
                backupCount=2,
                encoding='utf-8'
            ),
            logging.StreamHandler(sys.stdout)
        ],
        format=(
            '%(asctime)s [%(levelname)s] - '
            '(%(filename)s).%(funcName)s:%(lineno)d - %(message)s'
        )
    )
    main()
