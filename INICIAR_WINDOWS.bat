@echo off
echo Iniciando AutoLead Brasil...

REM Cria o venv se não existir
if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
)

REM Ativa o venv
call venv\Scripts\activate

REM Instala as dependências
pip install -r backend\requirements.txt

REM Inicia o servidor
python backend\app.py

pause
