-- ══════════════════════════════════════════════════════════════
-- AutoLead Brasil — Setup das tabelas no Supabase
-- Execute este script no Supabase: Dashboard → SQL Editor → New query
-- ══════════════════════════════════════════════════════════════

-- 1. Histórico / cache de pesquisas (state + city + resultados JSON)
CREATE TABLE IF NOT EXISTS searches (
  id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  search_key  TEXT        UNIQUE NOT NULL,
  state       TEXT        NOT NULL,
  city        TEXT,
  results     JSONB,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Lojas registradas (CRM)
CREATE TABLE IF NOT EXISTS stores (
  id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email   TEXT,
  company_name TEXT        NOT NULL,
  company_id   TEXT,
  phone        TEXT,
  address      TEXT,
  city         TEXT,
  state        TEXT,
  status       TEXT        DEFAULT 'contato',
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Favoritos (persistido por usuário)
CREATE TABLE IF NOT EXISTS favorites (
  id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email   TEXT        NOT NULL,
  place_id     TEXT        NOT NULL,
  company_data JSONB,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_email, place_id)
);

-- 4. Limite diário de buscas por usuário
CREATE TABLE IF NOT EXISTS search_limits (
  id          UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email  TEXT  NOT NULL,
  search_key  TEXT  NOT NULL,
  search_date DATE  NOT NULL,
  count       INTEGER DEFAULT 0,
  UNIQUE (user_email, search_key, search_date)
);

-- ──────────────────────────────────────────────────────────────
-- DESABILITAR RLS em todas as tabelas
-- (o app usa autenticação local, não Supabase Auth)
-- ──────────────────────────────────────────────────────────────
ALTER TABLE searches      DISABLE ROW LEVEL SECURITY;
ALTER TABLE stores        DISABLE ROW LEVEL SECURITY;
ALTER TABLE favorites     DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_limits DISABLE ROW LEVEL SECURITY;
