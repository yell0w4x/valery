import openai
import logging


_logger = logging.getLogger(__name__)


class AssistantError(RuntimeError):
    pass


def _adapt_message_history(context_limit, prompt, message_history, message):
    def get_token_num(text):
        TOKEN_FACTOR = 1.5
        return int(len(text) * 1.5)

    context_limit -= get_token_num(prompt) + get_token_num(message)
    if context_limit < 0:
        raise AssistantError('Context limit exceeded')

    rmh = list(reversed(message_history))

    i = 0
    for i, item in enumerate(zip(rmh[::2], rmh[1::2])):
        assistant, user = item
        token_num = get_token_num(assistant.content) + get_token_num(user.content)
        if token_num > context_limit:
            break
        context_limit -= token_num

    return ([dict(role='system', content=prompt)] + 
            [dict(role=el.role, content=el.content) for item in reversed(list(zip(rmh[::2], rmh[1::2]))[:i]) for el in reversed(item)] +
            [dict(role='user', content=message)])


class Assistant:
    SUPPORED_MODELS = 'meta-llama/Llama-2-70b-chat-hf',
    COMPLETION_OPTIONS = dict(temperature=0.7, 
                              max_tokens=1000, 
                              top_p=1, 
                              frequency_penalty=0, 
                              presence_penalty=0)

    def __init__(self, client, config):
        self.__client = client
        self.__config = config
        self.__model = model = config['model']
        self.__context_limit = config['models'][model]['context_limit']
        self.__completion_opts = config['models'][model]['completion_options']


    async def send_message(self, message, message_history, chat_mode):
        client = self.__client
        reply = await client.chat.completions.create(
            model=self.__model,
            messages=self.__adapt_message_history(message, message_history, chat_mode),
            stream=False,
            **self.__completion_opts
        )
        _logger.debug(f'{reply=}')
        response = reply.choices[0].message.content
        usage_stat = reply.usage
        return response, usage_stat


    async def send_message_stream(self, message, message_history, chat_mode):
        client = self.__client
        messages = self.__adapt_message_history(message, message_history, chat_mode)
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
                yield delta.content
                # # n_input_tokens, n_output_tokens = self._count_tokens_from_messages(messages, answer, model=self.model)
                # # n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)
        else:
            yield None


    def __adapt_message_history(self, message, message_history, chat_mode):
        prompt = self.__config['chat_modes'][chat_mode]['prompt_start']
        return _adapt_message_history(self.__context_limit, prompt, message_history, message)
