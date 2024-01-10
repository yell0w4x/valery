import ai
from repository import Dialog

import pytest
from collections import namedtuple
import logging


logging.basicConfig(level=logging.DEBUG)


def content_gen(words_num, word='word'):
    return ' '.join(list(f'{word}{i}' for i in range(1, words_num + 1)))


@pytest.fixture
def context_limit():
    LIMIT = 128
    return LIMIT


@pytest.fixture
def prompt(prompt_size):
    return content_gen(prompt_size, word='prompt')


USER_LEN = 10
ASSITANT_LEN = 15


Item = namedtuple('Item', ['role', 'content'])


@pytest.fixture
def message_history():
    def history_gen(n):
        for i in range(1, n + 1):
            yield (Item(role='user', content=content_gen(USER_LEN, word=f'{i}_user_word')), 
                   Item(role='assistant', content=content_gen(ASSITANT_LEN, word=f'{i}_assistant_word')))

    return [el for item in history_gen(10) for el in item]


@pytest.fixture
def message():
    return 'Hi there'


@pytest.mark.parametrize('prompt_size', [20])
def test_adapt_message_history_must_return_limited_to_context_size_history(prompt, context_limit, message_history, message):
    exptected = [
        dict(role='system', content=prompt),
        dict(role='user', content=content_gen(USER_LEN, word=f'9_user_word')),
        dict(role='assistant', content=content_gen(ASSITANT_LEN, word=f'9_assistant_word')),
        dict(role='user', content=content_gen(USER_LEN, word=f'10_user_word')),
        dict(role='assistant', content=content_gen(ASSITANT_LEN, word=f'10_assistant_word')),
        dict(role='user', content=message),
    ]

    assert exptected == ai._adapt_message_history(context_limit, prompt, message_history, message)


@pytest.mark.parametrize('prompt_size', [20])
def test_adapt_message_history_limit_exceeded_by_first_message(prompt, context_limit, message):
    message_history = [Item(role='user', content=content_gen(50, word=f'user_word')), 
                       Item(role='assistant', content=content_gen(50, word=f'assistant_word'))]

    exptected = [
        dict(role='system', content=prompt),
        dict(role='user', content=message),
    ]

    assert exptected == ai._adapt_message_history(context_limit, prompt, message_history, message)


@pytest.mark.parametrize('prompt_size', [20])
def test_adapt_message_history_single_element_in_history(prompt, context_limit, message):
    message_history = [Item(role='user', content=content_gen(USER_LEN, word=f'user_word')), 
                       Item(role='assistant', content=content_gen(ASSITANT_LEN, word=f'assistant_word'))]

    exptected = [
        dict(role='system', content=prompt),
        dict(role='user', content=content_gen(USER_LEN, word=f'user_word')),
        dict(role='assistant', content=content_gen(ASSITANT_LEN, word=f'assistant_word')),
        dict(role='user', content=message),
    ]

    assert exptected == ai._adapt_message_history(context_limit, prompt, message_history, message)


@pytest.mark.parametrize('prompt_size', [100])
def test_adapt_message_history_must_raise_if_prompt_and_message_exceeds_limit(prompt, context_limit, message_history, message):
    with pytest.raises(ai.AssistantError):
        ai._adapt_message_history(context_limit, prompt, message_history, message)
