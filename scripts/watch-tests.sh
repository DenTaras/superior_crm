#!/usr/bin/env bash
# Запуск автоматического прогона тестов при изменениях при помощи pytest-watch (ptw)
if command -v ptw >/dev/null 2>&1; then
  ptw -p "tests" -w "app.py,templates,static" -- "pytest -q"
else
  echo "pytest-watch (ptw) не найден. Установите dev зависимости: pip install -r requirements-dev.txt"
  echo "Или запустите: watchmedo shell-command --patterns '\*.py' --recursive --command 'pytest -q' ."
fi