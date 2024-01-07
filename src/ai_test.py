import ai

import pytest
from collections import namedtuple


@pytest.fixture
def context_limit():
    return 128


@pytest.fixture
def prompt(prompt_size):
    return 'x' * prompt_size


USER_LEN = 10
ASSITANT_LEN = 15


Item = namedtuple('Item', ['role', 'content'])


@pytest.fixture
def message_history():
    def history_gen(n):
        i = 0
        while i < n:
            yield (Item(role='user', content=f'{i}'*USER_LEN), 
                   Item(role='assistant', content=f'{i}'*ASSITANT_LEN))
            i += 1

    return [el for item in history_gen(10) for el in item]


@pytest.fixture
def message():
    return 'Hi there!'


@pytest.mark.parametrize('prompt_size', [20])
def test_adapt_message_history_must_return_limited_to_context_size_history(prompt, context_limit, message_history, message):
    exptected = [
        dict(role='system', content=prompt),
        dict(role='user', content='8'*USER_LEN),
        dict(role='assistant', content='8'*ASSITANT_LEN),
        dict(role='user', content='9'*USER_LEN),
        dict(role='assistant', content='9'*ASSITANT_LEN),
        dict(role='user', content=message),
    ]

    assert exptected == ai._adapt_message_history(context_limit, prompt, message_history, message)


@pytest.mark.parametrize('prompt_size', [100])
def test_adapt_message_history_must_raise_if_prompt_and_message_exceeds_limit(prompt, context_limit, message_history, message):
    with pytest.raises(ai.AssistantError):
        ai._adapt_message_history(context_limit, prompt, message_history, message)
