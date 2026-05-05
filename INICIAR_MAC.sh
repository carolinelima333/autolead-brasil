#!/bin/bash
cd "$(dirname "$0")"

# Cria o venv se não existir
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativa o venv
source venv/bin/activate

# Instala dependências
pip install -r backend/requirements.txt

# Inicia o servidor
python backend/app.py
