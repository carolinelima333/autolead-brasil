# AutoLead Brasil

Plataforma web de prospecção de leads no setor automotivo (pneus), com busca via Google Places API, validação de CNPJ e CRM básico.

---

## Funcionalidades

- Busca de empresas por estado ou cidade via Google Places API
- Dois modos de busca: **Lojas & Atacadistas** e **Frotistas / Compradores**
- Filtragem automática de borracharias (serviços de reparo)
- Validação de CNAE via consulta de CNPJ (BrasilAPI, ReceitaWS, CNPJ.ws)
- Identificação de leads novos (empresa aberta há menos de 24 meses)
- Histórico de pesquisas e cache de resultados no Supabase
- Favoritos salvos por usuário no banco de dados
- CRM básico: registro de lojas com status de relacionamento
- Exportação de leads em CSV
- Tema claro/escuro

---

## Pré-requisitos

- Python 3.8+
- Conta no [Google Cloud](https://console.cloud.google.com) com **Places API** ativada
- Projeto no [Supabase](https://supabase.com) (banco de dados)

---

## Rodar localmente

### 1. Clone o repositório

```bash
git clone https://github.com/SEU_USUARIO/autolead-brasil.git
cd autolead-brasil
```

### 2. Crie e ative o ambiente virtual

```bash
# Criar
python -m venv venv

# Ativar — Windows
venv\Scripts\activate

# Ativar — Mac/Linux
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas chaves:

```env
GOOGLE_API_KEY=sua_chave_aqui
```

### 5. Inicie o servidor

```bash
python api/index.py
```

Ou use o atalho (Windows):

```bash
INICIAR_WINDOWS.bat
```

O sistema estará disponível em `http://localhost:3000`.

---

## Deploy no Vercel

### Estrutura compatível

O projeto já está configurado para Vercel:

- Arquivos estáticos (`index.html`, `css/`, `js/`) são servidos da raiz
- A API Flask (`api/index.py`) roda como serverless function Python
- O `vercel.json` roteia `/api/*` para `api/index.py`

### Passo a passo

**1. Instale o CLI do Vercel** (se ainda não tiver):

```bash
npm i -g vercel
```

**2. Faça o deploy:**

```bash
# Deploy de preview
vercel

# Deploy de produção
vercel --prod
```

Ou conecte o repositório diretamente em [vercel.com](https://vercel.com) para deploy automático a cada push no GitHub.

**3. Configure a variável de ambiente no Vercel:**

> Dashboard do Vercel → Seu Projeto → **Settings → Environment Variables**

Adicione:

| Nome | Valor |
|------|-------|
| `GOOGLE_API_KEY` | sua chave da Google Places API |

> O arquivo `.env` é ignorado no deploy (`.vercelignore`). A variável deve ser configurada pelo painel.

---

## Estrutura do projeto

```
autolead-brasil/
├── api/
│   └── index.py          # Backend Flask — endpoints /api/buscar e /api/details
├── css/
│   └── styles.css        # Estilos da interface
├── js/
│   └── app.js            # JavaScript do frontend (referência local)
├── dist/                 # Ignorado pelo Vercel (.vercelignore)
├── index.html            # Frontend completo (JS inline)
├── requirements.txt      # Dependências Python
├── vercel.json           # Configuração de rotas e headers do Vercel
├── .env.example          # Exemplo de variáveis de ambiente
├── .vercelignore         # Arquivos excluídos do deploy
├── .gitignore
├── INICIAR_WINDOWS.bat   # Atalho para rodar localmente no Windows
└── README.md
```

---

## Endpoints da API

| Método | Rota | Parâmetros | Descrição |
|--------|------|------------|-----------|
| GET | `/api/buscar` | `uf`, `query`, `cidade` (opcional) | Busca empresas via Google Places |
| GET | `/api/details` | `place_id` | Detalhes de uma empresa (telefone, site, coordenadas) |

---

## Observações

- **Timeout no Vercel (plano gratuito):** o limite é 10 segundos por requisição. Buscas por estado inteiro fazem múltiplas chamadas à API e podem ser lentas. A busca por **cidade específica** é mais rápida e confiável.
- **Cache de resultados:** os resultados ficam salvos no Supabase por 7 dias (`CACHE_TTL_DAYS`). Pesquisas repetidas na mesma localidade não consomem a API do Google.
- **Limite diário:** cada combinação de localidade/modo é limitada a 10 buscas por dia por usuário (`MAX_DAILY`).
