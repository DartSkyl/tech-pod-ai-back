import os
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse

from database import bot_base
from config import API_URL, FRONT_PATH, DEMO_PAGE_PATH

index_router = APIRouter()
page_router = APIRouter(prefix="/pages", tags=["Pages"])

templates = Jinja2Templates(directory="templates")


async def reform_message(msg_text):
    return (msg_text
            .replace('{', '')
            .replace('}', '')
            .replace('$', '')
            # .replace(':', '')
            .replace('name:', '')
            .replace('tel:', '')
            .replace('email:', '')
            .replace(',', ', ').replace(' , ', ' '))


async def check_empty_form(chat_history):
    for i in range(len(chat_history)):
        try:
            if chat_history[i]['format'] == 'form':
                for msg in chat_history[i:]:
                    if msg['text'].startswith('Thank you, '):
                        chat_history[i]['format'] = 'text'
        except IndexError:
            pass
    return chat_history


# --------------------
# Index router
# --------------------


@index_router.get("/")
async def get_chat_page(request: Request):
    with open(DEMO_PAGE_PATH, 'r') as html:
        demo_page = html.read()
        return HTMLResponse(content=demo_page, status_code=200)


@index_router.get("/{file_path}")
async def get_demo_page_files(file_path: str):
    if os.path.exists(f"{FRONT_PATH + file_path}"):
        return FileResponse(f"{FRONT_PATH + file_path}")
    else:
        return FileResponse(f"{FRONT_PATH}/dist/{file_path}")


@index_router.get("/dist/{file_path}")
async def get_demo_page_files_dist(file_path: str):
    return FileResponse(f"{FRONT_PATH}/dist/{file_path}")


# --------------------
# Page router
# --------------------


@page_router.get("/client_history/dialogs")
async def get_all_dialogs(request: Request):
    # Получаем все имеющиеся чаты
    dialogs = await bot_base.get_all_chats()
    # Формируем словарь, где ключ это ID чата, а значение это контактные данные.
    # Если контактных данных нет, то значением будет 'empty'
    dialogs = {chat_id: await bot_base.get_contact_data(chat_id) for chat_id in dialogs}
    # На предыдущем этапе в словаре значениями являются картежи.
    # Преобразуем кортежи в словарь и добавляем последнее сообщение
    dialogs = {chat_id:
               {'name': cont[1], 'tel': cont[2], 'email': cont[3],
                'last_msg': (await bot_base.get_chat_history(chat_id))[-1]} if cont != 'empty'

               else {'name': 'unknown', 'tel': 'unknown', 'email': 'unknown',
                     'last_msg': (await bot_base.get_chat_history(chat_id))[-1]} for chat_id, cont in
               dialogs.items()}
    # Отсеем пустые диалоги с помощью другого словаря
    not_empty_dialogs = {}
    for chat_id, elem in dialogs.items():
        if elem['last_msg'] != 'empty':
            not_empty_dialogs[chat_id] = elem

    not_empty_dialogs = sorted(not_empty_dialogs.items(), key=lambda item: item[1]['last_msg'][5], reverse=True)
    # Так как на предыдущем этапе мы получаем кортеж, то нужно его преобразовать в JSON, т.е словарь
    not_empty_dialogs = {cont[0]: cont[1] for cont in not_empty_dialogs}

    return not_empty_dialogs


@page_router.get("/client_history")
async def get_chat_history_page(request: Request):
    return templates.TemplateResponse("client_history.html", {"request": request, "api_url": API_URL})


@page_router.get("/client_history/{chat_id}")
async def get_client_history(chat_id):
    chat_history = await bot_base.get_chat_history(str(chat_id))
    if chat_history != ('empty',):
        chat_history_json = [{'author': elem[3], 'text': await reform_message(elem[4]) if '{' in elem[4] else elem[4],
                              } for elem in chat_history]
        return chat_history_json
    return []


@page_router.get("/client_history/read/{chat_id}")
async def get_chat_history_page(request: Request, chat_id):
    return templates.TemplateResponse("client_history_read.html",
                                      {"request": request, "api_url": API_URL, "chat_id": chat_id})


@page_router.get("/chat_history/{chat_id}")
async def get_chat_history(chat_id):
    chat_history = await bot_base.get_chat_history(str(chat_id))
    chat_history_json = [{'type': 'outgoing' if elem[3] == 'Client' else 'incoming',
                          'text': await reform_message(elem[4]) if '{' in elem[4] else elem[4],
                          'time': str(elem[5].strftime("%Y-%m-%dT%H:%M:%SZ")),
                          'format': elem[2]} for elem in chat_history] if chat_history != ('empty',) else {}
    # Проверяем на наличие не заполненных форм
    chat_history_json = await check_empty_form(chat_history_json)
    return chat_history_json
