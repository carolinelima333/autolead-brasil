# 🚗 AutoLead Brasil (Python)

Sistema de prospecção automotiva — borracharias, lojas de pneus e auto centers.

## 🚀 Como rodar

### Pré-requisitos
- Python 3.8+
- Conta no Google Cloud com **Places API** ativada

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/autolead-brasil.git
cd autolead-brasil

# 2. Crie o ambiente virtual
python -m venv venv

# 3. Ative o venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Configure o .env
cp .env.example .env
# Edite o .env com sua GOOGLE_API_KEY

# 6. Inicie o servidor
python app.py

# 7. Acesse
# http://localhost:3000
```

## 📁 Estrutura

```
autolead-brasil/
├── app.py              # Servidor Flask (Python)
├── index.html          # Frontend completo
├── requirements.txt    # Bibliotecas Python
├── .env.example        # Exemplo de variáveis
├── .gitignore          # Ignora venv/ e .env
└── README.md
```
