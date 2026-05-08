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

**AutoLead Brasil** é uma plataforma web B2B para prospecção de leads no setor automotivo de pneus. O sistema permite que usuários autenticados busquem empresas vendedoras (distribuidoras, atacadistas e lojas de pneus) e empresas compradoras (transportadoras e frotistas) usando a Google Places API, validem os leads via consulta de CNPJ, gerenciem um CRM próprio e exportem os dados.

### Objetivos do Sistema

- Encontrar leads qualificados de pneus por estado e/ou cidade
- Diferenciar automaticamente vendedores de compradores
- Identificar empresas novas (abertura < 24 meses) como leads prioritários
- Bloquear empresas irrelevantes (borracharias, oficinas, etc.)
- Validar e enriquecer dados via CNPJ
- Gerenciar o relacionamento com leads em um CRM integrado
- Reduzir custo de API via cache de 7 dias

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
│  │  js/app.js      │      │                          │  │
│  │  (estáticos)    │      │  POST /api/register      │  │
│  └────────┬────────┘      │  GET  /api/buscar        │  │
│           │               │  GET  /api/details       │  │
│           │               └──────────┬───────────────┘  │
└───────────┼──────────────────────────┼──────────────────┘
            │                          │
            │ Supabase JS SDK          │ Requests
            ▼                          ▼
┌───────────────────────┐   ┌──────────────────────────┐
│     SUPABASE          │   │   GOOGLE PLACES API      │
│  (PostgreSQL + Auth)  │   │  (Text Search + Details) │
│                       │   └──────────────────────────┘
│  searches             │
│  search_history       │   ┌──────────────────────────┐
│  stores               │   │   CNPJ APIs (fallback)   │
│  favorites            │   │  BrasilAPI               │
│  search_limits        │   │  ReceitaWS               │
└───────────────────────┘   │  CNPJ.ws                 │
                            └──────────────────────────┘
```

### Estrutura de Arquivos

```
autolead_python/
├── api/
│   └── index.py              # Backend Flask — serverless function
├── css/
│   └── styles.css            # Estilos (492 linhas) — tema dark/light
├── js/
│   └── app.js                # Arquivo legado (JS ativo está inline no index.html)
├── dist/                     # Ignorado pelo Vercel
├── index.html                # Frontend completo com JS inline (1677 linhas)
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

### 4.1. Tabela `searches` — Cache de Pesquisas

Armazena os resultados das buscas por 7 dias para evitar retrabalho com a API do Google.

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email  TEXT NOT NULL
search_key  TEXT NOT NULL   -- chave composta: "SP_sao_paulo_vendedores"
state       TEXT NOT NULL   -- UF (ex: "SP")
city        TEXT            -- Cidade (pode ser null para busca por estado)
results     JSONB           -- Array de empresas retornadas
updated_at  TIMESTAMPTZ DEFAULT now()

UNIQUE (user_email, search_key)
```

**Formato da `search_key`:** `{UF}_{cidade}_{modo}` → ex: `SP_sao_paulo_vendedores`

**TTL:** 7 dias (verificado no frontend por comparação com `updated_at`)

---

### 4.2. Tabela `search_history` — Histórico Permanente

Registra cada pesquisa realizada. Diferente de `searches`, não tem restrição UNIQUE — acumula todos os registros.

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email   TEXT NOT NULL
state        TEXT NOT NULL    -- UF
city         TEXT             -- Cidade (nullable)
mode         TEXT             -- 'vendedores' ou 'compradores'
result_count INTEGER          -- Quantidade de empresas encontradas
results      JSONB            -- Snapshot completo das empresas
searched_at  TIMESTAMPTZ DEFAULT now()
```

**Uso:** Permite restaurar resultados passados sem consumir a API do Google.

---

### 4.3. Tabela `stores` — CRM de Lojas

Registro de lojas para acompanhamento comercial.

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email   TEXT
company_name TEXT NOT NULL
company_id   TEXT UNIQUE      -- place_id do Google (garante sem duplicatas)
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
place_id     TEXT NOT NULL    -- place_id do Google
company_data JSONB            -- Snapshot dos dados da empresa
created_at   TIMESTAMPTZ DEFAULT now()

