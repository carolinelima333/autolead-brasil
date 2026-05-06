# AutoLead Brasil — Documentação Completa do Sistema

**Versão:** 1.0  
**Data:** Maio/2026  
**Stack:** Python/Flask + Vanilla JS + Supabase (PostgreSQL)

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura do Sistema](#2-arquitetura-do-sistema)
3. [Estrutura de Arquivos](#3-estrutura-de-arquivos)
4. [Configuração e Credenciais](#4-configuração-e-credenciais)
5. [Backend — app.py](#5-backend--apppy)
6. [Frontend — app.js](#6-frontend--appjs)
7. [Banco de Dados — Supabase](#7-banco-de-dados--supabase)
8. [APIs Externas Utilizadas](#8-apis-externas-utilizadas)
9. [Lógica de Busca e Filtragem](#9-lógica-de-busca-e-filtragem)
10. [Classificação e Validação de Leads (CNAE)](#10-classificação-e-validação-de-leads-cnae)
11. [Módulos do Frontend](#11-módulos-do-frontend)
12. [Como Executar](#12-como-executar)
13. [Fluxo Completo de uma Pesquisa](#13-fluxo-completo-de-uma-pesquisa)

---

## 1. Visão Geral

O **AutoLead Brasil** é uma plataforma web de prospecção de leads no setor automotivo (pneus), focada em dois públicos:

| Perfil | O que são | Como buscar |
|--------|-----------|-------------|
| **Vendedores** | Lojas de pneus, distribuidoras e atacadistas | Modo "🏪 Lojas & Atacadistas" |
| **Compradores** | Transportadoras e empresas com frotas | Modo "🚛 Frotistas / Compradores" |

**Funcionalidades principais:**
- Busca por estado ou cidade via Google Places API
- Filtragem automática de borracharias (serviços de reparo)
- Validação de CNAE via consulta de CNPJ
- Identificação de leads novos (empresa aberta há < 24 meses)
- Histórico de pesquisas persistido por modo (Lojas vs. Frotistas)
- Favoritos salvos por usuário no banco de dados
- CRM básico: registro de lojas com status de relacionamento
- Exportação de dados em CSV
- Consulta de CNPJ com data de abertura
- Tema claro/escuro

---

## 2. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                     NAVEGADOR (Cliente)                  │
│                                                         │
│  frontend/index.html                                    │
│  frontend/js/app.js   ◄──── toda a lógica de UI        │
│  frontend/css/styles.css                                │
│                                                         │
│  Supabase JS SDK (CDN) ──────────────────────────────┐  │
└──────────────────────┬──────────────────────────────┘  │
                       │ HTTP (fetch)                     │
                       ▼                                  │
┌─────────────────────────────────────────────────────┐   │
│              SERVIDOR — Flask (Python)              │   │
│                      app.py                         │   │
│                   porta 3000                        │   │
│                                                     │   │
│  GET /api/buscar   → busca no Google Places         │   │
│  GET /api/details  → detalhes de um Place           │   │
│  GET /             → serve o index.html             │   │
│  GET /<path>       → serve arquivos estáticos       │   │
└──────────────────────┬──────────────────────────────┘   │
                       │ HTTPS (requests)                  │
                       ▼                                   │
┌────────────────────────────────────┐                     │
│       Google Places API            │                     │
│  maps.googleapis.com               │                     │
│  • /place/textsearch/json          │                     │
│  • /place/details/json             │                     │
└────────────────────────────────────┘                     │
                                                           │
┌──────────────────────────────────────────────────────────┘
│                SUPABASE (PostgreSQL)
│  nbigfrdezkozzwqozvlp.supabase.co
│
│  Tabelas:
│  • searches      — cache + histórico de pesquisas
│  • favorites     — favoritos por usuário
│  • stores        — lojas registradas (CRM)
│  • search_limits — limite diário de pesquisas
└──────────────────────────────────────────────────────────

APIs externas consultadas DIRETO pelo navegador (sem proxy):
  • BrasilAPI — IBGE municípios e CNPJ
  • ReceitaWS — consulta CNPJ (fallback)
  • CNPJ.ws   — consulta CNPJ (fallback)
```

### Fluxo de dados resumido

```
Usuário → escolhe estado/cidade + modo de busca
       → frontend chama /api/buscar N vezes (1 por termo)
       → backend chama Google Places (com paginação 3 páginas)
       → backend filtra nomes com palavras bloqueadas
       → backend retorna resultados deduplicados
       → frontend salva cache no Supabase (searches)
       → frontend exibe cards paginados (30/página)
       → usuário consulta CNPJ → frontend chama BrasilAPI diretamente
       → frontend valida CNAE e marca o lead
```

---

## 3. Estrutura de Arquivos

```
autolead_python/
│
├── app.py                  ← servidor Flask (backend completo)
├── .env                    ← variáveis de ambiente (NÃO versionar)
├── requirements.txt        ← dependências Python
├── supabase_setup.sql      ← script de criação das tabelas no Supabase
├── DOCUMENTACAO.md         ← este arquivo
│
└── frontend/
    ├── index.html          ← HTML único (SPA)
    ├── css/
    │   └── styles.css      ← estilos completos (dark/light mode)
    └── js/
        └── app.js          ← toda a lógica do frontend
```

---

## 4. Configuração e Credenciais

### Arquivo `.env` (raiz do projeto)

```env
GOOGLE_API_KEY=AIzaSyAijbBmi0VPf_NPJ5LRM-rXvmKRAOILp_A
PORT=3000
```

> ⚠️ Este arquivo **nunca deve ser commitado** no Git. Adicione `.env` ao `.gitignore`.

### Credenciais Supabase (hardcoded no frontend — `app.js`)

```javascript
const SUPA_URL = 'https://nbigfrdezkozzwqozvlp.supabase.co';
const SUPA_KEY = 'sb_publishable_uH_lieeSpbZHADvMAcDAwA_uqppix7p';
```

> A `SUPA_KEY` é a chave **pública/publishable** (anon key). É seguro expô-la no navegador.  
> A chave **secret/service role** (`sb_secret_...`) jamais deve ir para o frontend — ela bypassa todo o RLS.

### Google Cloud — APIs que precisam estar ativadas

No [Google Cloud Console](https://console.cloud.google.com), com a chave `AIzaSyAijbBmi0VPf_NPJ5LRM-rXvmKRAOILp_A`:

| API | Para que serve |
|-----|----------------|
| **Places API** | Busca de empresas por texto e localização |
| **Maps JavaScript API** | (opcional) Links de mapa |

---

## 5. Backend — app.py

### Dependências Python (`requirements.txt`)

```
flask==3.0.3
flask-cors==4.0.1
requests==2.31.0
python-dotenv==1.0.0
```

### Constantes de configuração

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `_MAX_PAGES` | 3 | Máximo de páginas por query no Google Places (3 × 20 = 60 resultados) |
| `_TOKEN_DELAY` | 2.0s | Delay obrigatório entre páginas (exigência da API do Google) |
| `_MAX_CITIES` | 10 | Cidades a varrer quando nenhuma cidade é informada |
| `_RETRY` | 3 | Tentativas por requisição ao Google |
| `_BACKOFF_BASE` | 2 | Base do backoff exponencial (2¹s, 2²s entre tentativas) |

### Termos de busca

```python
SEARCH_TERMS = [                    # modo Vendedores
    'distribuidora de pneus',
    'atacadista de pneus',
    'loja de pneus',
    'revenda de pneus',
    'pneus truck center',
]

SEARCH_TERMS_COMPRADORES = [        # modo Compradores (referência)
    'transportadora cargas',
    'empresa transporte rodoviario',
    'logistica transporte cargas',
]
```

> Os termos de compradores são enviados pelo frontend. O backend aceita qualquer `query` via parâmetro.

### Palavras bloqueadas no nome da empresa

```python
_BLOCK_WORDS = frozenset({
    'borracharia', 'borrachas', 'borracheiro',
    'reforma de pneu', 'conserto de pneu', 'recapagem',
})
```

Qualquer empresa cujo nome contenha uma dessas palavras é **descartada** nos resultados.

### Capitais por UF (fallback)

Quando a BrasilAPI não retorna municípios, o sistema usa a capital como ponto de busca:

```python
_CAPITAIS = {
    'AC': 'Rio Branco', 'AL': 'Maceió', 'AM': 'Manaus', 'AP': 'Macapá',
    'BA': 'Salvador',   'CE': 'Fortaleza', 'DF': 'Brasília', 'ES': 'Vitória',
    'GO': 'Goiânia',    'MA': 'São Luís', 'MG': 'Belo Horizonte',
    # ... todos os 27 estados
}
```

### Funções internas

#### `_is_blocked_name(name: str) → bool`
Verifica se o nome da empresa contém alguma palavra da lista `_BLOCK_WORDS`.

#### `_places_request(query, api_key, page_token?) → dict`
Faz **uma** requisição à Places Text Search API. Implementa retry com backoff exponencial (tentativas: imediata → 2s → 4s).

**Parâmetros fixos enviados ao Google:**
```
language = pt-BR
region   = BR
```

#### `_paginate(query, api_key) → (list[dict], list[str])`
Percorre até 3 páginas de resultados. O `next_page_token` retornado pelo Google exige espera de ≥2s antes de uso.

```
Página 1: resultado imediato
Página 2: sleep(2s) + usa next_page_token
Página 3: sleep(2s) + usa next_page_token
```

Retorna `(resultados, erros)`.

#### `_get_cidades(uf: str) → list[str]`
Busca municípios via BrasilAPI IBGE.

- **DF**: retorna `['Brasília']` diretamente (sem chamar a API — DF tem apenas 1 município oficial)
- **Demais estados**: chama `https://brasilapi.com.br/api/ibge/municipios/v1/{UF}` e normaliza nomes para Title Case
- **Falha na API**: retorna `[]` → o chamador usa a capital como fallback

#### `_format(raw: dict) → dict`
Normaliza um resultado bruto do Places:

```python
{
    'place_id':          str,   # ID único do Google
    'name':              str,   # nome da empresa
    'formatted_address': str,   # endereço completo
    'rating':            float, # avaliação (None se não disponível)
    'opening_hours':     dict,  # horários (vazio na maioria)
    'phone':             '',    # obtido via /api/details
    'website':           '',    # obtido via /api/details
    'place_types':       list,  # categorias do Google
}
```

#### `buscar_empresas(estado_uf, cidade, query, api_key, max_cidades) → dict`
Função principal de busca. Orquestra toda a lógica:

1. Se `cidade` fornecida → busca só nessa cidade
2. Se sem cidade → obtém lista de municípios via `_get_cidades()`; usa os primeiros `max_cidades`; fallback para capital se BrasilAPI falhar
3. Para cada localidade: monta query `"{termo} em {cidade}, {UF}, Brasil"` e chama `_paginate()`
4. Deduplicação por `place_id` (mantém o de maior rating quando há duplicata)
5. Filtra nomes bloqueados com `_is_blocked_name()`

**Retorno:**
```json
{
  "total_unique": 42,
  "results": [...],
  "errors": []
}
```

### Endpoints HTTP

#### `GET /api/buscar`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `uf` | string | ✅ | Sigla do estado (ex: `GO`) |
| `query` | string | ✅ | Termo de busca (ex: `loja de pneus`) |
| `cidade` | string | ❌ | Nome da cidade (vazio = busca todo o estado) |
| `max_cidades` | int | ❌ | Máximo de cidades (padrão: 10) |

**Exemplo:**
```
GET /api/buscar?uf=GO&query=distribuidora+de+pneus&cidade=Goiânia
```

**Resposta:**
```json
{
  "total_unique": 18,
  "results": [
    {
      "place_id": "ChIJabc123...",
      "name": "Pneus Goiás Distribuidora",
      "formatted_address": "Av. Anhanguera, 1234 - Goiânia, GO",
      "rating": 4.2,
      "opening_hours": {},
      "phone": "",
      "website": "",
      "place_types": ["car_repair", "store"]
    }
  ],
  "errors": []
}
```

#### `GET /api/details`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `place_id` | string | ✅ | ID do Google Places |

Retorna o JSON bruto do Google Place Details com: `formatted_phone_number`, `website`, `geometry`, `url`.

**Campos solicitados ao Google:**
```
place_id, name, formatted_address, formatted_phone_number,
rating, geometry, types, website, url
```

#### `GET /` e `GET /<path>`
Serve os arquivos estáticos do diretório `frontend/`.

---

## 6. Frontend — app.js

### Constantes globais

```javascript
const SUPA_URL = 'https://nbigfrdezkozzwqozvlp.supabase.co';
const SUPA_KEY = 'sb_publishable_uH_lieeSpbZHADvMAcDAwA_uqppix7p';

const TERMS_VENDEDORES  = ['distribuidora de pneus', 'atacadista de pneus',
                           'loja de pneus', 'revenda de pneus', 'pneus truck center'];
const TERMS_COMPRADORES = ['transportadora cargas',
                           'empresa transporte rodoviario', 'logistica transporte cargas'];

// CNAEs para validação
const CNAE_VENDEDOR  = ['4530701', '4530702'];   // Atacado e Varejo de pneus
const CNAE_COMPRADOR = ['4930202'];              // Transporte rodoviário de cargas
const CNAE_BLOQUEADO = ['4520006'];              // Serviços de borracharia

const MAX_DAILY     = 10;    // pesquisas por dia por localidade
const CACHE_TTL_DAYS = 7;    // dias antes de o cache expirar
const PAGE_SIZE     = 30;    // empresas por página
```

### Variáveis de estado (globais)

| Variável | Tipo | Descrição |
|----------|------|-----------|
| `sb` | Supabase Client | instância do Supabase JS SDK |
| `user` | Object | `{ email, name }` do usuário logado |
| `cos` | Array | lista de empresas da busca atual |
| `favs` | Set | place_ids favoritados (sessão) |
| `favData` | Map | place_id → dados completos da empresa (banco) |
| `hist` | Array | histórico em memória da sessão |
| `filterType` | string | filtro ativo: `todos`, `atacado`, `loja`, `frotista`, `novo` |
| `searchMode` | string | modo de busca: `vendedores` ou `compradores` |
| `currentPage` | int | página atual dos resultados |
| `theme` | string | `dark` ou `light` |

### Chave de cache (searchKey)

O identificador único de cada pesquisa inclui o modo:

```
{UF}_{modo}                          → ex: GO_vendedores
{UF}_{cidade_snake_case}_{modo}      → ex: GO_goiania_vendedores
DF_compradores
SP_sao_paulo_compradores
```

Isso garante que "GO — Lojas" e "GO — Frotistas" sejam caches independentes.

### Funções principais

#### Autenticação (local — sem Supabase Auth)

```
doAuth()     → valida email/senha localmente, define user, chama loadFavs(), vai para aba 'b'
logout()     → limpa user, cos, favs, favData, hist
```

> A autenticação é **local/simulada** — não há validação contra o banco. Qualquer email/senha válidos dão acesso.

#### Navegação

```
go(tab)      → troca de aba: 'b' (busca), 'f' (favoritos), 'h' (histórico), 'e' (exportar), 's' (lojas)
render()     → chama a função de página correspondente à aba ativa
```

#### Busca principal

```
buscar()
  1. Monta searchKey com modo
  2. checkRateLimit() → bloqueia se ≥10 pesquisas hoje para esta chave
  3. checkCache()     → se cache válido (< 7 dias), restaura e exibe
  4. Para cada termo do modo ativo:
     → apiBuscarTermo(uf, cidade, termo) → GET /api/buscar
     → deduplica por place_id
  5. textToCard() para cada resultado
  6. incrementRateLimit()
  7. saveToCache() → Supabase
  8. exibir()
```

#### Exibição paginada

```
exibir()
  → aplica filtro (filterType)
  → fatia lista: cos[page*30 .. (page+1)*30]
  → renderiza cards + paginação
  
mkPagination(current, total)
  → botões ← Anterior, números, Próxima →
  → reticências para muitas páginas

setPage(n)
  → muda currentPage, chama exibir(), scroll to top
```

#### Cards de empresa

```
mkCard(co)
  → renderiza card com:
     - nome, avaliação, tipo, endereço
     - badge de lead (🆕 Lead Novo / ✅ Aprovado / 🚫 Descartado / 🚛 Frotista)
     - botão "📞 Carregar contato" (lazy — só chama /api/details ao clicar)
     - ações: Maps, Site, WhatsApp, Favoritar, CNPJ, Registrar

loadDetails(idx)
  → chama GET /api/details para o place_id
  → atualiza co com telefone, website, gmaps_url
  → re-renderiza o card com replaceWith()
```

#### Validação de CNPJ e Lead

```
bCNPJCard(idx)
  → chama fetchCNPJ(raw)
  → chama validateLead(d)
  → persiste abertura, porte, cnae, _leadStatus, _isNovo em cos[idx]
  → exibe badge de status no card
  → re-renderiza o card se status relevante

validateLead(d)
  → analisa: cnae_code, nome, porte, is_mei, data_inicio_atividade
  → retorna: { status, label, cls, msg }
  → statuses: 'bloqueado' | 'filtrado' | 'comprador' | 'novo' | 'aprovado' | 'potencial' | 'indefinido'

isWithin24Months(isoDate)
  → retorna true se a empresa foi aberta nos últimos 24 meses
```

#### Favoritos

```
loadFavs()       → carrega do Supabase (tabela favorites) ao login
tgFav(idx)       → toggle: salva ou remove do Supabase + atualiza favs + favData
unfavById(pid)   → remove favorito pelo place_id (usado na aba Favoritos)
pFavs(c)         → renderiza aba, mescla favData (banco) + cos (sessão)
mkFavCard(co)    → card simplificado com botão "★ Remover"
```

#### Histórico

```
pHist(c)           → carrega tabela searches do Supabase, mescla com hist em memória
                   → exibe badge do modo (🏪 ou 🚛)
restoreSearch(key) → lê cache, restaura searchMode, carrega cos, vai para aba 'b'
deleteHistory(key) → exclui da tabela searches + remove do hist em memória
```

#### Lojas registradas (CRM)

```
pStores(c)        → carrega lojas do usuário (filtro por user_email)
openStoreModal(idx) → abre modal, pré-preenche com dados do card (se idx fornecido)
submitStore()     → insere na tabela stores com user_email
deleteStore(id)   → exclui por id com confirmação
```

#### Exportação CSV

```
expCSV(modo)
  → 'todas'    → todos cos
  → 'favs'     → cos filtrados por favs
  → 'abertura' → cos com co.abertura preenchido
  → gera Blob CSV com BOM UTF-8 e força download
```

#### Consulta CNPJ avulsa

```
qCNPJ()      → consulta painel superior, exibe card completo com:
             → situação (Ativa/Inativa), badge do lead, Lead Novo
             → razão social, data abertura, tempo de atividade
             → município, telefone, CNAE, porte

fetchCNPJ(raw)
  → tenta 3 APIs em cascata, cada uma com 3 proxies CORS:
     1. BrasilAPI  → https://brasilapi.com.br/api/cnpj/v1/{cnpj}
     2. ReceitaWS  → https://receitaws.com.br/v1/cnpj/{cnpj}
     3. CNPJ.ws   → https://publica.cnpj.ws/cnpj/{cnpj}
  → proxies: corsproxy.io, allorigins.win, codetabs.com
  → timeout: 6s por tentativa
```

---

## 7. Banco de Dados — Supabase

**Projeto:** `nbigfrdezkozzwqozvlp`  
**URL:** `https://nbigfrdezkozzwqozvlp.supabase.co`  
**RLS:** Desabilitado em todas as tabelas (a autenticação é local, não via Supabase Auth)

### Script de setup (`supabase_setup.sql`)

Execute no Supabase → **SQL Editor → New query → Run**.

### Tabela: `searches`

Cache e histórico de pesquisas.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | gerado automaticamente |
| `search_key` | TEXT UNIQUE | identificador da pesquisa (ex: `GO_vendedores`, `SP_sao_paulo_compradores`) |
| `state` | TEXT | sigla do estado (ex: `GO`) |
| `city` | TEXT (null) | nome da cidade, ou null para busca estadual |
| `results` | JSONB | array completo de empresas encontradas |
| `updated_at` | TIMESTAMPTZ | data/hora da última atualização |

**Índice implícito:** UNIQUE em `search_key` (usado pelo `upsert`).

**TTL:** O frontend considera o cache expirado após 7 dias (`CACHE_TTL_DAYS`).

### Tabela: `favorites`

Favoritos por usuário.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | gerado automaticamente |
| `user_email` | TEXT | e-mail do usuário |
| `place_id` | TEXT | ID do Google Places |
| `company_data` | JSONB | dados completos da empresa (snapshot) |
| `created_at` | TIMESTAMPTZ | data do favorito |

**Constraint:** UNIQUE(`user_email`, `place_id`) — evita duplicatas por usuário.

### Tabela: `stores`

CRM de lojas registradas.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | gerado automaticamente |
| `user_email` | TEXT | e-mail do usuário dono do registro |
| `company_name` | TEXT | nome da empresa (obrigatório) |
| `company_id` | TEXT (null) | place_id do Google (se veio de um card) |
| `phone` | TEXT (null) | telefone |
| `address` | TEXT (null) | endereço |
| `city` | TEXT (null) | cidade |
| `state` | TEXT (null) | UF |
| `status` | TEXT | `contato` / `cliente` / `retorno` |
| `notes` | TEXT (null) | observações livres |
| `created_at` | TIMESTAMPTZ | data do cadastro |

### Tabela: `search_limits`

Controle de rate limit (máximo 10 pesquisas/dia por localidade+modo).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | UUID (PK) | gerado automaticamente |
| `user_email` | TEXT | e-mail do usuário |
| `search_key` | TEXT | chave da pesquisa (inclui o modo) |
| `search_date` | DATE | data da contagem |
| `count` | INTEGER | número de pesquisas realizadas |

**Constraint:** UNIQUE(`user_email`, `search_key`, `search_date`).

---

## 8. APIs Externas Utilizadas

### 8.1 Google Places Text Search API

**URL:** `https://maps.googleapis.com/maps/api/place/textsearch/json`  
**Chave:** `AIzaSyAijbBmi0VPf_NPJ5LRM-rXvmKRAOILp_A`  
**Chamada por:** Backend (Python/Flask) — a chave nunca é exposta ao navegador.

**Parâmetros enviados:**
```
query    = "distribuidora de pneus em Goiânia, GO, Brasil"
key      = GOOGLE_API_KEY
language = pt-BR
region   = BR
pagetoken = <next_page_token> (quando paginando)
```

**Limites:**
- Até 20 resultados por página
- Até 3 páginas via `next_page_token` = máx. **60 resultados por query**
- Requer espera de ≥2 segundos entre páginas com `next_page_token`
- Cobrança: por requisição (veja Google Maps Platform Pricing)

### 8.2 Google Place Details API

**URL:** `https://maps.googleapis.com/maps/api/place/details/json`  
**Chave:** `AIzaSyAijbBmi0VPf_NPJ5LRM-rXvmKRAOILp_A`  
**Chamada por:** Backend via `GET /api/details`

**Campos solicitados:**
```
place_id, name, formatted_address, formatted_phone_number,
rating, geometry, types, website, url
```

**Quando é chamado:** Apenas quando o usuário clica em "📞 Carregar contato" em um card (lazy loading).

### 8.3 BrasilAPI — Municípios (IBGE)

**URL:** `https://brasilapi.com.br/api/ibge/municipios/v1/{UF}`  
**Chave:** Nenhuma (API pública gratuita)  
**Chamada por:** Backend Python

Retorna lista de municípios do estado. Usado para dividir a busca estadual por cidades.

**Caso especial DF:** A API é ignorada para DF — o sistema retorna `['Brasília']` diretamente.

### 8.4 BrasilAPI — CNPJ

**URL:** `https://brasilapi.com.br/api/cnpj/v1/{CNPJ}`  
**Chave:** Nenhuma (API pública gratuita)  
**Chamada por:** Frontend (navegador)

Campos usados:
- `razao_social`, `nome_fantasia`
- `descricao_situacao_cadastral` → ativa/inativa
- `data_inicio_atividade` → para calcular se é Lead Novo (< 24 meses)
- `cnae_fiscal` → código CNAE numérico
- `cnae_fiscal_descricao` → descrição do CNAE
- `porte` → MICRO EMPRESA / EMPRESA DE PEQUENO PORTE / DEMAIS
- `natureza_juridica` → natureza (ex: "206-2 Sociedade Empresária Limitada")
- `opcao_pelo_mei` → true/false → identifica MEI
- `ddd_telefone_1` + `telefone_1` → telefone

### 8.5 ReceitaWS (fallback CNPJ)

**URL:** `https://receitaws.com.br/v1/cnpj/{CNPJ}`  
**Chave:** Nenhuma  
**Chamada por:** Frontend (via proxy CORS se necessário)

Usado como fallback quando a BrasilAPI falha ou retorna erro.

### 8.6 CNPJ.ws (fallback CNPJ)

**URL:** `https://publica.cnpj.ws/cnpj/{CNPJ}`  
**Chave:** Nenhuma  
**Chamada por:** Frontend (via proxy CORS se necessário)

Segundo fallback para consulta de CNPJ.

### 8.7 Proxies CORS (fallback para as APIs de CNPJ)

Quando uma API de CNPJ bloqueia a requisição do navegador por CORS, o frontend tenta automaticamente via:

1. `https://corsproxy.io/?{url}`
2. `https://api.allorigins.win/raw?url={url}`
3. `https://api.codetabs.com/v1/proxy?quest={url}`

### 8.8 Supabase JS SDK

**CDN:** `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`  
**Chave pública:** `sb_publishable_uH_lieeSpbZHADvMAcDAwA_uqppix7p`

Usado para: leitura/gravação nas 4 tabelas (searches, favorites, stores, search_limits).

---

## 9. Lógica de Busca e Filtragem

### 9.1 Modos de busca

| Modo | Termos enviados à API | Objetivo |
|------|-----------------------|----------|
| `vendedores` | distribuidora de pneus, atacadista de pneus, loja de pneus, revenda de pneus, pneus truck center | Lojas e distribuidoras |
| `compradores` | transportadora cargas, empresa transporte rodoviario, logistica transporte cargas | Frotas e transportadoras |

### 9.2 Estratégia de cobertura por estado

```
Se cidade informada:
  → 1 query: "{termo} em {cidade}, {UF}, Brasil"

Se SEM cidade:
  → BrasilAPI retorna todos os municípios do estado
  → Seleciona os primeiros 10 (max_cidades)
  → Para cada um: "{termo} em {cidade}, {UF}, Brasil"
  → Fallback 1: capital do estado (se BrasilAPI falhar)
  → Fallback 2: "{UF}, Brasil" (se capital não disponível)
  
Caso especial DF:
  → Retorna ['Brasília'] diretamente (sem chamar BrasilAPI)
```

### 9.3 Paginação do Google Places

```
Cada query → até 3 páginas × 20 resultados = máx. 60 por query
Portanto: 10 cidades × 5 termos × 60 = até 3.000 resultados brutos

Após deduplicação por place_id (mantém maior rating): muito menos
Após filtro de nomes bloqueados: ainda menos
```

### 9.4 Filtro de nomes (backend)

Empresas descartadas automaticamente se o **nome** contém:
- `borracharia`, `borrachas`, `borracheiro`
- `reforma de pneu`, `conserto de pneu`, `recapagem`

### 9.5 Deduplicação

```python
# Backend — por place_id, mantém maior rating:
if pid not in seen:
    seen[pid] = r
else:
    if r.get('rating', 0) > seen[pid].get('rating', 0):
        seen[pid] = r

# Frontend — deduplicação adicional entre chamadas de diferentes termos:
if (!seenIds.has(p.place_id)) {
    seenIds.add(p.place_id);
    allResults.push(p);
}
```

### 9.6 Cache (Supabase)

```
Ao pesquisar:
  1. Verifica tabela searches por search_key
  2. Se encontrado e updated_at < 7 dias → usa cache (sem chamar o Google)
  3. Se não encontrado ou expirado → chama Google, salva no banco

search_key = "{UF}_{modo}" ou "{UF}_{cidade}_{modo}"
Exemplos: "GO_vendedores", "SP_sao_paulo_compradores"
```

### 9.7 Rate Limit

Máximo de **10 pesquisas por dia** por `(user_email, search_key)`. Controlado na tabela `search_limits`. Nota: pesquisas que batem o cache não consomem o limite.

---

## 10. Classificação e Validação de Leads (CNAE)

A validação ocorre **somente após o usuário consultar o CNPJ** de uma empresa. O resultado fica salvo no objeto do card para filtros e badges.

### Tabela de CNAEs

| Código | Descrição | Classificação |
|--------|-----------|---------------|
| **4530-7/01** | Comércio por atacado de pneumáticos e câmaras-de-ar | ✅ Vendedor Aprovado |
| **4530-7/02** | Comércio varejista de pneumáticos e câmaras-de-ar | ✅ Vendedor Aprovado |
| **4930-2/02** | Transporte rodoviário de carga, exceto produtos perigosos e mudanças | 🚛 Frotista/Comprador |
| **4520-0/06** | Serviços de borracharia para veículos automotores | 🚫 Descartado |

### Regras de classificação (`validateLead`)

```
1. Nome contém palavra bloqueada OU CNAE = 4520006
   → status: 'bloqueado' | 🚫 Descartado

2. is_mei = true (Microempreendedor Individual)
   → status: 'filtrado' | ⚠️ MEI — fora do foco comercial

3. CNAE = 4930202 (Transporte)
   → status: 'comprador' | 🚛 Frotista

4. CNAE em [4530701, 4530702] E empresa aberta há < 24 meses
   → status: 'novo' | 🆕 Lead Novo — prioridade alta

5. CNAE em [4530701, 4530702]
   → status: 'aprovado' | ✅ Aprovado

6. Porte = MICRO EMPRESA ou EMPRESA DE PEQUENO PORTE
   → status: 'potencial' | 📦 ME/EPP — Verificar

7. Demais casos
   → status: 'indefinido' | ❓ Verificar
```

### Identificação de Lead Novo

```javascript
isWithin24Months(isoDate)
  → calcula diferença entre hoje e data_inicio_atividade
  → se ≤ 24 meses → Lead Novo (badge verde 🆕)
```

### Filtros visuais disponíveis

| Pill | Filtra por |
|------|-----------|
| Todos | sem filtro |
| 📦 Atacadistas | `tipo === 'Atacadista de Pneus'` |
| 🔵 Lojas de Pneus | `tipo === 'Loja de Pneus'` |
| 🚛 Frotistas | `tipo === 'Frotista / Transportadora'` |
| 🆕 Leads Novos | `_isNovo === true` (requer CNPJ consultado) |

---

## 11. Módulos do Frontend

### index.html

SPA (Single Page Application) com:
- **Tela de login** (`#sc-auth`) — formulário de email/senha
- **Tela principal** (`#sc-main`) — layout com sidebar desktop + drawer mobile + bottom nav
- **Modal de Loja** (`#modal-store`) — formulário CRM
- **Sidebar desktop** — navegação, info do usuário, toggle de tema, botão de sair
- **Drawer mobile** — menu lateral deslizante com overlay
- **Bottom nav mobile** — 5 abas fixas na parte inferior

### styles.css — Temas

```css
/* Tema escuro (padrão) */
:root {
  --blk: #0d0d0d;   --g1: #161616;  --g2: #1f1f1f;  --g3: #272727;
  --txt: #d4d4d4;   --yel: #FFC107; --green: #22c55e; --red: #ef4444;
  --blue: #60a5fa;
}

/* Tema claro */
[data-theme="light"] {
  --blk: #f0f0f0;   --g1: #ffffff;  --g2: #f7f7f7;  --g3: #eeeeee;
  --txt: #1a1a1a;
}
```

O tema é persistido no `localStorage` com chave `al_theme`.

### Responsividade

| Breakpoint | Layout |
|------------|--------|
| > 768px | Sidebar fixa à esquerda, conteúdo à direita |
| ≤ 768px | Topbar + Drawer lateral + Bottom navigation (5 ícones) |

---

## 12. Como Executar

### Pré-requisitos

```bash
Python 3.10+
pip
```

### 1. Instalar dependências

```bash
cd C:\Projetos\autolead_python
python -m venv venv
.\venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 2. Configurar o `.env`

O arquivo já existe na raiz com:
```env
GOOGLE_API_KEY=AIzaSyAijbBmi0VPf_NPJ5LRM-rXvmKRAOILp_A
PORT=3000
```

### 3. Criar tabelas no Supabase

Execute o conteúdo de `supabase_setup.sql` no **SQL Editor** do Supabase:  
→ https://supabase.com → seu projeto → SQL Editor → New query → colar e Run

### 4. Iniciar o servidor

```bash
python app.py
```

Saída esperada:
```
✅ AutoLead Brasil rodando!
👉 Acesse: http://localhost:3000
🔑 Google API Key: configurada
```

### 5. Acessar

Abrir no navegador: `http://localhost:3000`

Use qualquer e-mail e senha (mín. 6 caracteres) para entrar.

---

## 13. Fluxo Completo de uma Pesquisa

```
1. Usuário faz login (qualquer email/senha válidos)
   → loadFavs() carrega favoritos do Supabase

2. Usuário seleciona:
   - Modo: "🏪 Lojas & Atacadistas"
   - Estado: GO
   - Cidade: (vazia)
   - Clica "Buscar agora"

3. Frontend monta searchKey = "GO_vendedores"

4. checkRateLimit("GO_vendedores")
   → se ≥ 10 pesquisas hoje: bloqueia

5. checkCache("GO_vendedores")
   → se cache < 7 dias: exibe direto (sem Google) ← FAST PATH

6. Para cada termo em TERMS_VENDEDORES (5 termos):
   → GET /api/buscar?uf=GO&query=distribuidora+de+pneus
   
7. Backend recebe query:
   → _get_cidades('GO') → lista de municípios via BrasilAPI
   → Seleciona primeiros 10: Goiânia, Aparecida de Goiânia, Anápolis...
   → Para cada cidade:
      → _paginate("distribuidora de pneus em Goiânia, GO, Brasil", api_key)
      → Página 1: imediata (20 resultados)
      → Página 2: sleep(2s) + next_page_token (se houver)
      → Página 3: sleep(2s) + next_page_token (se houver)
   → Deduplicação por place_id
   → Filtra nomes com "borracharia", "recapagem" etc.
   → Retorna JSON com resultados

8. Frontend deduplica entre termos (5 chamadas)

9. textToCard() converte cada resultado para formato de card
   (sem telefone/site ainda — serão carregados sob demanda)

10. currentPage = 0, filterType = 'todos'

11. saveToCache("GO_vendedores", 'GO', '', cos) → Supabase

12. incrementRateLimit("GO_vendedores") → Supabase

13. exibir() → mostra primeiros 30 cards + paginação

14. Usuário clica "📞 Carregar contato" em um card:
    → GET /api/details?place_id=ChIJ...
    → Backend chama Google Place Details (com a chave segura)
    → Card atualiza com telefone e link Maps

15. Usuário clica "🔎 CNPJ" e digita o número:
    → fetchCNPJ() tenta BrasilAPI, ReceitaWS, CNPJ.ws
    → validateLead() classifica o lead
    → Se CNAE 4530702 e aberta há 8 meses → "🆕 Lead Novo"
    → Card exibe badge verde

16. Usuário clica "☆ Favoritar":
    → tgFav() → INSERT em favorites (Supabase)
    → Badge muda para "★ Salvo"

17. Usuário vai em Histórico:
    → pHist() carrega tabela searches do Supabase
    → Vê "GO (estado inteiro) · 🏪 Lojas & Atacadistas"
    → Clica "↩ Restaurar" → cos restaurado sem consumir Google
```

---

*Documentação gerada em 06/05/2026 — AutoLead Brasil v1.0*
