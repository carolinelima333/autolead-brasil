# 🚗 AutoLead Brasil (Python)

1. Visão Geral
O AutoLead Brasil é uma plataforma web de prospecção de leads no setor automotivo (pneus), focada em dois públicos:

Perfil	O que são	Como buscar
Vendedores	Lojas de pneus, distribuidoras e atacadistas	Modo "🏪 Lojas & Atacadistas"
Compradores	Transportadoras e empresas com frotas	Modo "🚛 Frotistas / Compradores"
Funcionalidades principais:

Busca por estado ou cidade via Google Places API
Filtragem automática de borracharias (serviços de reparo)
Validação de CNAE via consulta de CNPJ
Identificação de leads novos (empresa aberta há < 24 meses)
Histórico de pesquisas persistido por modo (Lojas vs. Frotistas)
Favoritos salvos por usuário no banco de dados
CRM básico: registro de lojas com status de relacionamento
Exportação de dados em CSV
Consulta de CNPJ com data de abertura
Tema claro/escuro

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