UNIQUE (user_email, place_id)
```

---

### 4.5. Tabela `search_limits` — Rate Limiting Diário

Controla o número de buscas por usuário por dia e por modo.

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_email  TEXT NOT NULL
search_key  TEXT NOT NULL    -- 'vendedores' ou 'compradores'
search_date DATE NOT NULL    -- Data da contagem
count       INTEGER          -- Número de buscas realizadas naquele dia

UNIQUE (user_email, search_key, search_date)
```

**Limite:** 10 buscas por dia por modo (vendedores e compradores contados separadamente).

---

### 4.6. Row Level Security (RLS)

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

### 4.7. Trigger — Auto-confirmação de E-mail

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

### 5.1. Configurações Globais

```python
MAX_PAGES      = 2      # Máximo de páginas por query na Google Places API
PAGE_DELAY     = 2      # Delay entre páginas (segundos)
MAX_CITIES     = 3      # Máximo de cidades por estado em busca sem cidade
MAX_RETRIES    = 2      # Tentativas de retry por requisição
BACKOFF_BASE   = 1      # Backoff exponencial (1s, 2s)
```

### 5.2. Palavras Bloqueadas

Empresas cujo nome contém qualquer um desses termos são automaticamente filtradas:

```python
_BLOCK_WORDS = frozenset({
    'borracharia', 'borrachas', 'reforma de pneu', 'conserto de pneu',
    'recapagem', 'recauchutagem', 'vulcanização', 'alinhamento',
    'balanceamento', 'oficina', 'mecânica', 'auto center',
    'funilaria', 'pintura automotiva'
})
```

### 5.3. Endpoints

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

#### `GET /api/buscar`

Busca empresas via Google Places Text Search API.

**Parâmetros de query string:**

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `uf` | Sim | Sigla do estado (ex: `SP`) |
| `query` | Sim | Termo de busca (ex: `loja de pneus`) |
| `cidade` | Não | Nome da cidade (busca localizada) |
| `max_cidades` | Não | Número máximo de cidades a buscar (padrão: 3) |

**Resposta:**
```json
{
  "total_unique": 42,
  "results": [
    {
      "place_id": "ChIJ...",
      "name": "Nome da Empresa",
      "formatted_address": "Rua X, Cidade - SP",
      "rating": 4.5,
      "types": ["store"],
      "geometry": { "location": { "lat": -23.5, "lng": -46.6 } }
    }
  ],
  "errors": []
}
```

**Algoritmo de busca:**
1. Se `cidade` fornecida: busca diretamente naquela cidade
2. Se `cidade` vazia: obtém lista de municípios do estado via BrasilAPI e itera pelas `max_cidades` primeiras, com fallback para a capital do estado
3. Para cada city+query: faz requisição ao Google Places com paginação (até `MAX_PAGES`)
4. Implementa retry com backoff exponencial (`MAX_RETRIES` tentativas)
5. Deduplica por `place_id` mantendo o resultado com maior rating
6. Filtra empresas cujo nome contenha palavras em `_BLOCK_WORDS`

---

#### `GET /api/details`

Retorna detalhes completos de uma empresa pelo place_id.

**Parâmetros:**

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `place_id` | Sim | ID do Google Places |

**Resposta:** Resposta direta da Google Places Details API com campos:
- `name`, `formatted_address`, `formatted_phone_number`
- `website`, `opening_hours`, `geometry`
- `rating`, `user_ratings_total`

---

### 5.4. Tratamento de Erros

- Falha na Google Places API: retorna `{"error": "..."}` com status 500
- Parâmetro ausente: retorna `{"error": "..."}` com status 400
- Erro na criação de usuário: retorna `{"ok": false, "error": "..."}` com status 200

---

## 6. Frontend — Interface Web

**Arquivo:** [index.html](index.html) (1677 linhas com JS inline) + [css/styles.css](css/styles.css)

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
      <!-- Abas: Buscar / Favoritos / Histórico / Exportar / Lojas -->
    </main>

    <!-- Mobile: Bottom Nav -->
    <nav id="bottom-nav">
      5 botões de navegação
    </nav>

  </div>

  <!-- Modal: Registrar Loja -->
  <div id="modal-store">...</div>
