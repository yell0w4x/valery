from repository import Repository
from bot import Bot
from app_service import AppService
from ai import Assistant

from telegram.ext import ApplicationBuilder
import openai

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Singleton, Dependency, Factory
from os.path import realpath, abspath


class Container(DeclarativeContainer):
    config = Configuration()
    repo = Singleton(Repository, mongodb_uri=config.mongodb_uri)
    tg_app_builder = Singleton(ApplicationBuilder)
    openai_client = Factory(openai.AsyncOpenAI, 
                            api_key=config.anyscale_token, 
                            base_url=config.anyscale_base_url)

    assistant = Factory(Assistant, client=openai_client, config=config)
    bot = Singleton(Bot, 
                    telegram_app_builder=tg_app_builder, 
                    telegram_token=config.telegram_token, 
                    repository=repo,
                    assistant_factory=assistant.provider)
    app_service = Singleton(AppService, config=config, bot=bot)