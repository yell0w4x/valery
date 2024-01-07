from repository import Dialog

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    filters
)
from telegram.constants import ParseMode, ChatAction
from telegram import (
    Message,
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
import telegram

from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from pydub import AudioSegment

from datetime import datetime, timezone
import logging
import asyncio
from contextlib import contextmanager
from io import BytesIO
from functools import wraps
import traceback
import html
import json
from tempfile import NamedTemporaryFile


HELP_MESSAGE = """Commands:
👉 /start – Get started
👉 /new – Start new dialog
👉 /mode – Select chat mode
👉 /cancel – Cancel pending reply 
👉 /help – Show help

🎤 You can send <b>Voice Messages</b> instead of text
"""

HELP_GROUP_CHAT_MESSAGE = """You can add bot to any <b>group chat</b> to help and entertain its participants!

Instructions (see <b>video</b> below):
1. Add the bot to the group chat
2. Make it an <b>admin</b>, so that it can see messages (all other rights can be restricted)
3. You're done!

To get a reply from the bot in the chat – @ <b>tag</b> it or <b>reply</b> to its message.
For example: "{bot_username} write a poem about Telegram"
"""


_logger = logging.getLogger(__name__)


def escape_markdown(text):
    # SPECIAL_CHARS = '\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '<', '&', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    SPECIAL_CHARS = '\\', '[', ']', '(', ')', '>', '<', '&', '#', '+', '-', '=', '|', '{', '}', '.', '!'

    for char in SPECIAL_CHARS:
        text = text.replace(char, f'\\{char}')

    return text


async def transcribe_audio(api_key, buffer):
    from deepgram import DeepgramClientOptions

    deepgram = DeepgramClient(api_key, config=DeepgramClientOptions(verbose=logging.DEBUG))
    options = PrerecordedOptions(
        model="nova-2",
        # model='whisper-medium',
        smart_format=True,
        language='en'
        # summarize="v2",
    )
    payload = dict(buffer=buffer)
    return await deepgram.listen.asyncprerecorded.v('1').transcribe_file(payload, options)


def pending_protect(method):
    @wraps(method)
    async def wrapper(self, update, *args, **kwargs):
        if not isinstance(update, Update):
            raise ValueError('The first arg of protected callable must have an Update type')

        if await self._is_reply_pending(update):
            _logger.debug('Reply peding, do not execute handler')
            return

        await method(self, update, *args, **kwargs)

    return wrapper


def split_text(text, chunk_size):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


def format_exc(exc, update):
    tb_list = traceback.format_exception(None, exc, exc.__traceback__)
    tb_str = html.escape("".join(tb_list))
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    update_json_str = html.escape(json.dumps(update_str, indent=4, ensure_ascii=False))

    s = (
        "An exception was raised while handling an update\n"
        f"<pre>{update_json_str}</pre>\n"
        f"<pre>{tb_str}</pre>"
    )
    LIMIT = 4096
    if len(s) <= LIMIT:
        return [s]

    return (['An exception was raised while handling an update\n'] +
            [f'<pre>{s}</pre>\n' for s in split_text(update_json_str, LIMIT - len('<pre></pre>\n'))] +
            [f'<pre>{s}</pre>\n' for s in split_text(tb_str, LIMIT - len('<pre></pre>\n'))])
    

def log_handler(logger):
    def decorator(method):
        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            if logger.getEffectiveLevel() == logging.DEBUG:
                update: Update = args[0]
                logger.debug(f'{method.__name__}: Chat [{update.effective_chat}]; Message [{update.effective_message}]; User [{update.effective_user}]')
            return await method(self, *args, **kwargs)

        return wrapper

    return decorator


def get_ogg_duration_secs(file):
    pos = file.tell()
    try:
        duration = AudioSegment.from_ogg(file).duration_seconds
    finally:
        file.seek(pos)

    return duration


class Bot:
    def __init__(self, config, telegram_app_builder, repository, assistant_factory):
        _logger.debug(f'Creating bot [{config=}]')
        self.__config = config
        app = (telegram_app_builder
            .token(config['telegram_token'])
            .concurrent_updates(True)
            .rate_limiter(AIORateLimiter(max_retries=5))
            .http_version("1.1")
            .get_updates_http_version("1.1")
            .post_init(self.__post_init)
            .build()
        )
        self.__app = app
        self.__repo = repository
        self.__assistant_factory = assistant_factory
        self.__tasks = dict()
        self.__locks = dict()
        app.add_handler(CommandHandler("start", self.__start_handler, filters=filters.COMMAND))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.__message_handler))

        app.add_handler(CommandHandler("mode", self.__show_chat_modes_handler, filters=filters.COMMAND))
        app.add_handler(CallbackQueryHandler(self.__show_chat_modes_callback_handler, pattern="^show_chat_modes"))
        app.add_handler(CallbackQueryHandler(self.__set_chat_mode_handler, pattern="^set_chat_mode"))

        app.add_handler(CommandHandler("new", self.__new_dialog_handler, filters=filters.COMMAND))
        app.add_handler(MessageHandler(filters.VOICE, self.__voice_message_handler))

        app.add_handler(CommandHandler("help", self.__help_handler, filters=filters.COMMAND))
        app.add_error_handler(self.__error_handler)


    def run(self):
        self.__app.run_polling()


    async def __error_handler(self, update: Update, context: CallbackContext) -> None:
        _logger.error('Error has occurred', exc_info=context.error)
        if update.effective_chat is None:
            _logger.debug(f'Nothing to send to as {update.effective_chat=}')
            return

        try:
            message = format_exc(context.error, update)

            # split text into multiple messages due to 4096 character limit
            for message_chunk in message:
                try:
                    await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
                except telegram.error.BadRequest as e:
                    # answer has invalid characters, so we send it without parse_mode
                    _logger.error('Error has occurred', exc_info=e)
                    await context.bot.send_message(update.effective_chat.id, message_chunk)
        except BaseException as e:
            _logger.error('Error has occurred', exc_info=e)
            await context.bot.send_message(update.effective_chat.id, "Some error in error handler")


    @log_handler(_logger)
    @pending_protect
    async def __voice_message_handler(self, update: Update, context: CallbackContext):
        self.__register_user(update.message.from_user)

        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        
        buf = BytesIO()
        await voice_file.download_to_memory(buf)
        buf.name = "voice.oga"  # file extension is required
        buf.seek(0)
        duration_seconds = get_ogg_duration_secs(buf)
        _logger.debug(f'Got audio file: [{duration_seconds=} secs]')

        response = await transcribe_audio(self.__config['deepgram_token'], buf)
        _logger.debug(f'Voice transcription [{response}]')
        text = str(response.results.channels[0].alternatives[0].transcript)
        await update.message.reply_text(f'🎙️ Got it\n{text}', parse_mode=ParseMode.HTML)
        await self.__message_handler(update, context, alt_text=text)


    @log_handler(_logger)
    @pending_protect
    async def __start_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        self.__register_user(tg_user)

        reply_text = "Hi there! Pleased to meet you! Feel free to choose preset or supply your own 🤖\n\n"
        reply_text += HELP_MESSAGE

        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
        await self.__show_chat_modes_handler(update, context)


    @log_handler(_logger)
    @pending_protect
    async def __help_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        self.__register_user(tg_user)
        await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


    @log_handler(_logger)
    @pending_protect
    async def __new_dialog_handler(self, update: Update, context: CallbackContext):
        user = self.__register_user(update.message.from_user)
        user.current_dialog = list()
        self.__repo.put_user(user)
        await update.message.reply_text('Starting new dialog...')
        welcome_message = self.__config['chat_modes'][user.chat_mode]['welcome_message']
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)


    @log_handler(_logger)
    @pending_protect
    async def __message_handler(self, update: Update, context: CallbackContext, alt_text=None):
        tg_user = update.message.from_user
        user = self.__register_user(tg_user)

        _logger.debug(f'Message arrived [{alt_text or update.message.text}]')

        async with self.__locks[tg_user.id]:
            with self.__task_man(tg_user.id, update.message, user.current_dialog, user.chat_mode, alt_text) as task:
                try:
                    await task
                except asyncio.CancelledError:
                    await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
                except BaseException as e:
                    error_text = f"Something went wrong during completion. Reason: [{e!r}]"
                    _logger.error(error_text, exc_info=e)

                    message = format_exc(e, update)
                    await update.message.reply_text(f'{error_text}\n\n{message}', parse_mode=ParseMode.HTML)


    @contextmanager
    def __task_man(self, user_id, message, message_history, chat_mode, alt_text):
        task = asyncio.create_task(self.__message_handler_task(
            self.__repo.get_user(user_id), message, message_history, chat_mode, alt_text))
        tasks = self.__tasks
        tasks[user_id] = task
        try:
            yield task
        finally:
            if user_id in tasks:
                del tasks[user_id]


    def __parse_mode(self, chat_mode):
        config = self.__config
        return dict(html=ParseMode.HTML, 
                    markdown=ParseMode.MARKDOWN,
                    markdown_v2=ParseMode.MARKDOWN_V2).get(config['chat_modes'][chat_mode]['parse_mode'], 
                                                           ParseMode.HTML)


    async def __message_handler_task(self, user, message, message_history, chat_mode, alt_text):
        def put_dialog_item(user, message_text, response):
            user.current_dialog.append(Dialog(role='user', content=message_text))
            user.current_dialog.append(Dialog(role='assistant', content=response))
            self.__repo.put_user(user)

        assistant = self.__assistant_factory()
        config = self.__config
        parse_mode = self.__parse_mode(chat_mode)
        is_markdown = parse_mode.lower().startswith('markdown')
        # can't stream markdown as telegram fails with parsing errors because of 
        # it unable to find closing pair of starting markup symbol
        is_code_assistant = chat_mode == 'code_assistant'
        message_text = alt_text or message.text
        # message_text = message.text

        if config['message_streaming'] and not is_code_assistant:
            placeholder_message = await message.reply_text('...')
            await message.reply_chat_action(action=ChatAction.TYPING)
            prev_answer = ''
            whole_answer = ''
            async for answer in assistant.send_message_stream(message_text, message_history, chat_mode):
                limit = config['stream_update_chars']

                if answer is not None:
                    whole_answer += escape_markdown(answer) if is_markdown else answer

                if answer is not None and abs(len(whole_answer) - len(prev_answer)) < limit:
                    continue

                if answer is None:
                    put_dialog_item(user, message_text, whole_answer)

                _logger.debug(f'{prev_answer=}, {placeholder_message=}, {parse_mode=}')
                try:
                    await self.__app.bot.edit_message_text(whole_answer, 
                                                           chat_id=placeholder_message.chat_id, 
                                                           message_id=placeholder_message.message_id, 
                                                           parse_mode=parse_mode)
                except telegram.error.BadRequest as e:
                    _logger.warn(f'BadRequest [{e}]')
                    if str(e).startswith("Message is not modified"):
                        continue
                    else:
                        await self.__app.bot.edit_message_text(whole_answer, 
                                                               chat_id=placeholder_message.chat_id, 
                                                               message_id=placeholder_message.message_id, 
                                                               parse_mode=parse_mode)

                await asyncio.sleep(0.01)
                prev_answer = whole_answer
        else:
            await message.reply_chat_action(action=ChatAction.TYPING)
            resp, usage = await assistant.send_message(message_text, message_history, chat_mode)
            put_dialog_item(user, message_text, resp)

            if is_markdown:
                resp = escape_markdown(resp)

            await message.reply_text(resp, parse_mode=parse_mode)


    def __register_user(self, tg_user):
        if tg_user.id not in self.__locks:
            self.__locks[tg_user.id] = asyncio.Semaphore()

        now_utc = datetime.now(tz=timezone.utc)
        repo = self.__repo
        user = repo.get_user(tg_user.id)
        user.last_seen = now_utc
        if user.first_seen is None:
            _logger.debug(f'Add new user')
            user.first_seen = now_utc
            user.username = tg_user.username
            user.first_name=tg_user.first_name
            user.last_name= tg_user.last_name

        repo.put_user(user)
        return user


    @log_handler(_logger)
    @pending_protect
    async def __show_chat_modes_handler(self, update: Update, context: CallbackContext):
        self.__register_user(update.message.from_user)
        text, reply_markup = self.__get_chat_mode_menu()
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


    @log_handler(_logger)
    @pending_protect
    async def __show_chat_modes_callback_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.__register_user(query.from_user)

        await query.answer()

        page_index = int(query.data.split('|')[1])
        if page_index < 0:
            return

        text, reply_markup = get_chat_mode_menu(page_index)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except telegram.error.BadRequest as e:
            _logger.error(f'Edit message error [{e!r}]')


    @log_handler(_logger)
    @pending_protect
    async def __set_chat_mode_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        user = self.__register_user(query.from_user)

        await query.answer()

        chat_mode = query.data.split("|")[1]

        user.chat_mode = chat_mode
        user.current_dialog = list()
        self.__repo.put_user(user)
        config = self.__config

        await context.bot.send_message(
            update.callback_query.message.chat.id,
            f"{config['chat_modes'][chat_mode]['welcome_message']}",
            parse_mode=ParseMode.HTML
        )


    def __get_chat_mode_menu(self, page_index = 0):
        config = self.__config
        n_chat_modes_per_page = config['n_chat_modes_per_page']
        text = f"Select <b>chat mode</b> ({len(config['chat_modes'])} modes available):"

        # buttons
        chat_mode_keys = list(config['chat_modes'].keys())
        page_chat_mode_keys = chat_mode_keys[page_index * n_chat_modes_per_page : (page_index + 1) * n_chat_modes_per_page]

        keyboard = list()
        for chat_mode_key in page_chat_mode_keys:
            name = config['chat_modes'][chat_mode_key]['name']
            keyboard.append([InlineKeyboardButton(name, callback_data=f"set_chat_mode|{chat_mode_key}")])

        # pagination
        if len(chat_mode_keys) > n_chat_modes_per_page:
            is_first_page = page_index == 0
            is_last_page = (page_index + 1) * n_chat_modes_per_page >= len(chat_mode_keys)

            if is_first_page:
                keyboard.append([
                    InlineKeyboardButton("»", callback_data=f"show_chat_modes|{page_index + 1}")
                ])
            elif is_last_page:
                keyboard.append([
                    InlineKeyboardButton("«", callback_data=f"show_chat_modes|{page_index - 1}"),
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("«", callback_data=f"show_chat_modes|{page_index - 1}"),
                    InlineKeyboardButton("»", callback_data=f"show_chat_modes|{page_index + 1}")
                ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        return text, reply_markup


    async def _is_reply_pending(self, update: Update):
        is_message = hasattr(update, 'message') and isinstance(update.message, Message)
        # message = update.message if is_message else update.callback_query.message
        message = update.effective_message
        # user = update.message.from_user if is_message else update.callback_query.from_user
        user = update.effective_user
        assert user and message
        self.__register_user(user)

        if self.__locks[user.id].locked():
            if update.callback_query is not None:
                await update.callback_query.answer()

            text = "⏳ Please <b>wait</b> for a reply to the previous message\nOr you can /cancel it"
            await message.reply_text(text, reply_to_message_id=message.id, parse_mode=ParseMode.HTML)
            return True

        return False


    async def __post_init(self, app):
        _logger.info(f'Bot started')

        await app.bot.set_my_commands([
            BotCommand("/start", "Get started"),
            BotCommand("/new", "Start new dialog"),
            BotCommand("/mode", "Select chat mode"),
            BotCommand("/cancel", "Cancel pending reply"),
            # BotCommand("/settings", "Show settings"),
            BotCommand("/help", "Show help message"),
        ])
