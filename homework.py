import logging
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


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Бот отправил сообщение: {message}')
    except Exception as error:
        raise SystemError(f'Сообщение не отправилось: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    logging.info(f'Отправка запроса к {ENDPOINT} с параметрами {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise APIConnectionError(
                f'Не удалось подключиться к API '
                f'код ответа: {response.status_code}'
            )
        return response.json()
    except Exception as error:
        raise APIErrorsParams(
            'Ошибка при отправке запроса к API: {} {} {} {}'.format(
                ENDPOINT,
                HEADERS,
                params,
                error
            )
        )


def check_response(response):
    """Проверяем ответ API на корректность."""
    if not isinstance(response, dict):
        message = 'Некорректный тип данных, ожидался словарь'
        logging.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        logging.error('Отсутствует необоходимый ключ homeworks')
        raise KeyError

    get_homework = response['homeworks']
    if not isinstance(get_homework, list):
        message = 'Некорректный тип данных, ожидался список.'
        logging.error(message)
        raise TypeError(message)

    return get_homework


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

    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'Пришел неизвестный статус работы: {homework_status}')
        raise KeyError

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения.
    Если отсутсвует хотя бы одна переменная должно возвращаться False.
    """
    env_dict = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'
    }
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        for key in env_dict:
            if env_dict[key] is None:
                logging.critical(
                    f'Отсутствует переменная {key}'
                )
        return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения')
        raise SystemExit('Отсутствует обязательная переменная окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    last_msg = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                msg = parse_status(homeworks[0])
                if last_msg != msg:
                    send_message(bot, msg)
                    last_msg = msg
            else:
                logging.debug('Статус работы не изменился')
            
            if 'current_date' not in response:
                logging.error('В запросе отсутсвует "current_date"')
                raise KeyError('В запросе отсутсвует "current_date"')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    create_log_file = logging.FileHandler('main.log', 'w')
    stream_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[create_log_file, stream_handler],
        format=(
            '%(asctime)s [%(levelname)s] %(funcName)s %(lineno)d %(message)s'
        )
    )
    main()
