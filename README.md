# AutoLead Brasil

Plataforma web de prospecção de leads no setor automotivo (pneus), com lojas e frotistas da base oficial da Receita Federal, validação de CNPJ, CRM integrado e exportação de dados. Não usa nenhuma API paga do Google.

---

## Funcionalidades

- Aba **Lojas Novas**: lojas de pneus e frotistas ativos da Receita Federal (abertos desde 2010), sem MEI e sem borracharias, com filtros por tipo, estado, cidade, ano e mês — base atualizada automaticamente 2x por mês
- Selo de lead novo (empresa aberta nos últimos 3 anos)
- Consulta de CNPJ com 3 APIs gratuitas em fallback (BrasilAPI, ReceitaWS, CNPJá)
- Favoritos salvos por usuário no banco de dados, com busca textual
- CRM: registro de lojas com tabs por status (Em contato / Retornar depois / Sem interesse / Concluído) e edição inline
- Exportação de leads em CSV, Excel e PDF
- Autenticação via Supabase (cadastro auto-confirmado, sem e-mail de verificação)
- Tema claro/escuro, sidebar desktop + drawer mobile

---

## Pré-requisitos

- Python 3.8+
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

- Arquivos estáticos (`index.html`, `css/`) são servidos da raiz
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
├── dist/                 # Ignorado pelo Vercel (.vercelignore)
├── index.html            # Frontend completo (JS inline)
├── scripts/
│   ├── atualizar_receita.py  # Carrega a base da Receita no Supabase (GitHub Actions)
│   └── security_check.py     # Varredura de segurança (roda no pre-commit)
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
| `GET`  | `/api/cnpj` | `cnpj` | Consulta CNPJ nas bases públicas gratuitas |
| `GET`  | `/api/receita-lojas` | `tipo`, `uf`, `cidade`, `ano`, `mes`, `page`, `excluir`, `exportar` (todos opcionais) | Lista paginada de lojas/frotistas da Receita |
| `GET`  | `/api/receita-info` | — | Mês da base da Receita carregada |

Todas, exceto `/api/register`, exigem usuário logado e aprovado (as rotas `/api/admin-*` são só da administradora).

---

## Banco de dados (Supabase)

| Tabela | Descrição |
|--------|-----------|
| `lojas_receita` | Lojas de pneus e frotistas da Receita Federal (carregada por `scripts/atualizar_receita.py`) |
| `stores` | CRM de lojas registradas — unique por `company_id` |
| `favorites` | Favoritos por usuário — unique por `(user_email, place_id)` |
| `user_access` | Aprovação de cadastros e pedidos de reset de senha |

> As tabelas `searches`, `search_history` e `search_limits` eram da antiga busca no Google e não são mais usadas pelo sistema.

Todas as tabelas usam **Row Level Security (RLS)**: cada usuário acessa apenas seus próprios dados.

---

## Observações

- **Timeout no Vercel (plano gratuito):** o limite é 10 segundos por requisição.
- **Custo:** o sistema não chama nenhuma API paga — só o Supabase e as bases públicas gratuitas de CNPJ.
