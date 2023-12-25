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

from datetime import datetime, timezone
import logging
import asyncio
from contextlib import contextmanager


HELP_MESSAGE = """Commands:
⚪ /retry – Regenerate last bot answer
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
⚪ /settings – Show settings
⚪ /balance – Show balance
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
    def __init__(self, telegram_app_builder, telegram_token, repository, assistant_factory):
        _logger.debug(f'Creating bot [{telegram_token=}]')
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
        app.add_handler(CommandHandler("start", self.__start_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.__message_handler))


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


    async def __message_handler(self, update: Update, context: CallbackContext):
        tg_user = update.message.from_user
        user = self.__register_user(tg_user)

        message = update.message.text
        _logger.debug(f'Message arrived [{message}]')

        async with self.__locks[tg_user.id]:
            with self.__task_man(tg_user.id, message, user.current_dialog, 'english_tutor') as task:
                try:
                    resp = await task
                    await update.message.reply_text(resp)
                except asyncio.CancelledError:
                    await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
                except BaseException as e:
                    error_text = f"Something went wrong during completion. Reason: [{e}]"
                    _logger.error(error_text, exc_info=e)
                    await update.message.reply_text(error_text)


    async def __message_handler_task(self, user, message, message_history, chat_mode):
        assistant = self.__assistant_factory()
        resp, usage = await assistant.send_message(message, message_history, chat_mode)
        user.current_dialog.append(Dialog(role='user', content=message))
        user.current_dialog.append(Dialog(role='assistant', content=resp))
        self.__repo.put_user(user)
        return resp


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


    async def __post_init(self, app):
        _logger.info(f'Bot started')

        await app.bot.set_my_commands([
            BotCommand("/new", "Start new dialog"),
            BotCommand("/mode", "Select chat mode"),
            BotCommand("/retry", "Re-generate response for previous query"),
            BotCommand("/balance", "Show balance"),
            BotCommand("/settings", "Show settings"),
            BotCommand("/help", "Show help message"),
        ])
