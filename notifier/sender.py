"""Abstract MessageSender port + concrete Telegram implementation.

Why this port:
- Tests can use FakeMessageSender (no need to mock python-telegram-bot).
- A future WhatsApp/Slack adapter just implements the same 2 methods.
- send_photo accepting a path (not a file handle) keeps callers symmetric.
"""
from abc import ABC, abstractmethod
from typing import Any


class MessageSender(ABC):
    """Minimal port for one-way messaging. Concrete impls wrap a real client."""

    @abstractmethod
    async def send_text(self, chat_id: int, text: str, reply_markup: Any = None) -> None: ...

    @abstractmethod
    async def send_photo(self, chat_id: int, photo_path: str, caption: str,
                          reply_markup: Any = None) -> None: ...


class TelegramMessageSender(MessageSender):
    """Wraps python-telegram-bot's Bot. Opens the photo file here so callers
    don't deal with file handles."""

    def __init__(self, bot):
        self._bot = bot

    async def send_text(self, chat_id, text, reply_markup=None):
        await self._bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup,
        )

    async def send_photo(self, chat_id, photo_path, caption, reply_markup=None):
        with open(photo_path, "rb") as f:
            await self._bot.send_photo(
                chat_id=chat_id, photo=f, caption=caption, reply_markup=reply_markup,
            )


def as_sender(bot_or_sender) -> MessageSender:
    """Normalize a bot or a sender into a MessageSender.
    Lets callers keep passing `bot` while production code internally talks to the port."""
    if isinstance(bot_or_sender, MessageSender):
        return bot_or_sender
    return TelegramMessageSender(bot_or_sender)
