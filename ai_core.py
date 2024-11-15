from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores.faiss import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

from database import bot_base
import asyncio


load_dotenv()

# Задаем модель чата
chat_model = ChatOpenAI(model='gpt-3.5-turbo-1106', temperature=0)

# Формируем векторную базу данных на основе текстового документа
loader = TextLoader(file_path='company_info.txt', encoding='utf-8')
splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=500)
document = loader.load_and_split(text_splitter=splitter)
embedding = OpenAIEmbeddings()
vector_store = FAISS.from_documents(document, embedding=embedding)
store = vector_store.as_retriever(search_kwargs={'k': 3})
chat_history = []

prompt_text = """You are a manager of a company that deals with wholesale fuel supplies. Your task is to 
answer questions related to the activities of your company. Ignore questions that do not concern your company. 
The most important thing is that you already have the contact information of the clients you communicate with.
Also use context {context}. 
If the client writes any of this:
"I don't know"
"Don't know"
"I don't know"
"Don't know"
"Not sure"
"I'm not sure"
"I am not sure"
"Unsure"
"I am unsure" or another expression of not knowing the answer then just answer "no problem, we will have an account executive reach out to you and further assist you".
If you are asked any question about employment, then send this 
link https://www.ricochetfuel.com/contact-us/careers/ and say that all current vacancies can be found at this link."""


async def create_prompt():
    global prompt_text
    company_contact_data = await bot_base.get_company_contacts_data()
    company_contact_data = (f'Contact information: '
                            f'Address {company_contact_data[0][1]}, '
                            f'Phone {company_contact_data[1][1]}, '
                            f'Office Hours {company_contact_data[2][1]}')
    prompt_text += company_contact_data
    prompt = ChatPromptTemplate.from_messages([
        ('system', prompt_text),
        MessagesPlaceholder(variable_name='chat_history'),
        ('human', '{input}')
    ])
    # Формируем цепочку
    chain = create_stuff_documents_chain(llm=chat_model, prompt=prompt)
    retrieval_chain = create_retrieval_chain(store, chain)
    return retrieval_chain


# Делаем запрос
async def process_chat(user_input, chat_history_list):

    response = (await create_prompt()).invoke({
        'input': user_input,
        'chat_history': chat_history_list,
    })
    return response['answer']


def check_name(user_msg):
    model = ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        temperature=0.7,
    )

    prompt_for_name = ChatPromptTemplate.from_messages([
        ('system', 'Извлеки имя человека из сообщения если он там есть\nИнструкция форматирования:{format}'),
        ('human', '{input}')
    ])

    class Person(BaseModel):
        name: str = Field(description='the name of the person')

    parser = JsonOutputParser(pydantic_object=Person)
    chain_for_name = prompt_for_name | model | parser
    return chain_for_name.invoke({'input': user_msg,
                                  'format': parser.get_format_instructions()})


async def check_other_question(chat_his):
    model = ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        temperature=0,
    )

    prompt_for_check = ChatPromptTemplate.from_messages([
        ('system', 'Your task is to determine whether the person has any questions based on the history of '
                   'the correspondence. Answer only "yes" or "no" in JSON format. The presence of questions from a '
                   'person is considered to be the absence of an explicit denial of the presence of questions or the '
                   'presence of a question mark in the last message'
                   'Format instruction:{format}'),
        MessagesPlaceholder(variable_name='chat_history'),
    ])

    class Person(BaseModel):
        response: str = Field(description='the presence of questions in a person')

    parser = JsonOutputParser(pydantic_object=Person)
    chain_for_name = prompt_for_check | model | parser
    try:
        return chain_for_name.invoke({
                                      'chat_history': chat_his,
                                      'format': parser.get_format_instructions()
                                      })
    except OutputParserException as e:
        print(e)
        return e


async def time_for_communication(user_msg):
    model = ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        temperature=0.7,
    )

    prompt_for_name = ChatPromptTemplate.from_messages([
        ('system', 'You will be told the time when it is convenient for the person to be contacted, and you '
                   'must say that our manager will contact the person by this time. If the person does not want the '
                   'manager to contact him, then wish him a good day and say that you are always here and ready to help'),
        ('human', '{input}')
    ])

    chain_for_name = prompt_for_name | model
    return chain_for_name.invoke({'input': user_msg}).content


if __name__ == '__main__':
    async def start_up():
        await bot_base.create_pool()
        while True:
            user = input('You: ')
            if user != 'exit':
                res = await process_chat(user, chat_history)
                print(res)
                chat_history.append(HumanMessage(content=user))
                # a = await check_other_question(chat_history)
                chat_history.append(AIMessage(content=res))
                # a = await time_for_communication(user)
                # print(a)
            else:
                break

    asyncio.run(start_up())