</body>
```

### 6.2. Abas do Sistema

| Aba | ID | Funcionalidade Principal |
|---|---|---|
| Buscar | `'b'` | Pesquisa de empresas com filtros e cards |
| Favoritos | `'f'` | Lista de empresas favoritadas com busca |
| Histórico | `'h'` | Pesquisas passadas com restauração e filtros |
| Exportar | `'e'` | Exportação em CSV, Excel e PDF |
| Lojas (CRM) | `'s'` | Tabela de lojas registradas com edição inline |

### 6.3. Estado Global (JavaScript)

Todas as variáveis globais que controlam o estado da aplicação:

```javascript
let user        = null         // { email, name } — usuário logado
let cos         = []           // Array de empresas da busca atual
let favs        = new Set()    // place_ids dos favoritos
let favData     = new Map()    // Dados completos: place_id → company object
let hist        = []           // Histórico de pesquisas da sessão
let searchMode  = 'vendedores' // Modo ativo: 'vendedores' | 'compradores'
let filterType  = 'todos'      // Filtro ativo: 'atacado' | 'loja' | 'frotista' | 'novo'
let theme       = 'dark'       // Tema: 'dark' | 'light' (persistido no localStorage)
let dailyLimits = {}           // { vendedores: N, compradores: N } — uso diário
let storeFilter = 'todos'      // Filtro CRM: status da loja
let favSearch   = ''           // Texto de busca nos favoritos
let currentPage = 0            // Página atual (paginação de resultados)
const PAGE_SIZE = 30           // Resultados por página
```

### 6.4. Estrutura de Dados de uma Empresa

Cada empresa no array `cos` segue este formato:

```javascript
{
  _idx:           number,        // Índice no array cos[]
  id:             string,        // place_id do Google Places
  nome:           string,        // Nome da empresa
  endereco:       string,        // Endereço formatado completo
  cidade:         string,        // Cidade
  uf:             string,        // Estado (UF)
  telefone:       string,        // Telefone formatado
  website:        string,        // URL do site
  avaliacao:      string,        // Rating (ex: "4.5 ★")
  tipo:           string,        // 'Atacadista' | 'Loja de Pneus' | 'Frotista' | 'Empresa'
  lat:            number | null, // Latitude
  lon:            number | null, // Longitude
  abertura:       string | null, // Data de abertura (YYYY-MM-DD)
  gmaps_url:      string,        // Link direto para Google Maps
  _detailsLoaded: boolean,       // Se telefone/site já foram carregados
  _isNovo:        boolean,       // true se empresa < 24 meses
  _leadStatus:    string,        // Status calculado do lead (veja seção 8.3)
  cnpj:           string,        // CNPJ formatado
  porte:          string,        // Porte da empresa (BrasilAPI)
  cnae:           string,        // Descrição do CNAE principal
  cnae_code:      string         // Código do CNAE principal
}
```

### 6.5. Fluxo de Autenticação

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
1. Carrega favoritos do Supabase (`favorites` table)
2. Carrega contadores de limite diário (`search_limits` table)
3. Tenta restaurar última busca do histórico automaticamente
4. Renderiza a aba "Buscar"

**Logout:**
1. Chama `supabase.auth.signOut()`
2. Limpa todas as variáveis de estado global
3. Exibe tela de autenticação

---

### 6.6. Fluxo de Busca de Empresas

```
Usuário seleciona UF + (cidade opcional) + modo
           │
           ▼
    Verifica rate limit
    (< 10 buscas hoje?)
           │
     Sim ──┴── Não → Exibe erro
           │
           ▼
    Gera search_key:
    "{UF}_{cidade}_{modo}"
           │
           ▼
    Verifica cache no Supabase
    (updated_at < 7 dias?)
           │
     Hit ──┴── Miss
      │         │
      │         ▼
      │   Chama GET /api/buscar
      │   (múltiplas queries)
      │         │
      │         ▼
      │   Salva no cache
      │   (upsert em searches)
      │         │
      └────┬────┘
           │
           ▼
    Salva no histórico
    (insert em search_history)
           │
           ▼
    Incrementa rate limit
    (upsert em search_limits)
           │
           ▼
    Renderiza cards com
    paginação (30/página)
