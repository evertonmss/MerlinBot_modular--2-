# Merlin — BibliotecaRPG

## Comandos

`/enviar` — recebe PDF e pede `Nome | Cenário | Edição | Ano`; depois o usuário escolhe o sistema por botão.

`/buscar` — pesquisa no catálogo e mostra o link da publicação original.

`/mensagem` — administrador escolhe o tópico e publica uma mensagem.

`/editar Novo texto` — administrador responde à mensagem que deseja editar. A versão antiga é salva antes da alteração.

`/deletar` — administrador responde à mensagem que deseja excluir. A mensagem é arquivada antes da exclusão.

## Variáveis de ambiente

```text
TELEGRAM_BOT_TOKEN=SEU_TOKEN
MERLIN_ADMIN_IDS=123456789,987654321
```

## Estrutura

```text
merlin_bot/
├── config.py
├── models.py
├── repository.py
├── publisher.py
├── menus.py
├── handlers.py
├── main.py
├── requirements.txt
└── data/
    ├── livros.json
    ├── mensagens_excluidas.json
    └── mensagens_editadas.json
```
