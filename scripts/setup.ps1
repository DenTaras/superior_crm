# PowerShell setup script: создает venv и устанавливает зависимости
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
if (Test-Path requirements.txt) {
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt не найден — пропускаем установку зависимостей"
}
Write-Host "Готово. Активируйте окружение: .\\.venv\\Scripts\\Activate.ps1"