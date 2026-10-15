from pathlib import Path

from repository import JsonRepository


class AdminRepository:
    """
    Gerencia os administradores do Merlin.

    Os administradores são armazenados em:
        data/admins.json
    """

    def __init__(self, path: Path):
        self.repository = JsonRepository(path)

    def get_all(self) -> list[int]:
        """
        Retorna todos os IDs cadastrados.
        """

        admins = self.repository.load()

        return [
            int(admin["id"])
            for admin in admins
            if "id" in admin
        ]

    def exists(self, user_id: int) -> bool:
        """
        Verifica se um usuário é administrador.
        """

        return user_id in self.get_all()

    def add(
        self,
        user_id: int,
        name: str | None = None,
        username: str | None = None,
    ) -> bool:
        """
        Adiciona um administrador.

        Retorna:
            True  -> administrador adicionado
            False -> já existia
        """

        if self.exists(user_id):
            return False

        self.repository.append(
            {
                "id": user_id,
                "nome": name,
                "username": username,
            }
        )

        return True

    def remove(self, user_id: int) -> bool:
        """
        Remove um administrador.

        Retorna:
            True  -> removido
            False -> não encontrado
        """

        admins = self.repository.load()

        novos_admins = [
            admin
            for admin in admins
            if admin.get("id") != user_id
        ]

        if len(novos_admins) == len(admins):
            return False

        self.repository.save(novos_admins)

        return True