import html
import telebot
from telebot import types

from config import BotConfig, Topic
from models import BookDraft


class TelegramPublisher:
    """Centraliza as operações de publicação do Telegram."""

    def __init__(self, bot: telebot.TeleBot, config: BotConfig):
        self.bot = bot
        self.config = config

    def publish_book(self, draft: BookDraft, topic: Topic) -> dict[str, int]:
        caption = (
            f"📖 <b>{html.escape(draft.name or 'Sem título')}</b>\n\n"
            f"🎲 Sistema: {html.escape(topic.name)}\n"
            f"🌎 Cenário: {html.escape(draft.scenario or 'Não informado')}\n"
            f"📕 Edição: {html.escape(draft.edition or 'Não informada')}\n"
            f"📅 Ano: {draft.publication_year or 'Não informado'}\n\n"
            "🧙 Publicado por Merlin, o bibliotecário."
        )

        message = self.bot.send_document(
            chat_id=self.config.group_id,
            document=draft.file_id,
            caption=caption,
            parse_mode="HTML",
            message_thread_id=topic.thread_id,
        )
        return self.publication_data(message)

    def publish_message(self, text: str, topic: Topic) -> dict[str, int]:
        message = self.bot.send_message(
            chat_id=self.config.group_id,
            text=text,
            parse_mode="HTML",
            message_thread_id=topic.thread_id,
        )
        return self.publication_data(message)

    def delete_message(self, chat_id: int, message_id: int):
        return self.bot.delete_message(chat_id, message_id)

    def edit_text(self, chat_id: int, message_id: int, text: str):
        return self.bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
        )

    def edit_caption(self, chat_id: int, message_id: int, caption: str):
        return self.bot.edit_message_caption(
            caption=caption,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
        )

    @staticmethod
    def publication_data(message: types.Message) -> dict[str, int]:
        return {
            "grupo_id": message.chat.id,
            "topico_id": getattr(message, "message_thread_id", None) or 0,
            "mensagem_id": message.message_id,
        }
