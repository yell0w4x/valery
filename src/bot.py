from repository import Dialog
from money import Money

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

from datetime import datetime, timezone, timedelta
import logging
import asyncio
from contextlib import contextmanager, asynccontextmanager
from io import BytesIO
from functools import wraps
import traceback
import html
import json
from collections import namedtuple
import markdown


HELP_MESSAGE = """Commands:
👉 /start – Get started
👉 /new – Start new dialog
👉 /mode – Select chat mode
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

# fixme: figure out deepgram options
async def transcribe_audio(api_key, buffer, timeout, **options):
    payload = dict(buffer=buffer)
    client = DeepgramClient(api_key)    
    resp = await client.listen.asyncprerecorded.v('1').transcribe_file(payload, PrerecordedOptions(**options), timeout=timeout)
    _logger.debug(f'Voice transcription: [{resp=}]')
    return resp.results.channels[0].alternatives[0].transcript.strip(), resp.metadata.duration


PendingGuard = namedtuple('PendingGuard', ['lock', 'message_lock', 'messages'])


@contextmanager
def pending_message(guard, message):
    guard.messages.append(message)
    _logger.debug(f'Guard messages PUSH: [{len(guard.messages)=}, {message=}]')
    try:
        yield guard.lock
    finally:
        message = guard.messages.pop()
        _logger.debug(f'Guard messages POP: [{len(guard.messages)=}, {message=}]')


def pending_protect(method):
    @wraps(method)
    async def pending_guard(self, update, *args, **kwargs):
        if not isinstance(update, Update):
            raise ValueError('The first arg of protected callable must have an Update type')

        message = update.effective_message
        user = update.effective_user
        assert message and user

        self._register_user(user)
        guard = self._get_pending_guard(user.id)
        _logger.debug(f'Processing message: [{message.id=}; {message.text=}; {len(guard.messages)=};]')

        with pending_message(guard, message) as lock:
            _logger.debug(f'Penindg get IN: [{len(guard.messages)=}; {guard.messages=}]')
            if len(guard.messages) > 1:
                async with guard.message_lock:
                    if update.callback_query is not None:
                        await update.callback_query.answer()

                    text = "⏳ Please <b>wait</b> for a reply to the previous message\nOr you can /cancel it"
                    await message.reply_text(text, reply_to_message_id=message.id, parse_mode=ParseMode.HTML)
                    return

            async with lock:
                _logger.debug(f'Enter method: [{method.__name__}]')
                await method(self, update, *args, **kwargs)
                _logger.debug(f'Exit method: [{method.__name__}]')

        _logger.debug(f'Penindg get OUT: [{len(guard.messages)=}; {guard.messages=}]')

    return pending_guard


MESSAGE_LEN_LIMIT = 4096


def split_text(text, chunk_size=MESSAGE_LEN_LIMIT):
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
    if len(s) <= MESSAGE_LEN_LIMIT:
        return [s]

    return (['An exception was raised while handling an update\n'] +
            [f'<pre>{s}</pre>\n' for s in split_text(update_json_str, MESSAGE_LEN_LIMIT - len('<pre></pre>\n'))] +
            [f'<pre>{s}</pre>\n' for s in split_text(tb_str, MESSAGE_LEN_LIMIT - len('<pre></pre>\n'))])


def log_handler(logger):
    def decorator(method):
        @wraps(method)
        async def telegram_call_log(self, *args, **kwargs):
            if logger.getEffectiveLevel() == logging.DEBUG:
                update: Update = args[0]
                logger.debug(f'>> TELEGRAM CALL: {method.__name__}: Chat [{update.effective_chat}]; Message [{update.effective_message}]; User [{update.effective_user}]')
            return await method(self, *args, **kwargs)

        return telegram_call_log

    return decorator


def get_ogg_duration_secs(file):
    pos = file.tell()
    try:
        duration = AudioSegment.from_ogg(file).duration_seconds
    finally:
        file.seek(pos)

    return duration


def is_markdown(parse_mode):
    return parse_mode.lower().startswith('markdown')


async def send_reply(text, message, parse_mode=None):
    #fixme: Split code containig messages in smart way completing closing and opening markup symbols
    _logger.debug(f'Reply to user with: [{text=}]')
    try:
        for s in split_text(text):
            await message.reply_text(s, parse_mode=parse_mode)
    except telegram.error.BadRequest as e:
        _logger.warn(f'BadRequest: [{e!r}]', exc_info=e)
        for s in split_text(text.replace('\\', '') if is_markdown(parse_mode) else text):
            await message.reply_text(s)


def deposit(user, amount, repo):
    if not isinstance(amount, Money):
        ValueError('Given amount must be an instance of Money type')

    user.balance += amount
    repo.put_user(user)


def calc_transcribe_cost(duration, price):
    pass    


def is_command(text):
    return text.startswith('command')


def command_payload(text):
    return json.loads(text[len('command'):].strip())


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
        self.__pending_guards = dict()
        self.__timers = dict()
        self._register_user = self.__register_user
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
        config = self.__config

        if update.effective_chat is None:
            _logger.debug(f'Nothing to send to: [{update.effective_chat=}]')
            return

        debug = config['debug']
        if not debug:
            try:
                await context.bot.send_message(update.effective_chat.id, "Something went wrong")
            except BaseException as e:
                _logger.error('Error has occurred', exc_info=e)

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
        def put_duration(user, duration):
            user.stats.transcription_secs += duration
            self.__repo.put_user(user)

        user = self.__register_user(update.message.from_user)

        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        
        buf = BytesIO()
        await voice_file.download_to_memory(buf)
        buf.name = "voice.oga"  # file extension is required
        buf.seek(0)
        duration_seconds = get_ogg_duration_secs(buf)
        _logger.debug(f'Got audio file: [{duration_seconds=} secs]')

        config = self.__config
        model = config['deepgram_model']
        options = config['deepgram_models'][model]['options']
        text, duration = await transcribe_audio(config['deepgram_token'], buf.read(), 
                                                config['deepgram_timeout'], **options)
        if text:
            put_duration(user, duration)
            await update.message.reply_text(f'🎙️ Got it\n{text}', parse_mode=ParseMode.HTML)
            await self.__handle_message(update, context, alt_text=text)
        else:
            await update.message.reply_text(f'🎙️ Got it\n&lt;Nothing&gt;', parse_mode=ParseMode.HTML)
            await update.message.reply_text(f'Please say something', parse_mode=ParseMode.HTML)


    @log_handler(_logger)
    @pending_protect
    async def __start_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        self.__register_user(tg_user)

        reply_text = "Hi there! Pleased to meet you! Feel free to choose preset or supply your own 🤖\n\n"
        reply_text += HELP_MESSAGE

        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
        await self.__show_chat_modes(update, context)


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
        await self.__handle_message(update, context, alt_text)


    async def __handle_message(self, update: Update, context: CallbackContext, alt_text=None):
        tg_user = update.message.from_user
        user = self.__register_user(tg_user)

        _logger.debug(f'Message arrived: [{alt_text or update.message.text}, message.id={update.message.id if alt_text is None else None}]')

        with (self.__reply_task(tg_user, update.message, user.current_dialog, user.chat_mode, alt_text) as reply_task, 
              self.__typing_task(update.message) as typing_task):
            try:
                await asyncio.wait([reply_task, typing_task], return_when=asyncio.FIRST_COMPLETED)
                reply_task.result()
            except asyncio.CancelledError:
                await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
            except BaseException as e:
                error_text = f"Something went wrong during completion. Reason: [{e!r}]"
                _logger.error(error_text, exc_info=e)
                raise


    @contextmanager
    def __typing_task(self, message):
        task = asyncio.create_task(self.__bot_typing_task(message))
        try:
            yield task
        finally:
            if not task.cancelled():
                task.cancel()


    @contextmanager
    def __reply_task(self, tg_user, message, message_history, chat_mode, alt_text):
        user_id = tg_user.id
        task = asyncio.create_task(self.__message_handler_task(
            tg_user, message, message_history, chat_mode, alt_text))
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

    async def __message_handler_task(self, tg_user, message, message_history, chat_mode, alt_text):
        user_id = tg_user.id
        user = self.__repo.get_user(user_id)

        def put_dialog_item(user, message_text, response):
            user.current_dialog.append(Dialog(role='user', content=message_text))
            user.current_dialog.append(Dialog(role='assistant', content=response))
            self.__repo.put_user(user)

        def put_llm_stats(user, usage):
            user.stats.llm_total_tokens += usage.total_tokens
            self.__repo.put_user(user)

        assistant = self.__assistant_factory()
        config = self.__config
        parse_mode = self.__parse_mode(chat_mode)
        
        # can't stream markdown as telegram fails with parsing errors because of 
        # it unable to find closing pair of starting markup symbol
        is_code_assistant = chat_mode == 'code_assistant'
        message_text = alt_text or message.text
        assert message_text

        if config['message_streaming'] and not is_code_assistant:
            placeholder_message = await message.reply_text('...')
            await message.reply_chat_action(action=ChatAction.TYPING)
            prev_answer = ''
            whole_answer = ''
            async for answer in assistant.send_message_stream(message_text, message_history, chat_mode):
                limit = config['stream_update_chars']

                if answer is not None:
                    whole_answer += escape_markdown(answer) if is_markdown(parse_mode) else answer

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
                    _logger.warn(f'BadRequest: [{e!r}]', exc_info=e)
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
            resp, usage = await assistant.send_message(message_text, message_history, chat_mode)
            put_dialog_item(user, message_text, resp)
            put_llm_stats(user, usage)

            if is_markdown(parse_mode):
                resp = escape_markdown(resp)

            guard = self.__pending_guards[user.id]
            async with guard.message_lock:
                if is_command(resp):
                    payload = command_payload(resp)
                    if 'timer' in payload:
                        _logger.debug(f'Setting up timer: [{payload}]')
                        timer = payload['timer']
                        loop = asyncio.get_running_loop()
                        fire_in = timedelta(seconds=timer['fire_in'])
                        loop.call_later(fire_in.total_seconds(), asyncio.create_task, self.__timer_tracker_task(tg_user, timer))
                        await send_reply(f'Timer is set up: {fire_in}', message)
                else:
                    await send_reply(resp, message, parse_mode)


    async def __bot_typing_task(self, message):
        while True:
            await message.reply_chat_action(action=ChatAction.TYPING)
            await asyncio.sleep(6)


    async def __timer_tracker_task(self, user, timer):
        _logger.debug(f'Fire timer: [{timer}]')
        await user.send_message(f"Please don't forget about: {timer['text']}")


    def __register_user(self, tg_user):
        if tg_user.id not in self.__pending_guards:
            self.__pending_guards[tg_user.id] = PendingGuard(lock=asyncio.Lock(),
                                                             message_lock=asyncio.Lock(),
                                                             messages=list())

        now_utc = datetime.now(tz=timezone.utc)
        repo = self.__repo
        user = repo.get_user(tg_user.id)
        user.last_seen = now_utc
        if user.first_seen is None:
            _logger.debug('Add new user')
            user.first_seen = now_utc
            user.username = tg_user.username
            user.first_name=tg_user.first_name
            user.last_name= tg_user.last_name

        repo.put_user(user)
        return user


    @log_handler(_logger)
    @pending_protect
    async def __show_chat_modes_handler(self, update: Update, context: CallbackContext):
        await self.__show_chat_modes(update, context)


    async def __show_chat_modes(self, update: Update, context: CallbackContext):
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


    def _get_pending_guard(self, user_id):
        return self.__pending_guards[user_id]


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

