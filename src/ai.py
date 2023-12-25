import openai
import logging


_logger = logging.getLogger(__name__)


class Assistant:
    SUPPORED_MODELS = 'meta-llama/Llama-2-70b-chat-hf',
    COMPLETION_OPTIONS = dict(temperature=0.7, 
                              max_tokens=1000, 
                              top_p=1, 
                              frequency_penalty=0, 
                              presence_penalty=0, 
                              request_timeout=60.0)

    def __init__(self, client, config, model='meta-llama/Llama-2-70b-chat-hf'):
        _logger.debug(config)
        self.__client = client
        self.__config = config
        self.__model = model


    async def send_message(self, message, message_history, chat_mode):
        client = self.__client
        reply = await client.chat.completions.create(
            model = 'meta-llama/Llama-2-70b-chat-hf', 
            messages = self.__adapt_message_history(message, message_history, chat_mode),
            stream = False
        )
        _logger.debug(reply)
        response = reply.choices[0].message.content
        usage_stat = reply.usage
        return response, usage_stat


    def __adapt_message_history(self, message, message_history, chat_mode):
        prompt = self.__config['chat_modes'][chat_mode]['prompt_start']
        return ([dict(role='system', content=prompt)] + 
                [dict(role=item.role, content=item.content) for item in message_history] +
                [dict(role='user', content=message)])
