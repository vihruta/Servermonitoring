from aiogram.filters import BaseFilter
from aiogram.types import Message
import logging

logger = logging.getLogger(__name__)


class AllowedUserFilter(BaseFilter):
    def __init__(self, allowed_users: set[int]):
        self.allowed_users = allowed_users

    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            logger.warning("Unauthorized access attempt")
            return False
        
        logger.info(f'Get message from {message.from_user.id}')
        return message.from_user.id in self.allowed_users