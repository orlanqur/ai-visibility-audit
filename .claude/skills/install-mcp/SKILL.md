---
name: install-mcp
description: Разворачивает docs-intelligence-mcp на машине пользователя (обычно на Mac). Клонирует репозиторий, создаёт venv, ставит пакет, проверяет что команда docs-intel доступна. Используй при запросах "установи MCP", "разверни docs-intelligence-mcp", "у меня не работает docs_search, MCP не подключен", "docs-intel command not found", а также по инструкции из README §1.6.
user-invocable: true
---

# install-mcp

Устанавливает MCP-сервер `docs-intelligence-mcp` за пользователя.

## Когда использовать

- Первая сессия: пользователь только склонировал репо системы и просит «установи MCP»
- `docs-intel: command not found` — есть репо, нет venv или пакет не установлен
- Пользователь хочет перепроверить установку

## Алгоритм

1. **Проверь текущее состояние**:
   ```
   ls ~/docs-intelligence-mcp 2>/dev/null
   ls ~/docs-intelligence-mcp/venv/bin/docs-intel 2>/dev/null
   ```
   - Если ни того, ни другого нет → шаг 2 (полная установка).
   - Если репо есть, venv нет → шаг 3 (только venv+pip).
   - Если всё есть → шаг 4 (проверка).

2. **Клонирование + venv + pip install** (полная установка):
   ```bash
   cd ~
   git clone https://github.com/orlanqur/docs-intelligence-mcp.git
   cd docs-intelligence-mcp
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```
   Если `python3.11` нет — сначала `brew install python@3.11`.

3. **Только venv+pip** (репо уже есть):
   ```bash
   cd ~/docs-intelligence-mcp
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

4. **Проверка**:
   ```bash
   ~/docs-intelligence-mcp/venv/bin/docs-intel --help
   ```
   Должен вывести список команд (`index`, `search`, `serve`, `stats`).

5. **Проверь `.env`** в корне активного репо (`~/ai-audit/.env`). Там должен быть `OPENAI_API_KEY=sk-...`. Если файла нет — подскажи пользователю попросить ключ у Аркадия и создать `.env` (формат см. README §1.7).

6. **Проставь абсолютный путь к `docs-intel` в `mcp.json`**. По умолчанию в репо стоит `command: docs-intel` (полагается на PATH). Это хрупко — плагин VSCode может не видеть venv. Замени на абсолютный путь, который ты только что вычислил в шаге 4:
   ```bash
   # определи $HOME и впиши полный путь
   # пример: /Users/katerina/docs-intelligence-mcp/venv/bin/docs-intel
   ```
   Через Edit обнови `mcp.json`: `"command": "/Users/<имя>/docs-intelligence-mcp/venv/bin/docs-intel"`. Имя пользователя бери из `echo $HOME`.

7. **Проверь `docs-intel index` на активном проекте**:
   ```bash
   cd ~/ai-audit
   ~/docs-intelligence-mcp/venv/bin/docs-intel index projects/<активный_проект>
   ```
   Если выдаёт ошибку про API-ключ — см. шаг 5. Если всё ок — MCP готов. Попроси пользователя перезапустить VSCode, чтобы плагин подхватил обновлённый `mcp.json`.

## Важно

- **Запускай команды сам** через Bash (этот skill — автоматизация, не инструкция). Но перед деструктивными шагами (rm, git clone в существующую папку) спроси подтверждение.
- **Venv активируется в одном shell-сеансе.** Чтобы активировать между вызовами Bash, либо используй абсолютный путь `~/docs-intelligence-mcp/venv/bin/docs-intel`, либо собери команду цепочкой: `source ... && docs-intel ...`.
- **Если Claude Code плагин не видит MCP** после установки — попроси пользователя перезапустить VSCode. `mcp.json` подхватывается только при старте.

## Если ничего не помогает

Выведи пользователю:
- путь к venv, который ты создал
- вывод `docs-intel --help`
- содержимое `~/ai-audit/.env` (без значения ключа — только имя переменной)
- список MCP-серверов в VSCode (Command Palette → «Claude Code: Show MCP Servers»)

И предложи написать Аркадию с этим выводом.
