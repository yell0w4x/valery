import mongoengine
# from pyromod import listen, Client as PyromodClient
from pyrogram import Client, filters
import pytest
import time
import asyncio

from repository import User


@pytest.fixture
def anyio_backend():
    return 'asyncio'
    

@pytest.fixture
def session_name():
    return 'yellow4x'


@pytest.fixture
async def telegram_client(session_name):
    client = Client(session_name, workdir='/test')
    async with client:
        yield client


@pytest.fixture(autouse=True)
def mongo_connect():
    mongoengine.connect(host='mongodb://mongo:27017/valery?uuidRepresentation=standard')


VALERY_BOT_CHAT_ID = '@ValeryAIBot'


@pytest.mark.anyio
async def test_start_command_must_create_new_user(telegram_client):
    await telegram_client.send_message(VALERY_BOT_CHAT_ID, '/start')

    loop = asyncio.get_running_loop()
    message_arrived = loop.create_future()
    async def on_message(client, message):
        message_arrived.set_result(message)

    telegram_client.on_message(filters.all)(on_message)
    message = await message_arrived
    assert message.text.startswith('Hi there! Pleased to meet you!')
    User.objects.get(username='yell0w4x')



# async def message_waiting_task():
#     loop = asyncio.get_running_loop()
#     message_arrived = loop.create_future()
#     async def on_message(client, message):
#         message_arrived.set_result(message)

#     telegram_client.on_message(filters.all)(on_message)
#     response = await message_arrived
#     print(response)

# async def message_sending_task():
#     await telegram_client.send_message(VALERY_BOT_CHAT_ID, '/start')

# await asyncio.gather(message_waiting_task(), message_sending_task())