```

### 6.7. Termos de Busca por Modo

**Modo Vendedores** (distribuidoras, atacadistas, lojas):
- `distribuidora de pneus`
- `atacadista de pneus`
- `loja de pneus`
- `revenda de pneus`
- `pneus truck center`

**Modo Compradores** (transportadoras e frotistas):
- `transportadora cargas`
- `empresa transporte rodoviario`
- `logistica transporte cargas`

### 6.8. Validação de CNPJ

O sistema tenta 9 combinações (3 APIs × 3 proxies CORS) com timeout de 6 segundos cada:

**APIs:**
1. BrasilAPI: `https://brasilapi.com.br/api/cnpj/v1/{cnpj}`
2. ReceitaWS: `https://receitaws.com.br/v1/cnpj/{cnpj}`
3. CNPJ.ws: `https://publica.cnpj.ws/cnpj/{cnpj}`

**Proxies CORS** (usados quando o browser bloqueia a chamada direta):
1. `corsproxy.io/?url={url}`
2. `api.allorigins.win/raw?url={url}`
3. `api.codetabs.com/v1/proxy?quest={url}`

**Dados extraídos:** razão social, data de abertura, porte (ME/EPP/Médio/Grande), CNAE principal.

### 6.9. Paginação

- 30 empresas por página (`PAGE_SIZE = 30`)
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
| `GOOGLE_API_KEY` | Backend (`.env`) | Privada — nunca exposta ao navegador |
| `SUPABASE_SERVICE_KEY` | Backend (`.env`) | Privada — tem permissão de admin |
| `SUPABASE_URL` | Frontend (HTML inline) | Pública — necessário para o SDK |
| `SUPABASE_ANON_KEY` | Frontend (HTML inline) | Pública — acesso limitado pelo RLS |

---

## 8. Regras de Negócio

### 8.1. Rate Limiting

- **Limite:** 10 buscas por dia, por usuário, por modo
- **Contagem:** Separada para vendedores e compradores
- **Chave:** `user_email + modo + data`
- **Verificação:** Antes de cada busca (bloqueia se `count >= 10`)
- **Incremento:** Após busca concluída com sucesso (upsert com `count + 1`)

### 8.2. Cache de Pesquisas

- **TTL:** 7 dias a partir de `updated_at`
- **Chave:** `user_email + search_key`
- **Comportamento:** Se o cache existir e for válido, retorna os dados armazenados sem chamar a API do Google
- **Invalidação:** O cache é sobrescrito (upsert) quando o usuário força uma nova busca

### 8.3. Classificação de Leads

A função `validateLead(d)` classifica cada empresa com base em dados de CNPJ:

| Status | Label | Critério | Badge |
|---|---|---|---|
| `bloqueado` | 🚫 Bloqueado | Nome com palavra bloqueada OU CNAE `4520006` | Vermelho |
| `filtrado` | ⚠️ MEI | `is_mei === true` | Amarelo |
| `comprador` | ℹ️ Frotista/Comprador | CNAE `4930202` (transporte rodoviário) | Azul |
| `novo` | 🆕 Lead Novo | Modo vendedores + abertura < 24 meses | Verde brilhante |
| `aprovado` | ✅ Vendedor Confirmado | CNAE em `CNAE_VENDEDOR` | Verde |
| `potencial` | ⚠️ Verificar | Porte ME/EPP sem CNAE definitivo | Amarelo |
| `indefinido` | ℹ️ Não Mapeado | Nenhum critério se aplicou | Cinza |

**CNAEs Mapeados:**

```javascript
CNAE_VENDEDOR  = ['4530701', '4530702']  // Comércio de pneus (atacado e varejo)
CNAE_COMPRADOR = ['4930202']              // Transporte rodoviário de cargas
CNAE_BLOQUEADO = ['4520006']              // Serviços de borracharia
```

### 8.4. Identificação de Leads Novos

Uma empresa é marcada como **Lead Novo** quando:
1. O sistema está no modo **Vendedores**
2. A data de abertura (extraída do CNPJ) existe
3. A diferença entre hoje e a data de abertura é menor que **24 meses**

