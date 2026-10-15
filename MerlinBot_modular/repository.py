import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonRepository:
    """Persistência JSON com gravação atômica."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError(f"{self.path} deve conter uma lista JSON.")

        return data

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            delete=False,
        ) as temp:
            json.dump(items, temp, ensure_ascii=False, indent=4)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = Path(temp.name)

        temp_path.replace(self.path)

    def append(self, item: dict[str, Any]) -> None:
        items = self.load()
        items.append(item)
        self.save(items)


class BookRepository(JsonRepository):
    def next_id(self) -> int:
        books = self.load()
        ids = [b["id"] for b in books if isinstance(b.get("id"), int)]
        return max(ids, default=0) + 1

    def add(self, book: dict[str, Any]) -> None:
        book["id"] = self.next_id()
        self.append(book)

    def search(self, query: str) -> list[dict[str, Any]]:
        query = query.strip().casefold()
        if not query:
            return []

        results = []
        for book in self.load():
            text = " ".join(
                str(book.get(field, ""))
                for field in (
                    "nome",
                    "sistema",
                    "cenario",
                    "edicao",
                    "ano_publicacao",
                )
            ).casefold()

            if query in text:
                results.append(book)

        return results

    def get_by_id(self, book_id: int) -> dict[str, Any] | None:
        return next(
            (b for b in self.load() if b.get("id") == book_id),
            None,
        )
