import logging
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv

load_dotenv()

CONNECTION_ERROR = '{error}, {url}, {headers}, {params}'
SERVICE_REJECTION = '{code}'
WRONG_ENDPOINT = '{response_status}, {url}, {headers}, {params}'
WRONG_HOMEWORK_STATUS = '{homework_status}'
WRONG_DATA_TYPE = 'Неверный тип данных {type}, вместо "dict"'
STATUS_IS_CHANGED = '{verdict}, {homework}'
STATUS_IS_NOT_CHANGED = 'Статус не изменился, нет записей'
FAILURE_TO_SEND_MESSAGE = '{error}, {message}'
GLOBAL_VARIABLE_IS_MISSING = 'Отсутствует глобальная переменная'
GLOBAL_VARIABLE_IS_EMPTY = 'Пустая глобальная переменная'
MESSAGE_IS_SENT = 'Сообщение {message} отправлено'
FORMAT_NOT_JSON = 'Формат не json {error}'
LIST_IS_EMPTY = 'Список пустой'

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class ServiceError(Exception):
    """Ошибка отсутствия доступа по заданному эндпойнту."""

    pass


class NetworkError(Exception):
    """Ошибка отсутствия сети."""

    pass


class EndpointError(Exception):
    """Ошибка, если эндпойнт не корректен."""

    pass


class MessageSendingError(Exception):
    """Ошибка отправки сообщения."""

    pass


class GlobalsError(Exception):
    """Ошибка, если есть пустые глобальные переменные."""

    pass


class DataTypeError(Exception):
    """Ошибка, если тип данных не dict."""

    pass


class ResponseFormatError(Exception):
    """Ошибка, если формат response не json."""

    pass


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for token_name, token in {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }.items():
        if token is None:
            logging.critical(f'{GLOBAL_VARIABLE_IS_MISSING}: {token_name}')
            return False
        if not token:
            logging.critical(f'{GLOBAL_VARIABLE_IS_EMPTY}: {token_name}')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение пользователю в Телегу."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logging.error(FAILURE_TO_SEND_MESSAGE.format(error=error,
                                                     message=message))
        raise MessageSendingError(FAILURE_TO_SEND_MESSAGE.format(
            error=error,
            message=message,
        ))
    logging.debug(MESSAGE_IS_SENT.format(message=message))


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    all_params = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**all_params)
    except requests.exceptions.RequestException as error:
        raise TeleBot.TelegramError(CONNECTION_ERROR.format(
            error=error,
            **all_params,
        ))
    response_status = response.status_code
    if response_status != 200:
        raise EndpointError(WRONG_ENDPOINT.format(
            response_status=response_status,
            **all_params,
        ))
    try:
        return response.json()
    except Exception as error:
        raise ResponseFormatError(FORMAT_NOT_JSON.format(error))


def check_response(response):
    """
    Возвращает домашку, если есть.
    Проверяет валидность её статуса.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Данные под ключом "homeworks" должны быть списком')

    if not homeworks:
        logging.debug('Список домашних работ пуст.')
        raise IndexError(LIST_IS_EMPTY)

    return homeworks[0]


def parse_status(homework):
    """Возвращает текст сообщения от ревьюера."""
    if not isinstance(homework, dict):
        raise DataTypeError(WRONG_DATA_TYPE.format(type=type(homework)))

    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise NameError(WRONG_HOMEWORK_STATUS.format(homework_status))

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise GlobalsError('Ошибка глобальной переменной. Смотрите логи.')
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            logging.info(homework)
            timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

        except IndexError:
            message = 'Статус работы не изменился'
            send_message(bot, message)
            logging.info(message)

        finally:
            time.sleep(RETRY_PERIOD)
        logging.info(MESSAGE_IS_SENT.format(message))


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(message)s, %(levelname)s, %(name)s',
        filemode='w',
        filename='main.log',
        level=logging.ERROR,
    )
    main()