### 8.5. Deduplicação de Resultados

O backend deduplica os resultados da Google Places API por `place_id`. Em caso de duplicata (mesma empresa retornada por queries diferentes), mantém o resultado com maior `rating`.

### 8.6. Bloqueio Automático de Empresas

O backend filtra automaticamente empresas cujo nome (em lowercase) contenha qualquer das palavras em `_BLOCK_WORDS`. Esse filtro acontece antes do retorno da API — o frontend nunca recebe essas empresas.

### 8.7. Histórico x Cache

| Característica | `searches` (Cache) | `search_history` (Histórico) |
|---|---|---|
| Unicidade | Sim (por search_key) | Não (acumula tudo) |
| Sobrescrito | Sim (upsert) | Não (sempre insert) |
| TTL | 7 dias | Permanente |
| Finalidade | Evitar chamadas à API | Registrar histórico do usuário |
| Restauração | Automática (por chave) | Manual (clique em "Ver Resultados") |

---

## 9. Integrações Externas

### 9.1. Google Places API

**Endpoints utilizados:**

| Endpoint | Uso |
|---|---|
| `/maps/api/place/textsearch/json` | Busca de empresas por texto e localização |
| `/maps/api/place/details/json` | Detalhes de uma empresa (telefone, site, horários) |

**Parâmetros da busca:**
- `query`: Termo de busca + estado/cidade
- `language`: `pt-BR`
- `region`: `BR`
- `pagetoken`: Para paginar resultados (até 2 páginas)

**Campos dos detalhes:**
- `name`, `formatted_address`, `formatted_phone_number`
- `website`, `geometry`, `rating`, `user_ratings_total`

### 9.2. BrasilAPI — Municípios

Usada pelo backend para obter a lista de municípios de um estado quando o usuário não especifica uma cidade.

**Endpoint:** `https://brasilapi.com.br/api/ibge/municipios/v1/{uf}`

### 9.3. APIs de CNPJ (Frontend)

Chamadas diretamente pelo navegador via JS:

| API | Endpoint | Prioridade |
|---|---|---|
| BrasilAPI | `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` | 1ª |
| ReceitaWS | `https://receitaws.com.br/v1/cnpj/{cnpj}` | 2ª |
| CNPJ.ws | `https://publica.cnpj.ws/cnpj/{cnpj}` | 3ª |

Em caso de erro CORS, cada API é tentada via 3 proxies públicos:
1. `https://corsproxy.io/?url={url}`
2. `https://api.allorigins.win/raw?url={url}`
3. `https://api.codetabs.com/v1/proxy?quest={url}`

**Total de tentativas:** 9 (3 APIs × 3 proxies)

### 9.4. WhatsApp

Link direto para conversa via `https://wa.me/{telefone}` (sem API, apenas URL).

### 9.5. Mapas

- **Google Maps:** Link direto para a empresa via `https://maps.google.com/?q=...`
- **OpenStreetMap:** Usado para visualização de coordenadas (lat/lon)

---

## 10. Variáveis de Ambiente

### Backend (`.env`)

| Variável | Descrição | Obrigatório |
|---|---|---|
| `GOOGLE_API_KEY` | Chave da Google Places API | Sim |
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

- Arquivos estáticos (`index.html`, `css/`, `js/`) são servidos diretamente
- Rotas `/api/*` são redirecionadas para a serverless function `api/index.py`
- HTML é servido sempre sem cache para garantir atualização imediata

**Variáveis de ambiente no Vercel:**
Configure em Dashboard → Projeto → Settings → Environment Variables:
- `GOOGLE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**Arquivo `.vercelignore`** (excluídos do deploy):
- `venv/`
- `dist/`
- `node_modules/`
- `.env`

### 11.2. Limitações do Vercel (Plano Gratuito)

- **Timeout por requisição:** 10 segundos
- **Impacto:** Buscas por estado inteiro (sem cidade) podem ultrapassar o timeout
- **Recomendação:** Especificar sempre uma cidade para buscas mais rápidas

---

## 12. Setup Local

### Pré-requisitos

- Python 3.8+
- Conta no Google Cloud com Places API ativada
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
GOOGLE_API_KEY=sua_chave_aqui
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
