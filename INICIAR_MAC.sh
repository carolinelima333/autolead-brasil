#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt --quiet
python api/index.py
