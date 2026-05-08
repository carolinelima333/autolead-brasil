# AutoLead Brasil

Plataforma web de prospecção de leads no setor automotivo (pneus), com busca via Google Places API, validação de CNPJ, CRM integrado e exportação de dados.

---

## Funcionalidades

- Busca de empresas por estado ou cidade via Google Places API
- Dois modos de busca: **Lojas & Atacadistas** e **Frotistas / Compradores**
- Filtragem automática de borracharias (serviços de reparo)
- Validação de CNPJ com 3 APIs em fallback (BrasilAPI, ReceitaWS, CNPJ.ws)
- Identificação de leads novos (empresa aberta há menos de 24 meses)
- Histórico permanente de pesquisas com filtros por estado e modo — restaura resultados sem consumir a API
- Cache de resultados no Supabase (7 dias por busca)
- Favoritos salvos por usuário no banco de dados, com busca textual
- CRM: registro de lojas com tabs por status (Em contato / Retornar depois / Sem interesse / Concluído) e edição inline
- Exportação de leads em CSV, Excel e PDF
- Autenticação via Supabase (cadastro auto-confirmado, sem e-mail de verificação)
- Limite diário de 10 buscas por localidade/modo por usuário
- Tema claro/escuro, sidebar desktop + drawer mobile

---

## Pré-requisitos

- Python 3.8+
- Conta no [Google Cloud](https://console.cloud.google.com) com **Places API** ativada
- Projeto no [Supabase](https://supabase.com) com as tabelas criadas (veja `supabase_setup.sql`)

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
GOOGLE_API_KEY=sua_chave_google_aqui
PORT=3000
SUPABASE_SERVICE_KEY=sua_service_role_key_aqui
SUPABASE_URL=https://SEU_PROJETO.supabase.co
```

> A `SUPABASE_SERVICE_KEY` é a chave `service_role` (secret), disponível em: **Supabase Dashboard → Settings → API**.

### 5. Configure o banco de dados

Execute o arquivo `supabase_setup.sql` no **Supabase SQL Editor** para criar as tabelas, políticas de segurança (RLS) e o trigger de auto-confirmação de e-mail.

### 6. Inicie o servidor

```bash
python api/index.py
```

Ou use o atalho:

```bash
# Windows
INICIAR_WINDOWS.bat

# Mac/Linux
bash INICIAR_MAC.sh
```

O sistema estará disponível em `http://localhost:3000`.

---

## Deploy no Vercel

### Estrutura compatível

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

**3. Configure as variáveis de ambiente no Vercel:**

> Dashboard do Vercel → Seu Projeto → **Settings → Environment Variables**

| Nome | Valor |
|------|-------|
| `GOOGLE_API_KEY` | Chave da Google Places API |
| `SUPABASE_URL` | URL do seu projeto Supabase |
| `SUPABASE_SERVICE_KEY` | Chave `service_role` do Supabase |

> O arquivo `.env` é ignorado no deploy (`.vercelignore`). As variáveis devem ser configuradas pelo painel.

---

## Estrutura do projeto

```
autolead-brasil/
├── api/
│   └── index.py          # Backend Flask (serverless no Vercel)
├── css/
│   └── styles.css        # Estilos — tema dark/light com CSS vars
├── js/
│   └── app.js            # Versão legada (JS inline em index.html é o ativo)
├── dist/                 # Ignorado pelo Vercel (.vercelignore)
├── index.html            # Frontend completo (JS inline)
├── supabase_setup.sql    # Script SQL para criar tabelas e políticas no Supabase
├── requirements.txt      # Dependências Python
├── vercel.json           # Configuração de rotas e headers do Vercel
├── .env.example          # Exemplo de variáveis de ambiente
├── .vercelignore         # Arquivos excluídos do deploy
├── .gitignore
├── INICIAR_WINDOWS.bat   # Atalho para rodar localmente no Windows
├── INICIAR_MAC.sh        # Atalho para rodar localmente no Mac/Linux
└── README.md
```

---

## Endpoints da API

| Método | Rota | Parâmetros | Descrição |
|--------|------|------------|-----------|
| `POST` | `/api/register` | `email`, `password`, `name` | Cria usuário via Admin API do Supabase (auto-confirma e-mail) |
| `GET`  | `/api/buscar` | `uf`, `query`, `cidade` (opcional), `max_cidades` (opcional) | Busca empresas via Google Places |
| `GET`  | `/api/details` | `place_id` | Detalhes de uma empresa (telefone, site, coordenadas) |

---

## Banco de dados (Supabase)

| Tabela | Descrição |
|--------|-----------|
| `searches` | Cache de pesquisas por 7 dias — unique por `(user_email, search_key)` |
| `search_history` | Histórico permanente de pesquisas — acumula todos os registros |
| `stores` | CRM de lojas registradas — unique por `company_id` |
| `favorites` | Favoritos por usuário — unique por `(user_email, place_id)` |
| `search_limits` | Rate limit diário (10 buscas/dia por localidade/modo) |

Todas as tabelas usam **Row Level Security (RLS)**: cada usuário acessa apenas seus próprios dados.

---

## Observações

- **Timeout no Vercel (plano gratuito):** o limite é 10 segundos por requisição. A busca por **cidade específica** é mais rápida e confiável do que busca por estado inteiro.
- **Cache de resultados:** pesquisas repetidas na mesma localidade (dentro de 7 dias) não consomem a API do Google.
- **Limite diário:** cada combinação de localidade/modo é limitada a 10 buscas por dia por usuário.
