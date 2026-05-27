"""Tests for the MessageSender port — proves the abstraction works with a fake impl."""
import pytest
from unittest.mock import AsyncMock
from notifier.sender import MessageSender, TelegramMessageSender, as_sender


class FakeMessageSender(MessageSender):
    """In-memory sender that records calls — usable in tests without python-telegram-bot."""

    def __init__(self):
        self.texts: list[tuple[int, str]] = []
        self.photos: list[tuple[int, str, str]] = []

    async def send_text(self, chat_id, text, reply_markup=None):
        self.texts.append((chat_id, text))

    async def send_photo(self, chat_id, photo_path, caption, reply_markup=None):
        self.photos.append((chat_id, photo_path, caption))


@pytest.mark.asyncio
async def test_fake_sender_records_text():
    fake = FakeMessageSender()
    await fake.send_text(chat_id=42, text="hola")
    assert fake.texts == [(42, "hola")]


@pytest.mark.asyncio
async def test_fake_sender_records_photo():
    fake = FakeMessageSender()
    await fake.send_photo(chat_id=99, photo_path="/tmp/x.jpg", caption="caption")
    assert fake.photos == [(99, "/tmp/x.jpg", "caption")]


@pytest.mark.asyncio
async def test_telegram_sender_wraps_bot_send_message():
    bot = AsyncMock()
    sender = TelegramMessageSender(bot)
    await sender.send_text(chat_id=1, text="x")
    bot.send_message.assert_awaited_once_with(chat_id=1, text="x", reply_markup=None)


@pytest.mark.asyncio
async def test_telegram_sender_opens_photo_file(tmp_path):
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"binary-photo-data")

    captured = {}

    async def capture_call(**kwargs):
        captured["chat_id"] = kwargs["chat_id"]
        captured["caption"] = kwargs["caption"]
        captured["bytes"] = kwargs["photo"].read()

    bot = AsyncMock()
    bot.send_photo = AsyncMock(side_effect=capture_call)
    sender = TelegramMessageSender(bot)

    await sender.send_photo(chat_id=7, photo_path=str(photo), caption="cap")

    assert captured["chat_id"] == 7
    assert captured["caption"] == "cap"
    assert captured["bytes"] == b"binary-photo-data"


def test_as_sender_passes_through_existing_sender():
    fake = FakeMessageSender()
    assert as_sender(fake) is fake


def test_as_sender_wraps_bare_bot():
    bot = AsyncMock()
    sender = as_sender(bot)
    assert isinstance(sender, TelegramMessageSender)
    assert sender._bot is bot
