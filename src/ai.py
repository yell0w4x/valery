import openai
import logging


_logger = logging.getLogger(__name__)


class Assistant:
    SUPPORED_MODELS = 'meta-llama/Llama-2-70b-chat-hf',
    COMPLETION_OPTIONS = dict(temperature=0.7, 
                              max_tokens=1000, 
                              top_p=1, 
                              frequency_penalty=0, 
                              presence_penalty=0)

    def __init__(self, client, config, model='meta-llama/Llama-2-70b-chat-hf'):
        self.__client = client
        self.__config = config
        self.__model = model


    async def send_message(self, message, message_history, chat_mode):
        client = self.__client
        reply = await client.chat.completions.create(
            model='meta-llama/Llama-2-70b-chat-hf', 
            messages=self.__adapt_message_history(message, message_history, chat_mode),
            stream=False,
            **self.COMPLETION_OPTIONS
        )
        _logger.debug(f'{reply=}')
        response = reply.choices[0].message.content
        usage_stat = reply.usage
        return response, usage_stat


    async def send_message_stream(self, message, message_history, chat_mode):
        client = self.__client
        messages = self.__adapt_message_history(message, message_history, chat_mode)
        gen = await client.chat.completions.create(
            model='meta-llama/Llama-2-70b-chat-hf', 
            messages=messages,
            stream=True,
            **self.COMPLETION_OPTIONS
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
        return ([dict(role='system', content=prompt)] + 
                [dict(role=item.role, content=item.content) for item in message_history] +
                [dict(role='user', content=message)])
