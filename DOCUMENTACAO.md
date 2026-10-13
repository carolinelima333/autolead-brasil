# AutoLead Brasil — Documentação Técnica Completa

## Sumário

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Banco de Dados](#4-banco-de-dados)
5. [Backend — API Flask](#5-backend--api-flask)
6. [Frontend — Interface Web](#6-frontend--interface-web)
7. [Autenticação e Segurança](#7-autenticação-e-segurança)
8. [Regras de Negócio](#8-regras-de-negócio)
9. [Integrações Externas](#9-integrações-externas)
10. [Variáveis de Ambiente](#10-variáveis-de-ambiente)
11. [Deploy e Infraestrutura](#11-deploy-e-infraestrutura)
12. [Setup Local](#12-setup-local)
13. [Dependências](#13-dependências)

---

## 1. Visão Geral do Sistema

**AutoLead Brasil** é uma plataforma web B2B para prospecção de leads no setor automotivo de pneus. O sistema permite que usuários autenticados e aprovados encontrem empresas vendedoras (atacado e varejo de pneus) e compradoras (transportadoras e frotistas) na base oficial da Receita Federal, validem os leads via consulta de CNPJ, gerenciem um CRM próprio e exportem os dados.

O sistema **não usa nenhuma API paga** (a antiga busca no Google Places foi removida): só o Supabase e as bases públicas gratuitas de CNPJ.

### Objetivos do Sistema

- Listar lojas de pneus e frotistas ativos por estado, cidade, ano e mês de abertura
- Identificar empresas novas (abertas nos últimos 3 anos) como leads prioritários
- Bloquear empresas irrelevantes (MEI, borracharias, recapagem)
- Validar e enriquecer dados via CNPJ
- Gerenciar o relacionamento com leads em um CRM integrado

---

## 2. Stack Tecnológico

### Backend

| Tecnologia | Versão | Papel |
|---|---|---|
| Python | 3.8+ | Linguagem principal do backend |
| Flask | 3.0.3 | Framework web / API REST |
| Flask-CORS | 4.0.1 | Permite requisições cross-origin |
| Requests | 2.31.0 | Chamadas HTTP para APIs externas |
| Python-dotenv | 1.0.0 | Carregamento de variáveis de ambiente |

### Frontend

| Tecnologia | Versão | Papel |
|---|---|---|
| HTML5 / CSS3 | — | Estrutura e estilo |
| JavaScript (Vanilla) | ES2020+ | Lógica de interface sem frameworks |
| Supabase JS Client | v2 | Autenticação + operações no banco de dados |
| SheetJS (XLSX) | 0.20.3 | Exportação para Excel |
| Google Fonts (Inter) | — | Tipografia |

### Banco de Dados

| Tecnologia | Papel |
|---|---|
| Supabase (PostgreSQL) | Banco de dados principal |
| Row Level Security (RLS) | Isolamento de dados por usuário |
| JWT | Autenticação stateless |

### Deploy

| Tecnologia | Papel |
|---|---|
| Vercel | Hospedagem do frontend e das serverless functions |

---

## 3. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                        USUÁRIO                          │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────┐
│                       VERCEL                            │
│                                                         │
│  ┌─────────────────┐      ┌──────────────────────────┐  │
│  │  index.html     │      │  api/index.py            │  │
│  │  css/styles.css │      │  (Flask serverless)      │  │
│  │  (estáticos)    │      │  /api/register           │  │
│  └────────┬────────┘      │  /api/cnpj               │  │
│           │               │  /api/receita-lojas      │  │
│           │               │  /api/receita-info       │  │
│           │               │  /api/admin-*            │  │
│           │               └──────────┬───────────────┘  │
└───────────┼──────────────────────────┼──────────────────┘
            │ Supabase JS SDK          │ Requests
            ▼                          ▼
┌───────────────────────┐   ┌──────────────────────────┐
│     SUPABASE          │   │   CNPJ APIs (gratuitas)  │
│  (PostgreSQL + Auth)  │   │  BrasilAPI               │
│  lojas_receita        │   │  ReceitaWS               │
│  stores               │   │  CNPJá                   │
│  favorites            │   └──────────────────────────┘
│  user_access          │
└───────────────────────┘
        ▲
        │ GitHub Actions (dias 10 e 25)
  scripts/atualizar_receita.py ← dados abertos do CNPJ (Receita Federal)
```

### Estrutura de Arquivos

```
autolead_python/
├── api/
│   └── index.py              # Backend Flask — serverless function
├── css/
│   └── styles.css            # Estilos — tema dark/light
├── scripts/
│   ├── atualizar_receita.py  # Carrega a base da Receita no Supabase
│   └── security_check.py     # Varredura de segurança (pre-commit)
├── dist/                     # Ignorado pelo Vercel
├── index.html                # Frontend completo com JS inline
├── supabase_setup.sql        # Script de criação do banco de dados
├── requirements.txt          # Dependências Python
├── vercel.json               # Configuração de rotas e headers
├── .env.example              # Modelo de variáveis de ambiente
├── .env                      # Variáveis reais (não versionado)
├── .gitignore
├── .vercelignore
├── INICIAR_WINDOWS.bat       # Atalho para rodar localmente no Windows
├── INICIAR_MAC.sh            # Atalho para rodar localmente no Mac/Linux
└── README.md
```

---

## 4. Banco de Dados

O banco é gerenciado pelo **Supabase** (PostgreSQL hospedado). Todas as tabelas possuem **Row Level Security (RLS)** ativado, garantindo que cada usuário acesse apenas seus próprios dados.

### 4.1. Tabela `lojas_receita` — Base da Receita Federal

Lojas de pneus e frotistas ativos, carregados por `scripts/atualizar_receita.py` (veja a seção 8.3).
Colunas principais: `cnpj`, `razao_social`, `nome_fantasia`, `data_abertura`, `ano`, `mes`, `cnae`,
endereço (`logradouro`, `numero`, `complemento`, `bairro`, `cep`, `municipio`, `uf`), `telefone`,
`referencia` (mês da base) e `atualizado_em`. Lida só pelo backend com a service key.

---

### 4.2. Tabelas legadas `searches`, `search_history` e `search_limits`

Eram o cache, o histórico e o limite diário da antiga busca no Google Places. **Não são mais usadas** pelo
sistema; continuam no banco só com os dados antigos.

---

### 4.3. Tabela `stores` — CRM de Lojas

Registro de lojas para acompanhamento comercial.

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email   TEXT
company_name TEXT NOT NULL
company_id   TEXT UNIQUE      -- "cnpj:<número>" para lojas vindas da Receita
phone        TEXT
address      TEXT
city         TEXT
state        TEXT
status       TEXT             -- 'contato', 'retorno', 'sem_interesse', 'concluido'
notes        TEXT
created_at   TIMESTAMPTZ DEFAULT now()
```

**Status possíveis:**
- `contato` — Em contato
- `retorno` — Retornar depois
- `sem_interesse` — Sem interesse
- `concluido` — Concluído

---

### 4.4. Tabela `favorites` — Favoritos por Usuário

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email   TEXT NOT NULL
place_id     TEXT NOT NULL    -- identificador da empresa (registros antigos: id do Google)
company_data JSONB            -- Snapshot dos dados da empresa
created_at   TIMESTAMPTZ DEFAULT now()

UNIQUE (user_email, place_id)
```

---

### 4.5. Row Level Security (RLS)

Política aplicada a todas as tabelas:

```sql
-- Leitura
CREATE POLICY "Usuário lê apenas seus dados"
  ON <tabela> FOR SELECT
  USING (user_email = auth.jwt() ->> 'email');

-- Escrita
CREATE POLICY "Usuário escreve apenas seus dados"
  ON <tabela> FOR INSERT
  WITH CHECK (user_email = auth.jwt() ->> 'email');
```

---

### 4.6. Trigger — Auto-confirmação de E-mail

Evita o envio de e-mail de verificação ao criar novos usuários.

```sql
CREATE OR REPLACE FUNCTION public.auto_confirm_new_user()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE auth.users
  SET email_confirmed_at = now(),
      confirmed_at = now()
  WHERE id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trg_auto_confirm_user
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.auto_confirm_new_user();
```

---

## 5. Backend — API Flask

**Arquivo:** [api/index.py](api/index.py)

O backend é uma API REST em Flask executada como **serverless function** no Vercel.

### 5.1. Endpoints

#### `POST /api/register`

Cria um novo usuário via Admin API do Supabase com auto-confirmação de e-mail.

**Corpo da requisição (JSON):**
```json
{
  "email": "usuario@email.com",
  "password": "Senha1!",
  "name": "Nome do Usuário"
}
```

**Resposta de sucesso:**
```json
{ "ok": true }
```

**Resposta de erro:**
```json
{ "ok": false, "error": "Mensagem de erro" }
```

**Comportamento:**
1. Valida presença dos campos `email` e `password`
2. Chama `POST {SUPABASE_URL}/auth/v1/admin/users` com a service key
3. Define `email_confirm: true` para pular verificação
4. Salva `name` em `user_metadata`

---

#### `GET /api/cnpj`

Consulta um CNPJ (14 dígitos) em paralelo na BrasilAPI, ReceitaWS e CNPJá e devolve a primeira resposta
válida, já normalizada (`razao_social`, `data_inicio_atividade`, `cnae_code`, `porte`, `is_mei`…).

#### `GET /api/receita-lojas` e `GET /api/receita-info`

Lista paginada da base da Receita e mês da base carregada — detalhes na seção 8.3.

#### `/api/admin-users`, `/api/admin-decide`, `/api/admin-reset`

Aprovação de cadastros e reset de senha, só para a administradora (`_require_admin()`).

Todas as rotas, exceto `/api/register` e `/api/reset-request`, exigem usuário logado e aprovado (`_require_user()`).

---

### 5.2. Tratamento de Erros

- Serviços de CNPJ fora do ar: 502 com mensagem amigável
- Parâmetro inválido: retorna `{"ok": false, "error": "..."}` com status 400
- Erro na criação de usuário: retorna `{"ok": false, "error": "..."}` com status 200
- Base da Receita ainda não carregada (`lojas_receita` não existe): 503 com mensagem amigável

---

## 6. Frontend — Interface Web

**Arquivo:** [index.html](index.html) (JS inline) + [css/styles.css](css/styles.css)

### 6.1. Estrutura HTML

```
<body>
  <!-- Tela de autenticação -->
  <div id="sc-auth">
    Formulário login/cadastro
  </div>

  <!-- Aplicação principal -->
  <div id="sc-main" hidden>

    <!-- Desktop: Sidebar -->
    <nav id="sidebar">
      Logo + Navegação + Logout
    </nav>

    <!-- Mobile: Top Bar -->
    <div id="topbar">
      Hamburger + Logo + Tema
    </div>

    <!-- Mobile: Drawer -->
    <div id="drawer">
      Overlay + Menu lateral
    </div>

    <!-- Conteúdo principal -->
    <main id="content">
      <!-- Abas: Lojas Novas / Favoritos / Lojas / Exportar / Administração -->
    </main>

    <!-- Mobile: Bottom Nav -->
    <nav id="bottom-nav">
      Botões de navegação
    </nav>

  </div>

  <!-- Modal: Registrar Loja -->
  <div id="modal-store">...</div>
</body>
```

### 6.2. Abas do Sistema

| Aba | ID | Funcionalidade Principal |
|---|---|---|
| Lojas Novas | `'r'` | Empresas da Receita com filtros + consulta de CNPJ (aba inicial) |
| Favoritos | `'f'` | Lista de empresas favoritadas com busca |
| Lojas (CRM) | `'s'` | Lojas registradas com edição inline |
| Exportar | `'e'` | Exportação em CSV, Excel e PDF |
| Administração | `'a'` | Aprovação de cadastros e reset de senha (só a adm) |

### 6.3. Estado Global (JavaScript)

Todas as variáveis globais que controlam o estado da aplicação:

```javascript
let user        = null         // { email, name } — usuário logado
let favs        = new Set()    // ids dos favoritos
let favData     = new Map()    // Dados completos: id → empresa
let rf          = {...}        // Filtros, página e linhas da aba Lojas Novas
let theme       = 'dark'       // Tema: 'dark' | 'light' (persistido no localStorage)
let storeFilter = 'todos'      // Filtro CRM: status da loja
let favSearch   = ''           // Texto de busca nos favoritos
```

### 6.4. Fluxo de Autenticação

**Cadastro:**
1. Usuário preenche nome, e-mail e senha
2. Validação client-side da senha (mín 6 chars, 1 maiúscula, 1 número, 1 especial)
3. Chamada `POST /api/register` para criar conta via Admin API (sem e-mail de verificação)
4. Fallback: se o backend falhar, tenta `supabase.auth.signUp()` diretamente
5. Auto-login após cadastro bem-sucedido

**Login:**
1. Usuário preenche e-mail e senha
2. Chamada `supabase.auth.signInWithPassword()`
3. Supabase retorna JWT com dados do usuário
4. `user` global é populado com `{ email, name }`

**Entrada no App:**
1. Confere se o cadastro foi aprovado (`user_access`)
2. Carrega favoritos (`favorites`) e lojas registradas (`stores`)
3. Verifica se a base da Receita foi atualizada (aviso no topo)
4. Renderiza a aba "Lojas Novas"

**Logout:**
1. Chama `supabase.auth.signOut()`
2. Limpa todas as variáveis de estado global
3. Exibe tela de autenticação

---

### 6.5. Validação de CNPJ

Painel "Consultar CNPJ" na aba Lojas Novas. A consulta vai para `GET /api/cnpj` (BrasilAPI, ReceitaWS e
CNPJá em paralelo); se o servidor falhar, o navegador tenta a BrasilAPI direto.

**Dados extraídos:** razão social, data de abertura, porte (ME/EPP/Médio/Grande), CNAE principal, MEI.

### 6.6. Paginação

- 30 empresas por página na aba Lojas Novas
- Controles: Anterior / Páginas numéricas / Próxima
- Ellipsis (`...`) para ocultar páginas intermediárias quando há muitas

---

## 7. Autenticação e Segurança

### 7.1. Mecanismo de Autenticação

O sistema usa **Supabase Auth** com JWT (JSON Web Tokens):

- O cliente guarda o token JWT no `localStorage` via Supabase JS Client
- Cada requisição ao Supabase envia o JWT no header `Authorization: Bearer {token}`
- O Supabase valida o JWT e extrai o e-mail do usuário para aplicar as políticas de RLS

### 7.2. Criação de Usuários

A criação de usuários usa a **Admin API** do Supabase via backend Python:

```python
POST {SUPABASE_URL}/auth/v1/admin/users
Authorization: Bearer {SUPABASE_SERVICE_KEY}
Content-Type: application/json

{
  "email": "...",
  "password": "...",
  "email_confirm": true,
  "user_metadata": { "name": "..." }
}
```

Isso garante que o usuário já começa com e-mail confirmado, sem necessidade de verificação.

### 7.3. Validação de Senha (Frontend)

Regras mínimas de senha:
- Mínimo 6 caracteres
- Pelo menos 1 letra maiúscula
- Pelo menos 1 número
- Pelo menos 1 caractere especial (`!@#$%^&*`)

### 7.4. Row Level Security

Todas as tabelas têm RLS ativo. A política central:

```sql
user_email = auth.jwt() ->> 'email'
```

Isso garante que um usuário nunca consegue ler ou escrever dados de outro usuário, mesmo que conheça o UUID ou e-mail da outra pessoa.

### 7.5. Exposição de Chaves

| Chave | Localização | Nível de Exposição |
|---|---|---|
| `SUPABASE_SERVICE_KEY` | Backend (`.env`) | Privada — tem permissão de admin |
| `SUPABASE_URL` | Frontend (HTML inline) | Pública — necessário para o SDK |
| `SUPABASE_ANON_KEY` | Frontend (HTML inline) | Pública — acesso limitado pelo RLS |

---

## 8. Regras de Negócio

### 8.1. Classificação de Leads

A função `validateLead(d)` classifica a empresa consultada no painel de CNPJ:

| Status | Label | Critério | Badge |
|---|---|---|---|
| `bloqueado` | 🚫 Bloqueado | Nome com palavra bloqueada OU CNAE `4520006` | Vermelho |
| `filtrado` | ⚠️ MEI | `is_mei === true` | Amarelo |
| `comprador` | ℹ️ Frotista/Comprador | CNAE `4930202` (transporte rodoviário) | Azul |
| `novo` | 🆕 Lead Novo | CNAE vendedor + aberta nos últimos 3 anos (desde 1º/jan de `ANO_NOVAS`) | Verde brilhante |
| `aprovado` | ✅ Vendedor Confirmado | CNAE em `CNAE_VENDEDOR` | Verde |
| `potencial` | ⚠️ Verificar | Porte ME/EPP sem CNAE definitivo | Amarelo |
| `indefinido` | ℹ️ Não Mapeado | Nenhum critério se aplicou | Cinza |

**CNAEs Mapeados:**

```javascript
CNAE_VENDEDOR  = ['4530702', '4530705']  // Comércio de pneus: atacado (02) e varejo (05) — autopeças fica de fora
CNAE_COMPRADOR = ['4930202']              // Transporte rodoviário de cargas
CNAE_BLOQUEADO = ['4520006']              // Serviços de borracharia
```

### 8.2. Identificação de Leads Novos

Uma empresa é marcada como **Lead Novo** quando o CNAE é de comércio de pneus e ela foi
aberta nos **últimos 3 anos** (ano atual e os dois anteriores — `ANO_NOVAS` no frontend).

### 8.3. Lojas e frotistas da Receita Federal

A tabela `lojas_receita` guarda as lojas de pneus (CNAE 4530-7/02 e 4530-7/05) e os frotistas
(CNAE 4930-2/02, transporte rodoviário de carga — o mesmo `CNAE_COMPRADOR` da validação de lead)
**ativos**, abertos desde 2010 (`ANO_MIN` no script, `ANO_RECEITA` na tela; ~180 mil empresas, ~100 MB),
sem MEI e sem borracharia/recapagem no nome. Só os abertos nos últimos 3 anos (`ANO_NOVAS`) levam o selo
verde "🆕 nova" e contam como Lead Novo; os mais antigos aparecem com selo amarelo e sem borda verde. O tipo sai da coluna `cnae`. Origem: dados abertos do CNPJ da
Receita (publicados 1x por mês).

- **Atualização:** `scripts/atualizar_receita.py`, rodado pelo GitHub Actions
  (`.github/workflows/atualizar-receita.yml`) nos dias 10 e 25, ou à mão pelo botão *Run workflow*.
  Baixa ~6,5 GB, filtra e **substitui** a lista (upsert por CNPJ + remove o que não está na base nova).
  Se a lista nova vier com menos da metade das lojas atuais, nada é alterado (proteção contra base corrompida).
  Teste local sem gravar: `python scripts/atualizar_receita.py --teste saida.csv`.
- **Aba Lojas Novas** (`ctab = 'r'`, `GET /api/receita-lojas?tipo=lojas|frotistas`): empresas da Receita
  com filtros de tipo (Lojas de pneus / Frotistas), estado (ou Brasil todo), cidade, ano e mês.
  Lojas já registradas no CRM (`company_id = cnpj:<número>`) não se repetem.
- **Aba Exportar:** o card "Lojas Novas (Receita Federal)" exporta em CSV, Excel ou PDF com os **mesmos filtros**
  da aba Lojas Novas (`rfParams()`), buscando todas as páginas em blocos de 1000 (`exportar=1` na API).
  PDF limitado a 3000 registros.
- **Aviso de atualização** (`GET /api/receita-info`): ao entrar, a tela consulta o mês da base carregada
  (`referencia`) e compara com o último mês visto, guardado no `localStorage` por usuário (`al_rf_ref:<email>`).
  Se mudou, aparece um aviso no topo ("A base da Receita foi atualizada…") com o botão *Ver Lojas Novas*;
  ele some quando é fechado. No primeiro acesso só registra o mês, sem aviso.
- **Custo:** nenhuma API paga; só consultas ao nosso Supabase.

---

## 9. Integrações Externas

### 9.1. Dados abertos do CNPJ (Receita Federal)

Baixados pelo `scripts/atualizar_receita.py` (GitHub Actions) para montar a tabela `lojas_receita`.

### 9.2. APIs de CNPJ

Chamadas pelo backend (`/api/cnpj`), em paralelo:

| API | Endpoint |
|---|---|
| BrasilAPI | `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` |
| ReceitaWS | `https://receitaws.com.br/v1/cnpj/{cnpj}` |
| CNPJá | `https://open.cnpja.com/office/{cnpj}` |

### 9.3. WhatsApp

Link direto para conversa via `https://wa.me/{telefone}` (sem API, apenas URL).

### 9.4. Mapas

Botão "🗺 Maps" nos cards: link público de pesquisa do Google Maps (`https://www.google.com/maps/search/?api=1&query=...`).
Só abre o site em outra aba — não usa chave nem API paga.

---

## 10. Variáveis de Ambiente

### Backend (`.env`)

| Variável | Descrição | Obrigatório |
|---|---|---|
| `SUPABASE_URL` | URL do projeto Supabase | Sim |
| `SUPABASE_SERVICE_KEY` | Chave `service_role` do Supabase (admin) | Sim |
| `PORT` | Porta do servidor local (padrão: 3000) | Não |

### Frontend (embutido no HTML)

As seguintes constantes estão diretamente no código do `index.html`:

| Constante | Descrição |
|---|---|
| `SUPA_URL` | URL pública do projeto Supabase |
| `SUPA_KEY` | Chave `anon` do Supabase (pública, controlada pelo RLS) |

> **Atenção:** As chaves embutidas no frontend são públicas por design — o acesso é controlado pelo Row Level Security do Supabase.

---

## 11. Deploy e Infraestrutura

### 11.1. Vercel

O projeto está configurado para deploy no **Vercel**.

**Arquivo `vercel.json`:**
```json
{
  "rewrites": [{ "source": "/api/(.*)", "destination": "/api/index.py" }],
  "headers": [
    {
      "source": "/(.*).html",
      "headers": [
        { "key": "Cache-Control", "value": "no-cache" },
        { "key": "Pragma", "value": "no-cache" },
        { "key": "Expires", "value": "0" }
      ]
    }
  ]
}
```

- Arquivos estáticos (`index.html`, `css/`) são servidos diretamente
- Rotas `/api/*` são redirecionadas para a serverless function `api/index.py`
- HTML é servido sempre sem cache para garantir atualização imediata

**Variáveis de ambiente no Vercel:**
Configure em Dashboard → Projeto → Settings → Environment Variables:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**Arquivo `.vercelignore`** (excluídos do deploy):
- `venv/`
- `dist/`
- `node_modules/`
- `.env`

### 11.2. Limitações do Vercel (Plano Gratuito)

- **Timeout por requisição:** 10 segundos
- **Impacto:** a exportação da base da Receita é feita em blocos de 1000 linhas para caber nesse limite

---

## 12. Setup Local

### Pré-requisitos

- Python 3.8+
- Projeto no Supabase com tabelas criadas

### Passo a Passo

**1. Clone o repositório**
```bash
git clone <url-do-repositorio>
cd autolead_python
```

**2. Crie o ambiente virtual**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

**3. Instale as dependências**
```bash
pip install -r requirements.txt
```

**4. Configure as variáveis de ambiente**
```bash
cp .env.example .env
```

Edite `.env`:
```env
PORT=3000
SUPABASE_SERVICE_KEY=sua_service_role_key_aqui
SUPABASE_URL=https://SEU_PROJETO.supabase.co
```

**5. Configure o banco de dados**

Execute o arquivo `supabase_setup.sql` no **Supabase SQL Editor** (Dashboard → SQL Editor).

**6. Inicie o servidor**
```bash
python api/index.py
# ou
INICIAR_WINDOWS.bat   # Windows
bash INICIAR_MAC.sh   # Mac/Linux
```

O sistema estará disponível em `http://localhost:3000`.

---

## 13. Dependências

### Python (`requirements.txt`)

```
flask==3.0.3
flask-cors==4.0.1
requests==2.31.0
python-dotenv==1.0.0
```

### JavaScript (CDN — embutidas no HTML)

| Biblioteca | URL | Versão |
|---|---|---|
| Supabase JS Client | `cdn.jsdelivr.net/npm/@supabase/supabase-js@2` | v2 |
| SheetJS (XLSX) | `cdn.sheetjs.com/xlsx-0.20.3/...` | 0.20.3 |
| Google Fonts (Inter) | `fonts.googleapis.com` | — |

---

*Documentação gerada em 2026-05-08.*
