-- ══════════════════════════════════════════════════════════════
-- AutoLead Brasil — Setup das tabelas no Supabase
-- Execute este script no Supabase: Dashboard → SQL Editor → New query
-- ══════════════════════════════════════════════════════════════

-- 1. Histórico / cache de pesquisas (state + city + resultados JSON)
CREATE TABLE IF NOT EXISTS searches (
  id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email  TEXT        NOT NULL,
  search_key  TEXT        NOT NULL,
  state       TEXT        NOT NULL,
  city        TEXT,
  results     JSONB,
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_email, search_key)
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
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (company_id)
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
-- ROW LEVEL SECURITY (RLS)
-- ──────────────────────────────────────────────────────────────
ALTER TABLE searches      ENABLE ROW LEVEL SECURITY;
ALTER TABLE stores        ENABLE ROW LEVEL SECURITY;
ALTER TABLE favorites     ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_limits ENABLE ROW LEVEL SECURITY;

-- searches: cada usuário vê apenas o seu próprio histórico
DROP POLICY IF EXISTS searches_select ON searches;
DROP POLICY IF EXISTS searches_insert ON searches;
DROP POLICY IF EXISTS searches_update ON searches;
DROP POLICY IF EXISTS searches_delete ON searches;
DROP POLICY IF EXISTS searches_own ON searches;

CREATE POLICY searches_own ON searches
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');

-- stores: cada usuário acessa apenas os seus próprios registros
DROP POLICY IF EXISTS stores_own ON stores;

CREATE POLICY stores_own ON stores
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');

-- favorites: cada usuário acessa apenas os seus próprios favoritos
DROP POLICY IF EXISTS favorites_own ON favorites;

CREATE POLICY favorites_own ON favorites
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');

-- search_limits: cada usuário acessa apenas o seu próprio contador
DROP POLICY IF EXISTS search_limits_own ON search_limits;

CREATE POLICY search_limits_own ON search_limits
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');

-- ──────────────────────────────────────────────────────────────
-- AUTO-CONFIRMAR E-MAIL NO CADASTRO (sem envio de confirmação)
-- Execute este bloco no Supabase SQL Editor para que novos
-- usuários entrem diretamente no sistema após se cadastrar.
-- ──────────────────────────────────────────────────────────────

-- Confirmar todos os usuários já existentes não confirmados
UPDATE auth.users SET email_confirmed_at = NOW() WHERE email_confirmed_at IS NULL;

-- Função que auto-confirma o e-mail de qualquer novo usuário
CREATE OR REPLACE FUNCTION public.auto_confirm_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE auth.users
  SET email_confirmed_at = NOW()
  WHERE id = NEW.id AND email_confirmed_at IS NULL;
  RETURN NEW;
END;
$$;

-- Trigger: dispara após cada novo cadastro
DROP TRIGGER IF EXISTS trg_auto_confirm_user ON auth.users;
CREATE TRIGGER trg_auto_confirm_user
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.auto_confirm_new_user();

-- ──────────────────────────────────────────────────────────────
-- MIGRATION: recriar searches com a estrutura correta
-- (searches é apenas cache — sem perda de dados críticos)
-- ──────────────────────────────────────────────────────────────
-- ──────────────────────────────────────────────────────────────
-- MIGRATION: adicionar UNIQUE em stores.company_id
-- (necessário para upsert com onConflict: 'company_id')
-- ──────────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'stores_company_id_key' AND table_name = 'stores'
  ) THEN
    ALTER TABLE stores ADD CONSTRAINT stores_company_id_key UNIQUE (company_id);
  END IF;
END $$;

DROP TABLE IF EXISTS searches CASCADE;
CREATE TABLE searches (
  id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email  TEXT        NOT NULL,
  search_key  TEXT        NOT NULL,
  state       TEXT        NOT NULL,
  city        TEXT,
  results     JSONB,
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_email, search_key)
);
ALTER TABLE searches ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS searches_own ON searches;
CREATE POLICY searches_own ON searches
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');

-- ──────────────────────────────────────────────────────────────
-- 5. Histórico permanente de pesquisas (sem UNIQUE — acumula tudo)
--    Cada busca real na API gera uma linha aqui.
--    Os resultados ficam salvos para restaurar sem chamar a API.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_history (
  id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_email   TEXT        NOT NULL,
  state        TEXT        NOT NULL,
  city         TEXT,
  mode         TEXT        NOT NULL DEFAULT 'vendedores',
  result_count INTEGER     DEFAULT 0,
  results      JSONB,
  searched_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS search_history_own ON search_history;
CREATE POLICY search_history_own ON search_history
  FOR ALL TO authenticated
  USING      (user_email = auth.jwt() ->> 'email')
  WITH CHECK (user_email = auth.jwt() ->> 'email');
