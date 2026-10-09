@echo off
echo Iniciando AutoLead Brasil...

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

rem Ativa a varredura de segurança antes de cada commit (scripts\security_check.py)
git config core.hooksPath .githooks 2>nul

call venv\Scripts\activate
pip install -r requirements.txt --quiet
python api\index.py

pause
