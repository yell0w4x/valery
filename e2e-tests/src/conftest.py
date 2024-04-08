import logging
import pytest
import os


_logger = logging.getLogger(__name__)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def pytest_addoption(parser):
    parser.addoption('--session-name', action='store', default=os.environ.get('VALERY_BOT_SESSION_NAME', None), 
        help='Pyrogram session name to interact with the bot')
    parser.addoption('--chatbot-id', action='store', default=os.environ.get('VALERY_BOT_CHAT_ID', None), 
        help='Telegram chatbot id to use in tests')


def get_option(request, name):
    value = request.config.getoption(name)
    _logger.debug(f'Option: {name}={value}')
    return value


@pytest.fixture(scope='session')
def session_name(request):
    value = get_option(request, '--session-name')
    assert value is not None, 'VALERY_BOT_SESSION_NAME or --session-name is required'
    return value


@pytest.fixture(scope='session')
def chatbot_id(request):
    value = get_option(request, '--chatbot-id')
    value is not None, 'VALERY_BOT_CHAT_ID or --chatbot-id is required'
    return value


@pytest.fixture
def user_id(session_name):
    return session_name
