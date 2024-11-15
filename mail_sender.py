import smtplib
from smtplib import SMTPServerDisconnected
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import asyncio

from config import API_URL_EMAIL
from database import bot_base


class MailSender:
    """Класс создает объект, который отправляет email"""

    def __init__(self, email_from, email_from_pass, smtp_host, smtp_port):
        self._email_from = email_from
        self._email_from_pass = email_from_pass
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        self._smtp_server.ehlo()

    async def start_sender(self):
        """Логинимся на почте"""
        self._smtp_server.login(user=self._email_from, password=self._email_from_pass)

    async def send_contact_data(self, client_data: dict, client_id):
        """Отправляем контактные данные заказчику на почту"""
        # Создание объекта сообщения
        msg = MIMEMultipart()
        try:
            email_to = (await bot_base.get_email_to())[1]
            # Настройка параметров сообщения
            msg["From"] = 'Ricochet Chatbot'
            msg["To"] = email_to
            msg["Subject"] = 'New customer contacted via chatbot'

            # Добавление текста в сообщение
            msg_text = (f'Client`s contact info:\n\n'
                        f'Name: {client_data["name"] if client_data.get("name") else "not specified"}\n'
                        f'Tel: {client_data["tel"] if client_data.get("tel") else "not specified"}\n'
                        f'Email: {client_data["email"] if client_data["email"] != "" else "not specified"}\n\n'
                        f'You can view the chat history here: '
                        f'{API_URL_EMAIL}/{client_id}/messages\n')

            msg.attach(MIMEText(msg_text, "plain"))
            try:
                self._smtp_server.sendmail(from_addr=self._email_from, to_addrs=email_to, msg=msg.as_string())
            except SMTPServerDisconnected:
                self._smtp_server.connect(self._smtp_host, self._smtp_port)
                # self._smtp_server.starttls()
                self._smtp_server.ehlo()
                self._smtp_server.login(user=self._email_from, password=self._email_from_pass)
                self._smtp_server.sendmail(from_addr=self._email_from, to_addrs=email_to, msg=msg.as_string())
        except Exception as e:
            print(e)
            pass
