from dataclasses import dataclass


@dataclass
class BookDraft:
    file_id: str
    filename: str
    name: str | None = None
    scenario: str | None = None
    edition: str | None = None
    publication_year: int | None = None
    system_key: str | None = None


@dataclass
class MessageTarget:
    chat_id: int
    message_id: int
    thread_id: int | None
    content_type: str
    text: str | None
    caption: str | None
    author_id: int | None
    author_name: str | None
    file_id: str | None = None
    file_name: str | None = None
