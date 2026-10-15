from telebot import types
from config import TOPICS


def main_menu() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📚 Biblioteca", callback_data="menu:biblioteca"),
        types.InlineKeyboardButton("📤 Enviar Livro", callback_data="menu:enviar"),
    )
    markup.add(
        types.InlineKeyboardButton("🔎 Buscar Livro", callback_data="menu:buscar"),
        types.InlineKeyboardButton("📢 Mensagem", callback_data="menu:mensagem"),
    )
    return markup


def back_button(destination="menu:principal"):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Voltar", callback_data=destination))
    return markup


def topic_menu(prefix: str):
    markup = types.InlineKeyboardMarkup(row_width=2)

    for key, topic in TOPICS.items():
        markup.add(
            types.InlineKeyboardButton(
                topic.label,
                callback_data=f"{prefix}:{key}",
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "❌ Cancelar",
            callback_data="menu:principal",
        )
    )
    return markup


def system_menu():
    return topic_menu("system")
