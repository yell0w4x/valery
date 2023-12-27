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
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
import telegram

from datetime import datetime, timezone
import logging
import asyncio
from contextlib import contextmanager


HELP_MESSAGE = """Commands:
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
⚪ /settings – Show settings
⚪ /help – Show help

🎨 Generate images from text prompts in <b>👩‍🎨 Artist</b> /mode
👥 Add bot to <b>group chat</b>: /help_group_chat
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


class Bot:
    def __init__(self, config, telegram_app_builder, telegram_token, repository, assistant_factory):
        _logger.debug(f'Creating bot [{telegram_token=}]')
        self.__config = config
        app = (telegram_app_builder
            .token(telegram_token)
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


    def run(self):
        self.__app.run_polling()


    async def __start_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        _logger.debug(f'/start command arrived [{tg_user=}]')
        self.__register_user(tg_user)

        reply_text = "Hi there! Pleased to meet you! Feel free to choose preset or supply your own 🤖\n\n"
        # reply_text += HELP_MESSAGE

        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
        # await show_chat_modes_handle(update, context)


    async def __message_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        user = self.__register_user(tg_user)

        _logger.debug(f'Message arrived [{update.message.text}]')

        async with self.__locks[tg_user.id]:
            with self.__task_man(tg_user.id, update.message, user.current_dialog, user.chat_mode) as task:
                try:
                    await task
                except asyncio.CancelledError:
                    await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
                except BaseException as e:
                    error_text = f"Something went wrong during completion. Reason: [{e!r}]"
                    _logger.error(error_text, exc_info=e)
                    await update.message.reply_text(error_text)


    @contextmanager
    def __task_man(self, user_id, message, message_history, chat_mode):
        task = asyncio.create_task(self.__message_handler_task(
            self.__repo.get_user(user_id), message, message_history, chat_mode))
        tasks = self.__tasks
        tasks[user_id] = task
        try:
            yield task
        finally:
            if user_id in tasks:
                del tasks[user_id]


    async def __message_handler_task(self, user, message, message_history, chat_mode):
        assistant = self.__assistant_factory()
        config = self.__config
        if config['message_streaming']:
            placeholder_message = await message.reply_text('...')
            await message.reply_chat_action(action=ChatAction.TYPING)
            parse_mode = dict(html=ParseMode.HTML, 
                              markdown=ParseMode.MARKDOWN).get(config['chat_modes'][chat_mode]['parse_mode'], 
                                                               ParseMode.HTML)
                        
            prev_answer = ''
            async for answer in assistant.send_message_stream(message.text, message_history, chat_mode):
                limit = config['stream_update_chars']
                if answer is not None and abs(len(answer) - len(prev_answer)) < limit:
                    continue

                if answer is not None:
                    prev_answer = answer

                try:
                    await self.__app.bot.edit_message_text(prev_answer, 
                                                           chat_id=placeholder_message.chat_id, 
                                                           message_id=placeholder_message.message_id, 
                                                           parse_mode=parse_mode)
                except telegram.error.BadRequest as e:
                    if str(e).startswith("Message is not modified"):
                        continue
                    else:
                        await self.__app.bot.edit_message_text(prev_answer, 
                                                                chat_id=placeholder_message.chat_id, 
                                                                message_id=placeholder_message.message_id, 
                                                                parse_mode=parse_mode)

                await asyncio.sleep(0.01)
        else:
            await message.reply_chat_action(action=telegram.constants.ChatAction.TYPING)
            resp, usage = await assistant.send_message(message.text, message_history, chat_mode)
            user.current_dialog.append(Dialog(role='user', content=message.text))
            user.current_dialog.append(Dialog(role='assistant', content=resp))
            self.__repo.put_user(user)
            await message.reply_text(resp)


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


    async def __show_chat_modes_handler(self, update: Update, context: CallbackContext):
        self.__register_user(update.message.from_user)
        # if await is_previous_message_not_answered_yet(update, context): return
        text, reply_markup = self.__get_chat_mode_menu()
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


    async def __show_chat_modes_callback_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.__register_user(query.from_user)
        # if await is_previous_message_not_answered_yet(update.callback_query, context): return

        await query.answer()

        page_index = int(query.data.split('|')[1])
        if page_index < 0:
            return

        text, reply_markup = get_chat_mode_menu(page_index)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except telegram.error.BadRequest as e:
            _logger.error(f'Edit message error [{e!r}]')


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


    async def __post_init(self, app):
        _logger.info(f'Bot started')

        await app.bot.set_my_commands([
            BotCommand("/new", "Start new dialog"),
            BotCommand("/mode", "Select chat mode"),
            BotCommand("/settings", "Show settings"),
            BotCommand("/help", "Show help message"),
        ])
