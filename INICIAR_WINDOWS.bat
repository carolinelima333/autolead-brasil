@echo off
echo Iniciando AutoLead Brasil...

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

call venv\Scripts\activate
pip install -r requirements.txt --quiet
python api\index.py

pause
