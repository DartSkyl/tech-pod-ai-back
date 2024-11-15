import os
from dotenv import load_dotenv, find_dotenv
import logging

if not find_dotenv():
    exit("Переменные окружения не загружены т.к отсутствует файл .env")
else:
    load_dotenv()

API_URL = os.getenv('API_URL', 'http://localhost:8000/')

# Переменные для базы данных
DB_HOST = os.getenv('db_host')
DB_NAME = os.getenv('db_name')
DB_PASS = os.getenv('db_pass')
DB_USER = os.getenv('db_user')
DB_PORT = int(os.getenv('db_port'))

# Переменные для чата
CHAT_CHAR_DELAY = int(os.getenv('chat_char_delay'))
CHAT_MAX_DELAY = int(os.getenv('chat_max_delay'))
CHAT_MESS_WAITING = int(os.getenv('chat_mess_waiting'))
QUESTION_CHECK = int(os.getenv('question_check'))

# Переменные для почтовой службы
API_URL_EMAIL = os.getenv('api_url_email')
EMAIL_FROM = os.getenv('email_from')
EMAIL_FROM_PASS = os.getenv('email_from_pass')

SMTP_SERVER_HOST = os.getenv('smtp_server_host')
SMTP_SERVER_PORT = os.getenv('smtp_server_port')

# Расположение фронта
FRONT_PATH = os.getenv('front_path')
DEMO_PAGE_PATH = os.getenv('demo_path')

# Заголовки
ORIGINS_LIST = os.getenv('origins').split()
