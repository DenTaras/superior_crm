#!/usr/bin/env bash
set -euo pipefail

# Создаёт виртуальное окружение .venv и устанавливает зависимости
python -m venv .venv
# активировать среду в текущем шелле: source .venv/bin/activate
. .venv/bin/activate
python -m pip install --upgrade pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt not found — пропускаем установку зависимостей"
fi

echo "Готово. Активируйте окружение: source .venv/bin/activate"