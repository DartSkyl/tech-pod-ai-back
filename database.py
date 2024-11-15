import datetime
import aiomysql
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME


class AiDataBase:
    def __init__(self):
        self.pool = None

    async def create_pool(self):
        self.pool = await aiomysql.create_pool(host=DB_HOST, port=DB_PORT,
                                               user=DB_USER, password=DB_PASS,
                                               db=DB_NAME, autocommit=True)

    async def check_db_structure(self):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute('CREATE TABLE IF NOT EXISTS all_chats'
                                  '(chat_id VARCHAR(255) PRIMARY KEY,'
                                  'chat_hash VARCHAR(255),'
                                  'client_name VARCHAR(255));')

                await cur.execute('CREATE TABLE IF NOT EXISTS all_messages'
                                  '(id MEDIUMINT AUTO_INCREMENT PRIMARY KEY,'
                                  'chat_id VARCHAR(255),'
                                  'format VARCHAR(255),'
                                  'author VARCHAR(255),'
                                  'msg_text TEXT,'
                                  'date_added DATETIME,'
                                  'FOREIGN KEY (chat_id) REFERENCES all_chats(chat_id));')

                await cur.execute(f'CREATE TABLE IF NOT EXISTS all_contacts_data'
                                  f'(chat_id VARCHAR(255) PRIMARY KEY,'
                                  f'name VARCHAR(255),'
                                  f'telephone VARCHAR(255),'
                                  f'email VARCHAR(255),'
                                  f'FOREIGN KEY (chat_id) REFERENCES all_chats(chat_id));')

                await cur.execute(f'CREATE TABLE IF NOT EXISTS settings'
                                  f'(set_name VARCHAR(255),'
                                  f'set_content TEXT)')

    async def get_company_contacts_data(self):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute('SELECT * FROM settings WHERE set_name = "Address" OR set_name = "Phone" OR set_name = "Office Hours"')
                rows = await cur.fetchall()
                return rows

    async def add_new_chat(self, chat_id: str, chat_hash: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'INSERT INTO all_chats (chat_id, chat_hash) '
                                  f'VALUES ("{chat_id}", "{chat_hash}");')

    async def insert_msg(self, chat_id: str, author: str, msg_text: str, format_name: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'INSERT INTO all_messages (chat_id, format, author, msg_text, date_added) '
                                  f'VALUES ("{chat_id}","{format_name}", "{author}", "{msg_text}", "{datetime.datetime.utcnow()}");')

    async def add_client_name(self, chat_id: str, client_name: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'UPDATE all_chats SET client_name = "{client_name}" WHERE chat_id = "{chat_id}"')

    async def get_chat_history(self, chat_id: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'SELECT * FROM all_messages WHERE chat_id = "{chat_id}"')
                rows = await cur.fetchall()
                return rows if len(rows) > 0 else ('empty',)

    async def add_new_contact_data(self, chat_id: str, name: str, telephone: str, email: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'INSERT INTO all_contacts_data (chat_id, name, telephone, email) '
                                  f'VALUES ("{chat_id}", "{name}", "{telephone}", "{email}");')

    async def get_contact_data(self, chat_id: str):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'SELECT * FROM all_contacts_data WHERE chat_id = "{chat_id}"')
                rows = await cur.fetchall()
                return rows[0] if len(rows) > 0 else 'empty'

    async def get_all_chats(self):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute(f'SELECT chat_id FROM all_chats')
                rows = await cur.fetchall()
                rows = [row[0] for row in rows]
                return rows

    async def get_email_to(self):
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cur:
                await cur.execute('SELECT * FROM settings WHERE set_name = "AdminEmail"')
                rows = await cur.fetchall()
                return rows[0]


bot_base = AiDataBase()
