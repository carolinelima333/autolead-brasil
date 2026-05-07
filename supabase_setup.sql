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
-- ──────────────────────────────────────────────────────────────
ALTER TABLE searches      DISABLE ROW LEVEL SECURITY;
ALTER TABLE stores        DISABLE ROW LEVEL SECURITY;
ALTER TABLE favorites     DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_limits DISABLE ROW LEVEL SECURITY;

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
