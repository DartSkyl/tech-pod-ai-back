from random import choices
import string
import datetime
import json

from langchain_core.messages import HumanMessage, AIMessage
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pymysql.err import IntegrityError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError

from router import page_router, index_router
from database import bot_base
from config import (ORIGINS_LIST, EMAIL_FROM, EMAIL_FROM_PASS, SMTP_SERVER_HOST,
                    SMTP_SERVER_PORT, CHAT_MESS_WAITING, CHAT_CHAR_DELAY, CHAT_MAX_DELAY, QUESTION_CHECK)

from ai_core import process_chat, check_other_question, time_for_communication
from mail_sender import MailSender

app = FastAPI()
app.include_router(page_router)
app.include_router(index_router)

clients_dict = dict()

origins = ORIGINS_LIST

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mail_sender = MailSender(
    email_from=EMAIL_FROM,
    email_from_pass=EMAIL_FROM_PASS,
    smtp_host=SMTP_SERVER_HOST,
    smtp_port=SMTP_SERVER_PORT
)


async def start_db():
    await bot_base.create_pool()
    await bot_base.check_db_structure()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    @staticmethod
    async def send_personal_message(message: str, websocket: WebSocket, delay: int = 0):
        data = {
            'format': 'text',
            'time': str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            'text': message,
            'delay': delay
        }

        await websocket.send_json(data=data)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


async def send_contact_data(client_data: dict, client_id: int):
    """Через данную функцию отправляем контактные данные клиента заказчику"""
    await mail_sender.send_contact_data(client_data, client_id)


# Словарь хранит время последнего ответа и сокета с которого оно было отправлено по ключу client_id
last_message_time = {}


async def send_messages(websocket: WebSocket, client_id):
    user_msg = ''
    for mess in clients_dict[client_id]['messages_list']:
        user_msg += mess + ' '

    clients_dict[client_id]['chat_history'].append(HumanMessage(content=user_msg))

    if clients_dict[client_id]['check_other_question']:
        clients_dict[client_id]['have_other_question'] = await check_other_question(
            clients_dict[client_id]['chat_history'])
        try:
            # Если ответ "no" значит вопрос больше нет
            clients_dict[client_id]['have_other_question'] = False if clients_dict[client_id]['have_other_question']['response'].lower() == 'no' else True
            if not clients_dict[client_id]['have_other_question']:
                clients_dict[client_id]['time_for_communication'] = True
        except KeyError:
            clients_dict[client_id]['have_other_question'] = True
        clients_dict[client_id]['check_other_question'] = False

    clients_dict[client_id]['messages_list'] = []  # Обнуляем ожидающий список сообщений
    await messages_checker.remove_job(client_id)

    if not clients_dict[client_id]['time_for_communication'] and not clients_dict[client_id]['check_time_for_communication']:
        ai_answer = await process_chat(user_input=user_msg, chat_history_list=clients_dict[client_id]['chat_history'])
        if clients_dict[client_id]['have_other_question']:
            await messages_checker.check_other_question(websocket, client_id)
    elif clients_dict[client_id]['time_for_communication']:
        ai_answer = 'What time would you like our manager to contact you?'
        clients_dict[client_id]['time_for_communication'] = False
        clients_dict[client_id]['check_time_for_communication'] = True
    else:
        ai_answer = await time_for_communication(user_msg)
        clients_dict[client_id]['check_time_for_communication'] = False

    # Задержка перед отправкой сообщения, для эмуляции живого общения.
    # Переменные CHAT_CHAR_DELAY и CHAT_MAX_DELAY указываются в файле .env в миллисекундах
    delay = len(ai_answer) * CHAT_CHAR_DELAY
    delay = delay if delay <= CHAT_MAX_DELAY else CHAT_MAX_DELAY

    await manager.send_personal_message(ai_answer, websocket, delay=delay)

    await bot_base.insert_msg(
        chat_id=str(client_id),
        author='Chat-bot',
        msg_text=ai_answer,
        format_name='text'
    )
    clients_dict[client_id]['chat_history'].append(AIMessage(content=ai_answer))


async def check_question(websocket: WebSocket, client_id):
    ai_answer = 'Do you have any other questions?'
    await manager.send_personal_message(ai_answer, websocket, delay=1000)

    await bot_base.insert_msg(
        chat_id=str(client_id),
        author='Chat-bot',
        msg_text=ai_answer,
        format_name='text'
    )

    clients_dict[client_id]['chat_history'].append(AIMessage(content=ai_answer))
    clients_dict[client_id]['check_other_question'] = True
    await messages_checker.remove_job(client_id + 'oq')


