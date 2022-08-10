import pickle
from collections import defaultdict
from redis import Redis
from telegram.ext import BasePersistence
from telegram.ext.utils.types import ConversationDict, BD, CD, UD
from typing import DefaultDict, Dict, Optional, Tuple, Any
from exceptions import StoringDataError
from copy import deepcopy


class FishShopPersistence(BasePersistence):
    def __init__(
        self,
        reddisdb: Redis,
        on_flush: bool = False,
        store_user_data: bool = False,
        store_chat_data: bool = False,
        store_bot_data: bool = False,
        store_callback_data: bool = False
    ):
        super().__init__(store_user_data, store_chat_data, store_bot_data, store_callback_data)
        self.reddisdb = reddisdb
        self.on_flush = on_flush
        self.conversations = None

    def load_redis(self) -> None:
        try:
            data_bytes = self.reddisdb.get('TelegramBotPersistence')
            if data_bytes:
                data = pickle.loads(data_bytes)
                self.user_data = defaultdict(dict, data['user_data'])
                self.chat_data = defaultdict(dict, data['chat_data'])
                # For backwards compatibility with files not containing bot data
                self.bot_data = data.get('bot_data', {})
                self.conversations = data['conversations']
            else:
                self.conversations = dict()
                self.user_data = defaultdict(dict)
                self.chat_data = defaultdict(dict)
                self.bot_data = {}
        except TypeError as exc:
            raise StoringDataError(
                f"Something went wrong unpickling from Redis, exception is:\n{exc}"
                )

    def dump_redis(self) -> None:
        data = {
            'conversations': self.conversations,
            'user_data': self.user_data,
            'chat_data': self.chat_data,
            'bot_data': self.bot_data,
        }
        data_bytes = pickle.dumps(data)
        self.reddisdb.set('TelegramBotPersistence', data_bytes)

    def get_conversations(self, name: str) -> ConversationDict:
        '''Returns the conversations from the pickle on Redis if it exsists or an empty dict.'''
        if self.conversations:
            pass
        else:
            self.load_redis()
        return self.conversations.get(name, {}).copy()

    def update_conversation(self, name: str, key: Tuple[int, ...], new_state: Optional[object]) -> None:
        '''Will update the conversations for the given handler and depending on :attr:`on_flush` save the pickle on Redis.'''
        if not self.conversations:
            self.conversations = dict()
        if self.conversations.setdefault(name, {}).get(key) == new_state:
            return
        self.conversations[name][key] = new_state
        if not self.on_flush:
            self.dump_redis()

    def get_user_data(self) -> DefaultDict[int, Dict[Any, Any]]:
        '''Returns the user_data from the pickle on Redis if it exists or an empty :obj:`defaultdict`.'''
        if self.user_data:
            pass
        else:
            self.load_redis()
        return deepcopy(self.user_data)

    def get_chat_data(self) -> DefaultDict[int, Dict[Any, Any]]:
        '''Returns the chat_data from the pickle on Redis if it exists or an empty :obj:`defaultdict`.'''
        if self.chat_data:
            pass
        else:
            self.load_redis()
        return deepcopy(self.chat_data)

    def get_bot_data(self) -> Dict[Any, Any]:
        '''Returns the bot_data from the pickle on Redis if it exists or an empty :obj:`dict`.'''
        if self.bot_data:
            pass
        else:
            self.load_redis()
        return deepcopy(self.bot_data)

    def update_user_data(self, user_id: int, data: Dict) -> None:
        '''Will update the user_data and depending on :attr:`on_flush` save the pickle on Redis.'''
        if self.user_data is None:
            self.user_data = defaultdict(dict)
        if self.user_data.get(user_id) == data:
            return
        self.user_data[user_id] = data
        if not self.on_flush:
            self.dump_redis()

    def update_chat_data(self, chat_id: int, data: Dict) -> None:
        '''Will update the chat_data and depending on :attr:`on_flush` save the pickle on Redis.'''
        if self.chat_data is None:
            self.chat_data = defaultdict(dict)
        if self.chat_data.get(chat_id) == data:
            return
        self.chat_data[chat_id] = data
        if not self.on_flush:
            self.dump_redis()

    def update_bot_data(self, data: Dict) -> None:
        '''Will update the bot_data and depending on :attr:`on_flush` save the pickle on Redis.'''
        if self.bot_data == data:
            return
        self.bot_data = data.copy()
        if not self.on_flush:
            self.dump_redis()
