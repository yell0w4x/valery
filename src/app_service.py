from mongoengine import connect
import logging


_logger = logging.getLogger(__name__)


class AppService:
    def __init__(self, config, bot):
        self.__config = config
        self.__bot = bot


    def run(self):
        self.__bot.run()
