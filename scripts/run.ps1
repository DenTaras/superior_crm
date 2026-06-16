# PowerShell run script: активирует venv и запускает uvicorn
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
if (Test-Path .\\.venv\\Scripts\\Activate.ps1) {
    & .\\.venv\\Scripts\\Activate.ps1
}
uvicorn main:app --reload --host 0.0.0.0 --port 8000