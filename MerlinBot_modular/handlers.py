import html
import logging
from datetime import datetime, timezone
from typing import Any

from telebot import types

from admin_repository import AdminRepository
from config import BotConfig, TOPICS, PUBLIC_TOPICS
from menus import main_menu, topic_menu, system_menu
from models import BookDraft, MessageTarget
from publisher import TelegramPublisher
from repository import BookRepository, JsonRepository


class MerlinHandlers:
    """Handlers e regras de negócio do Merlin."""

    def __init__(
        self,
        bot,
        config,
        books,
        deleted,
        edited,
        publisher,
        admins,
    ):
        self.bot = bot
        self.config = config

        self.books = books
        self.deleted = deleted
        self.edited = edited
        self.publisher = publisher
        self.admins = admins

        self.book_sessions = {}
        self.message_sessions = {}

    def is_public_topic(self, message: types.Message) -> bool:
        """
        Verifica se a mensagem foi enviada em um tópico
        onde usuários comuns podem conversar livremente.
        """

        thread_id = getattr(
            message,
            "message_thread_id",
            None
        )

        return thread_id in PUBLIC_TOPICS
    
    def allow_message_in_topic(
        self,
        message: types.Message
    ) -> bool:
        """
        Permite mensagens caso:

        - O usuário seja administrador; ou
        - A mensagem esteja em um tópico público.
        """

        # Administradores podem enviar mensagens normalmente.
        if self.is_admin(message.from_user.id):
            return True

        # Usuários comuns podem enviar mensagens
        # somente nos tópicos públicos.
        if self.is_public_topic(message):
            return True

        return False

    def can_publish_in_topic(
        self,
        user_id: int,
        topic_key: str
    ) -> bool:
        """
        Verifica se o usuário possui permissão para
        publicar no tópico escolhido.

        Administradores podem publicar em qualquer tópico.

        Usuários comuns podem publicar somente nos tópicos
        definidos em PUBLIC_TOPICS.
        """

        # Administradores possuem acesso total.
        if self.is_admin(user_id):
            return True

        # Usuários comuns podem acessar somente tópicos públicos.
        return topic_key in PUBLIC_TOPICS

    # ========================================================
    # PERMISSÕES
    # ========================================================

    def is_admin(self, user_id: int) -> bool:
        """
        Verifica se o usuário está cadastrado como administrador.
        """
        return self.admins.exists(user_id)

    def require_admin(self, message: types.Message) -> bool:
        if self.is_admin(message.from_user.id):
            return True

        self.bot.reply_to(
            message,
            "🔒 Esta função é restrita aos administradores de Merlin.",
        )
        return False

    def command_admin(self, message: types.Message):
        """
        Gerencia os comandos administrativos.

        Uso:

            /admin listar
            /admin adicionar 123456789
            /admin remover 123456789
        """

        # Somente administradores podem administrar outros administradores.
        if not self.is_admin(message.from_user.id):
            self.bot.reply_to(
                message,
                "🔒 Somente administradores podem utilizar este comando."
            )
            return

        parts = message.text.split()

        if len(parts) < 2:
            self.show_admin_help(message)
            return

        action = parts[1].lower()

        if action == "listar":
            self.list_admins(message)

        elif action == "adicionar":
            self.add_admin(message, parts)

        elif action == "remover":
            self.remove_admin(message, parts)

        else:
            self.show_admin_help(message)

    # ========================================================
    # COMANDOS
    # ========================================================

    def start(self, message: types.Message):
        self.bot.send_message(
            message.chat.id,
            (
                "🧙‍♂️ <b>Olá, aventureiro!</b>\n\n"
                "Sou Merlin, bibliotecário da BibliotecaRPG.\n\n"
                "📤 /enviar — cadastrar livro\n"
                "🔎 /buscar — buscar livro\n"
                "📢 /mensagem — publicar mensagem\n"
                "✏️ /editar — editar mensagem\n"
                "🗑️ /deletar — excluir mensagem"
            ),
            reply_markup=main_menu(),
            parse_mode="HTML",
        )

    def command_send_book(self, message: types.Message):
        self.bot.reply_to(
            message,
            (
                "📤 <b>Enviar Livro</b>\n\n"
                "Envie o PDF nesta conversa."
            ),
            parse_mode="HTML",
        )

    def command_search(self, message: types.Message):
        self.bot.reply_to(
            message,
            "🔎 Digite o nome, sistema, cenário, edição ou ano:",
        )
        self.bot.register_next_step_handler(
            message,
            self.receive_search,
        )

    def command_message(
        self,
        message: types.Message
    ):
        """
        Permite iniciar o envio de uma mensagem.

        Administradores podem escolher qualquer tópico.

        Usuários comuns podem publicar apenas nos
        tópicos públicos.
        """

        if self.is_admin(message.from_user.id):

            # Administrador pode visualizar todos os tópicos.
            markup = topic_menu("publish")

        else:

            # Usuário comum verá somente os tópicos públicos.
            markup = types.InlineKeyboardMarkup(
                row_width=1
            )

            for topic_key in PUBLIC_TOPICS:

                topic = TOPICS[topic_key]

                markup.add(
                    types.InlineKeyboardButton(
                        topic.label,
                        callback_data=f"publish:{topic_key}",
                    )
                )

        self.bot.reply_to(
            message,
            "📢 Escolha onde deseja publicar:",
            reply_markup=markup,
        )

    def command_delete(self, message: types.Message):
        if not self.require_admin(message):
            return

        target = self.get_reply_target(message)

        if not target:
            self.bot.reply_to(
                message,
                "🗑️ Responda à mensagem e envie /deletar.",
            )
            return

        self.archive_and_delete(target, message.from_user)

    def command_edit(self, message: types.Message):
        if not self.require_admin(message):
            return

        target = self.get_reply_target(message)

        if not target:
            self.bot.reply_to(
                message,
                (
                    "✏️ Responda à mensagem e use:\n"
                    "<code>/editar Novo texto</code>"
                ),
                parse_mode="HTML",
            )
            return

        new_text = message.text.partition(" ")[2].strip()

        if not new_text:
            self.bot.reply_to(
                message,
                "<code>/editar Novo texto</code>",
                parse_mode="HTML",
            )
            return

        self.archive_and_edit(target, new_text, message.from_user)

    def show_admin_help(
        self,
        message: types.Message
    ):
        """
        Exibe os comandos disponíveis para administração.
        """

        self.bot.reply_to(
            message,
            (
                "🧙‍♂️ <b>Gerenciamento de Administradores</b>\n\n"

                "➕ Adicionar:\n"
                "<code>/admin adicionar ID</code>\n\n"

                "➖ Remover:\n"
                "<code>/admin remover ID</code>\n\n"

                "📋 Listar:\n"
                "<code>/admin listar</code>\n\n"

                "Exemplo:\n"
                "<code>/admin adicionar 123456789</code>"
            ),
            parse_mode="HTML"
        )

    def list_admins(
        self,
        message: types.Message
    ):
        """
        Lista todos os administradores cadastrados.
        """

        admins = self.admins.repository.load()

        if not admins:
            self.bot.reply_to(
                message,
                "📋 Nenhum administrador cadastrado."
            )
            return

        linhas = [
            "🧙‍♂️ <b>Administradores do Merlin</b>\n"
        ]

        for index, admin in enumerate(admins, start=1):

            user_id = admin.get("id")
            name = admin.get("nome") or "Sem nome"
            username = admin.get("username")

            if username:
                username_text = f"@{username}"
            else:
                username_text = "sem username"

            linhas.append(
                f"{index}. 👤 <b>{name}</b>\n"
                f"   🆔 <code>{user_id}</code>\n"
                f"   📱 {username_text}\n"
            )

        self.bot.reply_to(
            message,
            "\n".join(linhas),
            parse_mode="HTML"
        )

    def add_admin(
        self,
        message: types.Message,
        parts: list[str]
    ):
        """
        Adiciona um novo administrador.

        Uso:
            /admin adicionar 123456789
        """

        if len(parts) < 3:

            self.bot.reply_to(
                message,
                (
                    "⚠️ Informe o ID do usuário.\n\n"
                    "Exemplo:\n"
                    "<code>/admin adicionar 123456789</code>"
                ),
                parse_mode="HTML"
            )

            return

        try:
            user_id = int(parts[2])

        except ValueError:

            self.bot.reply_to(
                message,
                "⚠️ O ID precisa ser numérico."
            )

            return

        if user_id <= 0:

            self.bot.reply_to(
                message,
                "⚠️ ID inválido."
            )

            return

        if self.admins.exists(user_id):

            self.bot.reply_to(
                message,
                (
                    "ℹ️ Este usuário já é administrador.\n\n"
                    f"🆔 <code>{user_id}</code>"
                ),
                parse_mode="HTML"
            )

            return

        added = self.admins.add(
            user_id=user_id
        )

        if not added:

            self.bot.reply_to(
                message,
                "⚠️ Não foi possível adicionar o administrador."
            )

            return

        self.bot.reply_to(
            message,
            (
                "🧙‍♂️ <b>Novo administrador nomeado!</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                "O aventureiro agora possui acesso às funções "
                "administrativas do Merlin."
            ),
            parse_mode="HTML"
        )

    def remove_admin(
        self,
        message: types.Message,
        parts: list[str]
    ):
        """
        Remove um administrador.

        Uso:
            /admin remover 123456789
        """

        if len(parts) < 3:

            self.bot.reply_to(
                message,
                (
                    "⚠️ Informe o ID do administrador.\n\n"
                    "Exemplo:\n"
                    "<code>/admin remover 123456789</code>"
                ),
                parse_mode="HTML"
            )

            return

        try:
            user_id = int(parts[2])

        except ValueError:

            self.bot.reply_to(
                message,
                "⚠️ O ID precisa ser numérico."
            )

            return

        # Evita que um administrador remova a si próprio.
        if user_id == message.from_user.id:

            self.bot.reply_to(
                message,
                (
                    "🛡️ Merlin não permitirá que você remova "
                    "seus próprios poderes administrativos."
                )
            )

            return

        removed = self.admins.remove(user_id)

        if not removed:

            self.bot.reply_to(
                message,
                (
                    "⚠️ Este ID não está cadastrado como administrador.\n\n"
                    f"🆔 <code>{user_id}</code>"
                ),
                parse_mode="HTML"
            )

            return

        self.bot.reply_to(
            message,
            (
                "⚔️ <b>Privilégios revogados!</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                "Merlin removeu este aventureiro da lista "
                "de administradores."
            ),
            parse_mode="HTML"
        )

    # ========================================================
    # LIVROS
    # ========================================================

    def handle_pdf(self, message: types.Message):
        document = message.document

        if not document:
            return

        filename = (document.file_name or "").strip()

        if not filename.lower().endswith(".pdf"):
            self.bot.reply_to(
                message,
                "⚠️ Merlin aceita somente arquivos PDF.",
            )
            return

        self.book_sessions[message.from_user.id] = BookDraft(
            file_id=document.file_id,
            filename=filename,
        )

        self.bot.reply_to(
            message,
            (
                "📚 <b>PDF recebido!</b>\n\n"
                "Agora envie os dados em uma única mensagem:\n\n"
                "<code>Nome | Cenário | Edição | Ano</code>\n\n"
                "Exemplo:\n"
                "<code>Livro do Jogador | Forgotten Realms | "
                "5ª Edição | 2014</code>"
            ),
            parse_mode="HTML",
        )

        self.bot.register_next_step_handler(
            message,
            self.receive_book_data,
        )

    def receive_book_data(self, message: types.Message):
        draft = self.book_sessions.get(message.from_user.id)

        if not draft:
            self.bot.reply_to(
                message,
                "⚠️ Não há cadastro de livro ativo.",
            )
            return

        parts = [
            item.strip()
            for item in (message.text or "").split("|")
        ]

        if len(parts) != 4:
            self.bot.reply_to(
                message,
                (
                    "⚠️ Formato inválido.\n\n"
                    "<code>Nome | Cenário | Edição | Ano</code>"
                ),
                parse_mode="HTML",
            )
            self.bot.register_next_step_handler(
                message,
                self.receive_book_data,
            )
            return

        name, scenario, edition, year_text = parts

        try:
            year = int(year_text)
        except ValueError:
            self.bot.reply_to(
                message,
                "⚠️ O ano deve ser numérico.",
            )
            self.bot.register_next_step_handler(
                message,
                self.receive_book_data,
            )
            return

        if not all((name, scenario, edition)):
            self.bot.reply_to(
                message,
                "⚠️ Nome, cenário e edição são obrigatórios.",
            )
            self.bot.register_next_step_handler(
                message,
                self.receive_book_data,
            )
            return

        if not 1000 <= year <= 2100:
            self.bot.reply_to(
                message,
                "⚠️ Informe um ano entre 1000 e 2100.",
            )
            self.bot.register_next_step_handler(
                message,
                self.receive_book_data,
            )
            return

        draft.name = name
        draft.scenario = scenario
        draft.edition = edition
        draft.publication_year = year

        self.bot.send_message(
            message.chat.id,
            "🎲 Escolha o sistema:",
            reply_markup=system_menu(),
        )

    def receive_system(
        self,
        call: types.CallbackQuery,
        system_key: str,
    ):
        draft = self.book_sessions.get(call.from_user.id)
        topic = TOPICS.get(system_key)

        if not draft or not topic:
            self.bot.answer_callback_query(
                call.id,
                "⚠️ Cadastro ou sistema inválido.",
                show_alert=True,
            )
            return

        draft.system_key = system_key

        try:
            publication = self.publisher.publish_book(
                draft,
                topic,
            )

            self.books.add(
                {
                    "nome": draft.name,
                    "sistema": topic.name,
                    "sistema_id": topic.key,
                    "cenario": draft.scenario,
                    "edicao": draft.edition,
                    "ano_publicacao": draft.publication_year,
                    "arquivo": {
                        "file_id": draft.file_id,
                        "nome": draft.filename,
                    },
                    "usuario": {
                        "id": call.from_user.id,
                        "nome": call.from_user.first_name,
                        "username": call.from_user.username,
                    },
                    "publicacao": publication,
                }
            )

            del self.book_sessions[call.from_user.id]

        except Exception:
            logging.exception("Erro ao publicar livro.")
            self.bot.answer_callback_query(
                call.id,
                "❌ Não consegui publicar o livro.",
                show_alert=True,
            )
            return

        self.bot.answer_callback_query(
            call.id,
            "📚 Livro publicado!",
        )

        self.bot.send_message(
            call.message.chat.id,
            (
                "✅ <b>Livro catalogado!</b>\n\n"
                f"📖 {html.escape(draft.name or '')}\n"
                f"🎲 {html.escape(topic.name)}\n"
                f"📕 {html.escape(draft.edition or '')}\n"
                f"📅 {draft.publication_year}"
            ),
            parse_mode="HTML",
        )

    # ========================================================
    # BUSCA
    # ========================================================

    def receive_search(self, message: types.Message):
        query = (message.text or "").strip()
        results = self.books.search(query)

        if not results:
            self.bot.reply_to(
                message,
                "🔎 Nenhum livro encontrado.",
            )
            return

        markup = types.InlineKeyboardMarkup(row_width=1)

        for book in results[:10]:
            markup.add(
                types.InlineKeyboardButton(
                    f"📖 {book.get('nome', 'Sem nome')} — "
                    f"{book.get('sistema', '')}",
                    callback_data=f"book:{book.get('id')}",
                )
            )

        self.bot.send_message(
            message.chat.id,
            f"🔎 Encontrei {min(len(results), 10)} resultado(s):",
            reply_markup=markup,
        )

    def show_book(
        self,
        call: types.CallbackQuery,
        book_id: int,
    ):
        book = self.books.get_by_id(book_id)

        if not book:
            self.bot.answer_callback_query(
                call.id,
                "⚠️ Livro não encontrado.",
                show_alert=True,
            )
            return

        publication = book.get("publicacao", {})
        group_id = publication.get("grupo_id")
        message_id = publication.get("mensagem_id")

        if not group_id or not message_id:
            self.bot.answer_callback_query(
                call.id,
                "⚠️ Publicação não registrada.",
                show_alert=True,
            )
            return

        link = self.build_message_link(
            group_id,
            message_id,
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "📖 Abrir publicação",
                url=link,
            )
        )

        self.bot.send_message(
            call.message.chat.id,
            (
                f"📚 <b>{html.escape(str(book.get('nome', '')))}</b>\n\n"
                f"🎲 Sistema: {html.escape(str(book.get('sistema', '')))}\n"
                f"🌎 Cenário: {html.escape(str(book.get('cenario', '')))}\n"
                f"📕 Edição: {html.escape(str(book.get('edicao', '')))}\n"
                f"📅 Ano: {book.get('ano_publicacao', 'Não informado')}"
            ),
            reply_markup=markup,
            parse_mode="HTML",
        )

    @staticmethod
    def build_message_link(
        group_id: int,
        message_id: int,
    ) -> str:
        group = str(group_id)

        if not group.startswith("-100"):
            raise ValueError(
                "O grupo precisa ser um supergrupo."
            )

        return f"https://t.me/c/{group[4:]}/{message_id}"

    # ========================================================
    # PUBLICAÇÃO DE MENSAGEM
    # ========================================================

    def choose_message_topic(
        self,
        call: types.CallbackQuery,
        topic_key: str,
    ):
        """
        Define o tópico onde a mensagem será publicada.

        Administradores podem escolher qualquer tópico.

        Usuários comuns somente podem escolher tópicos
        definidos como públicos.
        """

        # Verifica se o tópico existe.
        if topic_key not in TOPICS:

            self.bot.answer_callback_query(
                call.id,
                "⚠️ Tópico inválido.",
                show_alert=True,
            )

            return

        # Verifica se o usuário possui permissão.
        if not self.can_publish_in_topic(
            call.from_user.id,
            topic_key
        ):

            self.bot.answer_callback_query(
                call.id,
                "🔒 Você não possui permissão para publicar neste tópico.",
                show_alert=True,
            )

            return

        # Armazena o tópico escolhido temporariamente.
        self.message_sessions[
            call.from_user.id
        ] = topic_key

        self.bot.answer_callback_query(
            call.id
        )

        # Solicita a mensagem.
        self.bot.edit_message_text(
            (
                f"📢 <b>Publicar em "
                f"{html.escape(TOPICS[topic_key].name)}</b>\n\n"

                "Digite a mensagem que deseja publicar."
            ),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
        )

        self.bot.register_next_step_handler(
            call.message,
            self.receive_message_to_publish,
        )

    def receive_message_to_publish(
        self,
        message: types.Message,
    ):
        """
        Recebe e publica a mensagem no tópico selecionado.
        """

        topic_key = self.message_sessions.pop(
            message.from_user.id,
            None,
        )

        text = (message.text or "").strip()

        # Verifica se existe uma sessão ativa.
        if not topic_key or topic_key not in TOPICS:

            self.bot.reply_to(
                message,
                "⚠️ Publicação não encontrada ou expirada.",
            )

            return

        # Verifica novamente a permissão.
        if not self.can_publish_in_topic(
            message.from_user.id,
            topic_key,
        ):

            self.bot.reply_to(
                message,
                "🔒 Você não possui permissão para publicar neste tópico.",
            )

            return

        # Verifica se a mensagem está vazia.
        if not text:

            self.bot.reply_to(
                message,
                "⚠️ A mensagem não pode estar vazia.",
            )

            return

        try:

            # Publica no tópico.
            self.publisher.publish_message(
                text,
                TOPICS[topic_key],
            )

            self.bot.reply_to(
                message,
                (
                    "✅ Sua mensagem foi publicada em "
                    f"<b>{html.escape(TOPICS[topic_key].name)}</b>."
                ),
                parse_mode="HTML",
            )

        except Exception:

            logging.exception(
                "Erro ao publicar mensagem."
            )

            self.bot.reply_to(
                message,
                "❌ Merlin não conseguiu publicar sua mensagem.",
            )

    # ========================================================
    # EDIÇÃO E EXCLUSÃO
    # ========================================================

    def get_reply_target(
        self,
        command: types.Message,
    ) -> MessageTarget | None:
        original = command.reply_to_message

        if not original:
            return None

        file_id = None
        file_name = None

        if original.document:
            file_id = original.document.file_id
            file_name = original.document.file_name

        return MessageTarget(
            chat_id=original.chat.id,
            message_id=original.message_id,
            thread_id=getattr(
                original,
                "message_thread_id",
                None,
            ),
            content_type=original.content_type,
            text=original.text,
            caption=original.caption,
            author_id=(
                original.from_user.id
                if original.from_user
                else None
            ),
            author_name=(
                original.from_user.first_name
                if original.from_user
                else None
            ),
            file_id=file_id,
            file_name=file_name,
        )

    @staticmethod
    def snapshot(
        target: MessageTarget,
        action: str,
        actor_id: int,
    ) -> dict[str, Any]:
        return {
            "acao": action,
            "data": datetime.now(
                timezone.utc,
            ).isoformat(),
            "executado_por": actor_id,
            "mensagem": {
                "chat_id": target.chat_id,
                "message_id": target.message_id,
                "thread_id": target.thread_id,
                "content_type": target.content_type,
                "text": target.text,
                "caption": target.caption,
                "autor_id": target.author_id,
                "autor_nome": target.author_name,
                "file_id": target.file_id,
                "file_name": target.file_name,
            },
        }

    def archive_and_delete(
        self,
        target: MessageTarget,
        actor: types.User,
    ):
        # Regra importante: arquivar ANTES de excluir.
        self.deleted.append(
            self.snapshot(
                target,
                "exclusao",
                actor.id,
            )
        )

        try:
            self.publisher.delete_message(
                target.chat_id,
                target.message_id,
            )
        except Exception:
            logging.exception(
                "Erro ao excluir mensagem."
            )
            self.bot.reply_to(
                actor,
                "❌ A mensagem foi arquivada, mas a exclusão falhou.",
            )
            return

        self.bot.reply_to(
            actor,
            "🗑️ Mensagem excluída e arquivada.",
        )

    def handle_new_member(self, message: types.Message):
        """
        Remove a mensagem automática de entrada do Telegram
        e envia a mensagem de boas-vindas do Merlin.
        """

        try:
            # 1. Remove a mensagem automática do Telegram
            self.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )

            logging.info(
                "Mensagem automática de entrada removida: %s",
                message.message_id,
            )

        except Exception:
            logging.exception(
                "Não foi possível remover a mensagem automática de entrada."
            )

        # 2. Obtém os novos membros
        novos_membros = message.new_chat_members

        if not novos_membros:
            return

        # 3. Monta as menções dos novos membros
        mencoes = []

        for membro in novos_membros:
            if membro.username:
                mencao = f"@{membro.username}"
            else:
                # Mention usando o ID do usuário
                mencao = (
                    f'<a href="tg://user?id={membro.id}">'
                    f'{membro.first_name}'
                    f'</a>'
                )

            mencoes.append(mencao)

        nomes = ", ".join(mencoes)

        # 4. Mensagem de boas-vindas
        mensagem = f"""
            🧙‍♂️ <b>Uma nova alma adentra a Biblioteca!</b>

            📚 Saudações, {nomes}!

            Eu sou <b>Merlin</b>, bibliotecário desta antiga biblioteca dedicada aos amantes de RPG.

            Antes de explorar os tomos, mapas e pergaminhos desta biblioteca, apresente-se aos demais aventureiros!

            ⚔️ <b>O Modelo de apresentação está fixado no chat.</b>

            Que os dados estejam ao seu favor! 🎲

            — <i>Merlin, Bibliotecário da Biblioteca RPG</i>
            """

        # 5. Envia a mensagem no mesmo tópico/conversa
        try:
            self.bot.send_message(
                chat_id=message.chat.id,
                text=mensagem,
                parse_mode="HTML",
            )

            logging.info(
                "Mensagem de boas-vindas enviada para: %s",
                nomes,
            )

        except Exception:
            logging.exception(
                "Não foi possível enviar a mensagem de boas-vindas."
            )

    def handle_left_member(self, message: types.Message):
        """
        Remove a mensagem automática gerada quando um membro sai
        ou é removido do grupo.
        """

        try:
            self.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )

            logging.info(
                "Mensagem de saída removida: %s",
                message.message_id,
            )

        except Exception:
            logging.exception(
                "Não foi possível remover a mensagem de saída."
            )

    def archive_and_edit(
        self,
        target: MessageTarget,
        new_text: str,
        actor: types.User,
    ):
        # Regra importante: guardar a versão antiga ANTES de editar.
        self.edited.append(
            {
                **self.snapshot(
                    target,
                    "edicao",
                    actor.id,
                ),
                "novo_conteudo": new_text,
            }
        )

        try:
            if target.content_type == "text":
                self.publisher.edit_text(
                    target.chat_id,
                    target.message_id,
                    new_text,
                )
            elif target.caption is not None:
                self.publisher.edit_caption(
                    target.chat_id,
                    target.message_id,
                    new_text,
                )
            else:
                raise ValueError(
                    "A mensagem não possui texto ou legenda editável."
                )

        except Exception:
            logging.exception(
                "Erro ao editar mensagem."
            )
            self.bot.reply_to(
                actor,
                "❌ A versão anterior foi arquivada, mas a edição falhou.",
            )
            return

        self.bot.reply_to(
            actor,
            "✏️ Mensagem editada. A versão anterior foi arquivada.",
        )

    # ========================================================
    # CALLBACKS
    # ========================================================

    def callback(
        self,
        call: types.CallbackQuery,
    ):
        data = call.data or ""

        try:
            if data == "menu:principal":
                self.bot.edit_message_text(
                    "🏰 <b>BibliotecaRPG</b>\n\nEscolha uma função:",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=main_menu(),
                    parse_mode="HTML",
                )

            elif data == "menu:enviar":
                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    "📤 Use /enviar e envie o PDF.",
                )

            elif data == "menu:buscar":
                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    "🔎 Use /buscar.",
                )

            elif data == "menu:mensagem":
                if not self.is_admin(call.from_user.id):
                    self.bot.answer_callback_query(
                        call.id,
                        "🔒 Acesso restrito.",
                        show_alert=True,
                    )
                    return

                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    "📢 Escolha o tópico:",
                    reply_markup=topic_menu("publish"),
                )

            elif data.startswith("publish:"):
                self.choose_message_topic(
                    call,
                    data.split(":", 1)[1],
                )

            elif data.startswith("system:"):
                self.receive_system(
                    call,
                    data.split(":", 1)[1],
                )

            elif data.startswith("book:"):
                self.show_book(
                    call,
                    int(data.split(":", 1)[1]),
                )

            self.bot.answer_callback_query(call.id)

        except Exception:
            logging.exception("Erro no callback.")
            self.bot.answer_callback_query(
                call.id,
                "❌ Erro ao processar operação.",
                show_alert=True,
            )

    # ========================================================
    # REGISTRO DOS HANDLERS
    # ========================================================

    def register(self):
        self.bot.message_handler(
            commands=["start", "help"]
        )(self.start)

        self.bot.message_handler(
            commands=["enviar"]
        )(self.command_send_book)

        self.bot.message_handler(
            commands=["buscar"]
        )(self.command_search)

        self.bot.message_handler(
            commands=["mensagem"]
        )(self.command_message)

        self.bot.message_handler(
            commands=["editar"]
        )(self.command_edit)

        self.bot.message_handler(
            commands=["deletar"]
        )(self.command_delete)

        self.bot.message_handler(
            commands=["admin"]
        )(self.command_admin)

        self.bot.message_handler(
            content_types=["document"]
        )(self.handle_pdf)

        self.bot.callback_query_handler(
            func=lambda call: True
        )(self.callback)

        # Entrada de novos membros
        self.bot.message_handler(
            content_types=["new_chat_members"]
        )(self.handle_new_member)

        self.bot.message_handler(
            content_types=["left_chat_member"]
        )(self.handle_left_member)