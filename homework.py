from email.policy import default
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import APIConnectionError, APIErrorsParams

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(
            f'Бот отправил сообщение в чат {TELEGRAM_CHAT_ID}: {message}'
        )
    except Exception as error:
        raise SystemError(
            f'Сообщение в чат {TELEGRAM_CHAT_ID} не отправилось: {error}'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    logging.info(f'Отправка запроса к {ENDPOINT} с параметрами {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise APIErrorsParams(
            'Ошибка при отправке запроса к API: {} {} {} {}'.format(
                ENDPOINT,
                HEADERS,
                params,
                error
            )
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
        message = (
            f'Некорректный тип данных: {type(response)}, ожидался словарь.'
        )
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'Отсутствует необоходимый ключ homeworks'
        raise KeyError(message)

    homework_list = response['homeworks']
    if not isinstance(homework_list, list):
        message = (
            f'Некорректный тип данных: {type(response["homeworks"])}, ожидался список.'
        )
        raise TypeError(message)

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

    if homework_status not in VERDICTS:
        raise KeyError(
            f'Пришел неизвестный статус работы: {homework_status}'
        )

    verdict = VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения.
    Если отсутсвует хотя бы одна переменная должно возвращаться False.
    """
    tokens = True
    tokens_check = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens_check:
        if token is None:
            tokens = False
            logging.info(f'Отсутвует токен: {token}')
        return tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения')
        raise SystemExit('Отсутствует обязательная переменная окружения')

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
            current_timestamp = response.get('current_date', default) 
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
