import mongoengine
# from pyromod import listen, Client as PyromodClient
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
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
    db = mongoengine.connect(host='mongodb://mongo:27017/valery?uuidRepresentation=standard')
    db.drop_database('valery')


@pytest.fixture
def chatbot_id():
    VALERY_BOT_CHAT_ID = '@ValeryAIBot'
    return VALERY_BOT_CHAT_ID


@pytest.fixture
def user_id():
    USER_ID = 'yell0w4x'
    return USER_ID


async def wait_for_message(telegram_client):
    loop = asyncio.get_running_loop()
    message_arrived = loop.create_future()
    async def on_message(client, message):
        message_arrived.set_result(message)

    handler = telegram_client.add_handler(MessageHandler(on_message))
    message = await message_arrived
    telegram_client.remove_handler(*handler)
    return message


@pytest.mark.anyio
async def test_start_command_must_create_new_user(telegram_client, chatbot_id, user_id):
    await telegram_client.send_message(chatbot_id, '/start')
    message = await wait_for_message(telegram_client)
    assert message.text.startswith('Hi there! Pleased to meet you!')
    User.objects.get(username=user_id)


@pytest.mark.anyio
async def test_must_response_to_user_message(telegram_client, chatbot_id):
    await telegram_client.send_message(chatbot_id, 'Hi there')

    message = await wait_for_message(telegram_client)
    while message.text == '...':
        async for message in telegram_client.get_chat_history(chatbot_id, limit=1):
            if message.text != '...':
                break
            await asyncio.sleep(1)

    assert message.text.startswith('Hello!') or message.text.startswith('Greetings!')


@pytest.mark.anyio
async def test_must_show_available_chat_modes_and_select_chat_mode(telegram_client, chatbot_id, user_id):
    await telegram_client.send_message(chatbot_id, '/mode')
    message = await wait_for_message(telegram_client)
    assert message.text.startswith('Select chat mode')

    await telegram_client.request_callback_answer(
        chat_id=message.chat.id, message_id=message.id, callback_data='set_chat_mode|code_assistant')
    user = User.objects.get(username=user_id)
    message = await wait_for_message(telegram_client)
    assert message.text.startswith("👩🏼‍💻 Hi, I'm Code Assistant")
    assert user.chat_mode == 'code_assistant'   


@pytest.mark.anyio
async def test_new_dialog_command(telegram_client, chatbot_id, user_id):
    await telegram_client.send_message(chatbot_id, 'Hi there')
    message = await wait_for_message(telegram_client)
    user = User.objects.get(username=user_id)
    assert len(user.current_dialog)

    await telegram_client.send_message(chatbot_id, '/new')
    message = await wait_for_message(telegram_client)
    assert message.text.startswith('Starting new dialog')
    user = User.objects.get(username=user_id)
    assert len(user.current_dialog) == 0
