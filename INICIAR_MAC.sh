#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativa a varredura de segurança antes de cada commit (scripts/security_check.py)
git config core.hooksPath .githooks 2>/dev/null

source venv/bin/activate
pip install -r requirements.txt --quiet
python api/index.py
