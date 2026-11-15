"""Additive Bot API rich-message support without changing the pinned aiogram graph."""
import logging
from typing import Any
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
from aiogram.methods.base import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions, Message, MessageEntity

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class SendRichMessage(TelegramMethod[Message]):
    __returning__ = Message
    __api_method__ = "sendRichMessage"
    chat_id: int | str
    rich_message: dict[str, Any]
    reply_markup: InlineKeyboardMarkup | None = None
    allow_paid_broadcast: bool = False


class EditRichMessage(TelegramMethod[Message | bool]):
    __returning__ = Message | bool
    __api_method__ = "editMessageText"
    chat_id: int | str
    message_id: int
    rich_message: dict[str, Any]
    reply_markup: InlineKeyboardMarkup | None = None


async def send_document(bot: Bot, chat_id: int, document: dict, *, reply_markup: InlineKeyboardMarkup | None = None, message_id: int | None = None, text_only: bool = False) -> Message | bool:
    if not text_only:
        try:
            if message_id is not None:
                return await bot(EditRichMessage(chat_id=chat_id, message_id=message_id, rich_message=document["rich_message"], reply_markup=reply_markup), request_timeout=30)
            result = await bot(SendRichMessage(chat_id=chat_id, rich_message=document["rich_message"], reply_markup=reply_markup), request_timeout=30)
            log.info("Timetable delivery: rich_message accepted")
            return result
        except (TelegramBadRequest, TelegramNotFound) as error:
            if "message is not modified" in str(error).lower():
                return True
            # Telegram explicitly rejected this request: only then is fallback safe.
            # Never fallback on network/timeout/5xx/429: outcome could be ambiguous.
            log.warning("Telegram rich request rejected; use text fallback (%s)", type(error).__name__)
    fallback = document["fallback"]
    entities = [MessageEntity.model_validate(entity) for entity in fallback["entities"]]
    options = dict(text=fallback["text"], entities=entities, parse_mode=None, reply_markup=reply_markup, link_preview_options=LinkPreviewOptions(is_disabled=True))
    if message_id is not None:
        try:
            return await bot.edit_message_text(chat_id=chat_id, message_id=message_id, **options, request_timeout=30)
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).lower():
                return True
            raise
    return await bot.send_message(chat_id=chat_id, **options, request_timeout=30)
