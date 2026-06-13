#!/usr/bin/env bash
set -euo pipefail

# Запускает dev-сервер uvicorn из виртуального окружения
if [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
fi

# по умолчанию запускаем на 0.0.0.0:8000
uvicorn app:app --reload --host 0.0.0.0 --port 8000