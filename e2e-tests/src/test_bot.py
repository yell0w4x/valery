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
    VALERY_BOT_CHAT_ID = '@ValeryAITestBot'
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


def expect_message(telegram_client):
    loop = asyncio.get_running_loop()
    message_arrived = loop.create_future()
    async def on_message(client, message):
        message_arrived.set_result(message)
        telegram_client.remove_handler(*handler)

    handler = telegram_client.add_handler(MessageHandler(on_message))
    return message_arrived


async def wait_for_placeholder_changes(telegram_client, message, chatbot_id):
    while message.text == '...':
        async for message in telegram_client.get_chat_history(chatbot_id, limit=1):
            if message.text != '...':
                return message
            await asyncio.sleep(1)
    else:
        return message


@pytest.mark.anyio
async def test_start_command_must_create_new_user(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, '/start')
    message = await message_arrived
    assert message.text.startswith('Hi there! Pleased to meet you!') or \
        message.text.startswith('Select chat mode')
    User.objects.get(username=user_id)


@pytest.mark.anyio
async def test_help_command(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, '/help')
    message = await message_arrived
    assert '👉 /start – Get started' in message.text
    User.objects.get(username=user_id)


@pytest.mark.anyio
async def test_must_response_to_user_message(telegram_client, chatbot_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Hi there')

    message = await message_arrived
    message = await wait_for_placeholder_changes(telegram_client, message, chatbot_id)
    assert message.text.startswith('Hello!') or message.text.startswith('Greetings!')


@pytest.mark.anyio
async def test_must_show_available_chat_modes_then_select_code_assistant_chat_mode_and_ask_to_write_code(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, '/mode')
    message = await message_arrived
    assert message.text.startswith('Select chat mode')

    message_arrived = expect_message(telegram_client)
    await telegram_client.request_callback_answer(
        chat_id=message.chat.id, message_id=message.id, callback_data='set_chat_mode|code_assistant')
    message = await message_arrived
    user = User.objects.get(username=user_id)
    assert message.text.startswith("👩🏼‍💻 Hi, I'm Code Assistant")
    assert user.chat_mode == 'code_assistant'

    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Write smallest python example code')
    message = await message_arrived
    assert not message.text.startswith('Something went wrong')


@pytest.mark.anyio
async def test_new_dialog_command(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Hi there')
    message = await message_arrived
    user = User.objects.get(username=user_id)
    while len(user.current_dialog) == 0:
        user = User.objects.get(username=user_id)
        await asyncio.sleep(1)

    # message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, '/new')
    message = await wait_for_message(telegram_client)
    # message = await message_arrived
    print(f'{message=}')
    assert message.text.startswith('Starting new dialog')
    user = User.objects.get(username=user_id)
    assert len(user.current_dialog) == 0


@pytest.mark.anyio
async def test_unable_to_send_two_messages_in_a_row_without_getting_reply_to_first_one(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Hi there!')
    await telegram_client.send_message(chatbot_id, 'How are you?')
    message = await message_arrived
    assert 'Please wait for a reply' in message.text

    message_arrived = wait_for_message(telegram_client)
    message = await message_arrived
    assert 'Hello!' in message.text


@pytest.mark.anyio
@pytest.mark.parametrize('command', ['/start', '/new', '/mode'])
async def test_unable_to_send_command_if_message_reply_pending(telegram_client, chatbot_id, user_id, command):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Hi there!')
    await telegram_client.send_message(chatbot_id, command)
    message = await message_arrived
    assert 'Please wait for a reply' in message.text
    message = await wait_for_message(telegram_client)


@pytest.mark.anyio
async def test_must_forbid_to_select_chat_mode_if_message_pending(telegram_client, chatbot_id, user_id):
    message_arrived = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, '/mode')
    message_reply = await message_arrived
    assert message_reply.text.startswith('Select chat mode')

    hi_reply_expect = expect_message(telegram_client)
    await telegram_client.send_message(chatbot_id, 'Hi there!')
    await telegram_client.request_callback_answer(
        chat_id=message_reply.chat.id, message_id=message_reply.id, callback_data='set_chat_mode|code_assistant')
    message = await hi_reply_expect
    assert 'Please wait for a reply' in message.text
    message = await wait_for_message(telegram_client)


@pytest.mark.anyio
@pytest.mark.parametrize('fn, expected', [('hi-there.oga', 'Hi there'), ('silence.ogg', '<Nothing>')])
async def test_voice(telegram_client: Client, chatbot_id, user_id, fn, expected):
    with open(fn, 'rb') as f:
        print(type(f), f.name)
        message_arrived = expect_message(telegram_client)
        await telegram_client.send_voice(chatbot_id, voice=f)
        message = await message_arrived
        assert expected in message.text
        await wait_for_message(telegram_client)
