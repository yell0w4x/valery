from mongoengine import Document, StringField, IntField, DateField, \
    connect, EmbeddedDocumentField, EmbeddedDocument, ListField, FloatField
# from typing import Optional, Any 

# import pymongo
# import uuid
# from datetime import datetime

# import config
import logging


_logger = logging.getLogger(__name__)


class Dialog(EmbeddedDocument):
    role = StringField(choices=('user', 'assistant'))
    content = StringField()


class Subscription(EmbeddedDocument):
    llm_total_tokens = IntField(default=0)
    transcription_seconds = FloatField(default=0)


class User(Document):
    id = IntField(primary_key=True)
    username = StringField()
    first_name = StringField()
    last_name = StringField()
    first_seen = DateField()
    last_seen = DateField()
    chat_mode = StringField(default='english_tutor')
    current_dialog = ListField(EmbeddedDocumentField(Dialog))


class Repository:
    def __init__(self, mongodb_uri):
        _logger.debug(f'Connecting to mongo [{mongodb_uri=}]')
        connect(host=mongodb_uri)


    def get_user(self, user_id):
        """Gets user by id if exists and creates new one if doesn't"""

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist as e:
            _logger.info(f'User does not exist [{user_id=}] [{e!r}]')
            return User(id=user_id)
        except BaseException as e:
            _logger.error(f'Unexpected error [{user_id=}] [{e!r}]')
            raise


    def put_user(self, user):
        user.save()


    # def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
    #     if self.__users.count_documents({"_id": user_id}) > 0:
    #         return True
    #     else:
    #         if raise_exception:
    #             raise ValueError(f"User {user_id} does not exist")
    #         else:
    #             return False

    # def add_new_user(
    #     self,
    #     user_id: int,
    #     chat_id: int,
    #     username: str = "",
    #     first_name: str = "",
    #     last_name: str = "",
    # ):
    #     user_dict = {
    #         "_id": user_id,
    #         "chat_id": chat_id,

    #         "username": username,
    #         "first_name": first_name,
    #         "last_name": last_name,

    #         "last_interaction": datetime.now(),
    #         "first_seen": datetime.now(),

    #         "current_dialog_id": None,
    #         "current_chat_mode": "assistant",
    #         "current_model": config.models["available_text_models"][0],

    #         "n_used_tokens": {},

    #         "n_generated_images": 0,
    #         "n_transcribed_seconds": 0.0  # voice message transcription
    #     }

    #     if not self.check_if_user_exists(user_id):
    #         self.__users.insert_one(user_dict)

    # def start_new_dialog(self, user_id: int):
    #     self.check_if_user_exists(user_id, raise_exception=True)

    #     dialog_id = str(uuid.uuid4())
    #     dialog_dict = {
    #         "_id": dialog_id,
    #         "user_id": user_id,
    #         "chat_mode": self.get_user_attribute(user_id, "current_chat_mode"),
    #         "start_time": datetime.now(),
    #         "model": self.get_user_attribute(user_id, "current_model"),
    #         "messages": []
    #     }

    #     # add new dialog
    #     self.__dialogs.insert_one(dialog_dict)

    #     # update user's current dialog
    #     self.__users.update_one(
    #         {"_id": user_id},
    #         {"$set": {"current_dialog_id": dialog_id}}
    #     )

    #     return dialog_id

    # def get_user_attribute(self, user_id: int, key: str):
    #     self.check_if_user_exists(user_id, raise_exception=True)
    #     user_dict = self.__users.find_one({"_id": user_id})

    #     if key not in user_dict:
    #         return None

    #     return user_dict[key]

    # def set_user_attribute(self, user_id: int, key: str, value: Any):
    #     self.check_if_user_exists(user_id, raise_exception=True)
    #     self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})

    # def update_n_used_tokens(self, user_id: int, model: str, n_input_tokens: int, n_output_tokens: int):
    #     n_used_tokens_dict = self.get_user_attribute(user_id, "n_used_tokens")

    #     if model in n_used_tokens_dict:
    #         n_used_tokens_dict[model]["n_input_tokens"] += n_input_tokens
    #         n_used_tokens_dict[model]["n_output_tokens"] += n_output_tokens
    #     else:
    #         n_used_tokens_dict[model] = {
    #             "n_input_tokens": n_input_tokens,
    #             "n_output_tokens": n_output_tokens
    #         }

    #     self.set_user_attribute(user_id, "n_used_tokens", n_used_tokens_dict)

    # def get_dialog_messages(self, user_id: int, dialog_id: Optional[str] = None):
    #     self.check_if_user_exists(user_id, raise_exception=True)

    #     if dialog_id is None:
    #         dialog_id = self.get_user_attribute(user_id, "current_dialog_id")

    #     dialog_dict = self.dialog_collection.find_one({"_id": dialog_id, "user_id": user_id})
    #     return dialog_dict["messages"]

    # def set_dialog_messages(self, user_id: int, dialog_messages: list, dialog_id: Optional[str] = None):
    #     self.check_if_user_exists(user_id, raise_exception=True)

    #     if dialog_id is None:
    #         dialog_id = self.get_user_attribute(user_id, "current_dialog_id")

    #     self.dialog_collection.update_one(
    #         {"_id": dialog_id, "user_id": user_id},
    #         {"$set": {"messages": dialog_messages}}
    #     )