class MessagesChecker:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    async def start_checker(self):
        self._scheduler.start()

    async def wait_new_messages(self, client_id, websocket: WebSocket):
        try:
            self._scheduler.remove_job(client_id)
        except JobLookupError:
            pass
        self._scheduler.add_job(
            id=client_id,
            func=send_messages,
            kwargs={'websocket': websocket, 'client_id': client_id},
            trigger='interval',
            seconds=CHAT_MESS_WAITING,
            max_instances=1,
        )

    async def check_other_question(self, websocket: WebSocket, client_id):
        try:
            self._scheduler.remove_job(client_id + 'oq')
        except JobLookupError:
            pass
        self._scheduler.add_job(
            id=client_id + 'oq',
            func=check_question,
            kwargs={'websocket': websocket, 'client_id': client_id},
            trigger='interval',
            seconds=QUESTION_CHECK,
            max_instances=1,
        )

    async def remove_job(self, client_id):
        self._scheduler.remove_job(client_id)


messages_checker = MessagesChecker()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id):

    last_message_time[client_id] = {'socket': websocket}

    # Если пользователь новый, то создаем для него индивидуальный словарь
    if not clients_dict.get(client_id):

        # На всякий случай проверим, может контактные данные уже есть в базе

        check_data = True if len(await bot_base.get_contact_data(client_id)) > 0 else False
        clients_dict[client_id] = {
            'chat_history': [],
            'contact_info': dict(),
            'contacts_received': check_data,
            'messages_list': []  # Используется для того, что бы пользователь мог писать сразу несколько сообщений, а ИИ не отвечал на каждое по отдельности
        }

    await manager.connect(websocket)
    try:
        # Эти ключи нужны для логического завершения разговора. С их помощью проверяем остались ли вопросы у клиента
        clients_dict[client_id]['check_other_question'] = False
        clients_dict[client_id]['have_other_question'] = True
        clients_dict[client_id]['time_for_communication'] = False
        clients_dict[client_id]['check_time_for_communication'] = False
        while True:
            data = await websocket.receive_text()
            # Если от фронта пришел ответ JSON, то он будет в виде строки. Проведем манипуляции для
            # преобразования и отправляем заказчику

            if '{' and '}' in data:
                try:
                    await bot_base.add_new_chat(
                        chat_id=str(client_id),
                        # На данный момент хэш это случайная строка
                        chat_hash=''.join(choices(string.digits + string.ascii_letters, k=8))
                    )
                except IntegrityError:
                    pass
                user_form_with_data = json.loads(data.encode())
                clients_dict[client_id]['contacts_received'] = True
                await send_contact_data(user_form_with_data, client_id)
                answer_text = f'Thank you, {user_form_with_data["name"]}. How can I assist you?'
                await manager.send_personal_message(answer_text, websocket, delay=2500)

                await bot_base.insert_msg(
                    chat_id=str(client_id),
                    author='Client',
                    msg_text=data.replace('"', '$'),
                    format_name='text'
                )

                await bot_base.insert_msg(
                    chat_id=str(client_id),
                    author='Chat-bot',
                    msg_text=answer_text,
                    format_name='text'
                    )

                await bot_base.add_new_contact_data(
                    chat_id=str(client_id),
                    name=user_form_with_data['name'],
                    telephone=user_form_with_data['tel'],
                    email=user_form_with_data['email'],
                )

                client_msg = (f'My name is {user_form_with_data["name"]}, '
                              f'telephone is {user_form_with_data["tel"]}, '
                              f'email is {user_form_with_data["email"]}')

                clients_dict[client_id]['chat_history'].append(HumanMessage(content=client_msg))
                clients_dict[client_id]['chat_history'].append(AIMessage(content=answer_text))

            else:
                # На всякий случай заменим все двойные кавычки,
                # иначе может произойти синтаксическая ошибка SQL при записи в базу
                data = data.replace('"', '$')

                await bot_base.insert_msg(
                    chat_id=str(client_id),
                    author='Client',
                    msg_text=data,
                    format_name='text'
                )

                clients_dict[client_id]['messages_list'].append(data)

                await messages_checker.wait_new_messages(client_id, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    await start_db()
    await mail_sender.start_sender()
    await messages_checker.start_checker()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
