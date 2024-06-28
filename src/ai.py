import openai
import logging
from collections import Counter
import re
import math
import asyncio

_logger = logging.getLogger(__name__)


class AssistantError(RuntimeError):
    pass


async def _get_token_num(text):
    process = await asyncio.create_subprocess_exec('node', 'tokenizer/main.mjs', 
                                                    stdin=asyncio.subprocess.PIPE, 
                                                    stdout=asyncio.subprocess.PIPE, 
                                                    stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate(text.encode('utf-8'))
    if process.returncode != 0:
        raise AssistantError(text, stdout, stderr, process.returncode)

    _logger.debug(f'Tokenizer returned: [{stdout}]')
    return sum(map(int, stdout.decode().split()))


async def _adapt_message_history(context_limit, prompt, message_history, message):
    token_num = await _get_token_num(prompt) + await _get_token_num(message)
    total_tokens = token_num
    context_limit -= token_num
    if context_limit < 0:
        raise AssistantError('Context limit exceeded')

    rmh = list(reversed(message_history))

    def to_dict(item):
        return dict(role=item.role, content=item.content)

    dialog = list()
    for item in zip(rmh[1::2], rmh[::2]):
        user, assistant = item
        token_num = await _get_token_num(assistant.content) + await _get_token_num(user.content)
        if token_num > context_limit:
            break
        dialog += [to_dict(assistant), to_dict(user)]
        context_limit -= token_num
        total_tokens += token_num

    _logger.debug(f'Dialog total tokens: [{total_tokens=}]')
    dialog = list(reversed(dialog))
    return [dict(role='system', content=prompt)] + dialog + [dict(role='user', content=message)]


class Assistant:
    def __init__(self, client, config):
        self.__client = client
        self.__config = config
        self.__model = model = config['model']
        self.__context_limit = config['models'][model]['context_limit']
        self.__completion_opts = config['models'][model]['completion_options']


    async def send_message(self, message, message_history, chat_mode):
        client = self.__client
        messages = await self.__adapt_message_history(message, message_history, chat_mode)
        _logger.debug(f'Messages to be sent to model: [{messages=}]')
        reply = await client.chat.completions.create(
            model=self.__model,
            messages=messages,
            stream=False,
            **self.__completion_opts
        )
        _logger.debug(f'Reply from model: [{reply=}]')
        response = reply.choices[0].message.content.strip()
        usage_stat = reply.usage
        return response, usage_stat


    async def send_message_stream(self, message, message_history, chat_mode):
        client = self.__client
        messages = await self.__adapt_message_history(message, message_history, chat_mode)
        _logger.debug(f'Messages to be sent to model: [{messages=}]')
        gen = await client.chat.completions.create(
            model=self.__model,
            messages=messages,
            stream=True,
            **self.__completion_opts
        )

        async for item in gen:
            _logger.debug(f'{item=}')
            delta = item.choices[0].delta
            if hasattr(delta, 'content') and delta.content is not None:
                yield delta.content.strip()
                # # n_input_tokens, n_output_tokens = self._count_tokens_from_messages(messages, answer, model=self.model)
                # # n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)
        else:
            yield None


    async def __adapt_message_history(self, message, message_history, chat_mode):
        prompt = self.__config['chat_modes'][chat_mode]['prompt_start']
        return await _adapt_message_history(self.__context_limit, prompt, message_history, message)
