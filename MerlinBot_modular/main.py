import logging
import os

import telebot

from config import load_config
from admin_repository import AdminRepository
from handlers import MerlinHandlers
from publisher import TelegramPublisher
from repository import BookRepository, JsonRepository


def main():
    """
    Inicializa e executa o Merlin.
    """

    # --------------------------------------------------------
    # Configuração dos logs
    # --------------------------------------------------------

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    # --------------------------------------------------------
    # Carrega as configurações
    # --------------------------------------------------------

    config = load_config()

    # --------------------------------------------------------
    # Cria a instância do bot
    # --------------------------------------------------------

    bot = telebot.TeleBot(config.token)

    # --------------------------------------------------------
    # Cria os repositórios
    # --------------------------------------------------------

    books = BookRepository(
        config.books_file
    )

    admins = AdminRepository(
        config.admins_file
    )

    deleted = JsonRepository(
        config.deleted_file
    )

    edited = JsonRepository(
        config.edited_file
    )

    # --------------------------------------------------------
    # Cria o publicador do Telegram
    # --------------------------------------------------------

    publisher = TelegramPublisher(
        bot,
        config
    )

    # --------------------------------------------------------
    # Cria os handlers do Merlin
    # --------------------------------------------------------

    handlers = MerlinHandlers(
        bot=bot,
        config=config,
        books=books,
        deleted=deleted,
        edited=edited,
        publisher=publisher,
        admins=admins,
    )

    # --------------------------------------------------------
    # Registra os comandos e callbacks
    # --------------------------------------------------------

    handlers.register()

    # --------------------------------------------------------
    # Inicia o Merlin
    # --------------------------------------------------------

    logging.info(
        "🧙 Merlin iniciado com sucesso!"
    )

    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=[
            "message",
            "callback_query",
        ],
    )


if __name__ == "__main__":
    main()