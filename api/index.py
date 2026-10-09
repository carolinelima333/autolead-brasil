from __future__ import annotations

from flask import Flask, request, jsonify, send_from_directory, abort
import hashlib
import requests
import logging
import time
import os
import re
import secrets
import string
import unicodedata
from datetime import datetime, timezone
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# Raiz do projeto — index.html, css/ e js/ ficam aqui (local e Vercel)
_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = _BASE_DIR

# static_folder=None: sem a rota /static automática do Flask, que serviria
# qualquer arquivo da raiz (inclusive o .env). Os estáticos ficam na whitelist abaixo.
# Sem CORS: o frontend é servido do mesmo domínio, então outros sites não chamam a API.
app = Flask(__name__, static_folder=None)


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    if request.path.startswith('/api/'):
        resp.headers.setdefault('Cache-Control', 'no-store')
    return resp

# .strip(): valores colados no painel da Vercel podem vir com quebra de linha no fim
GOOGLE_API_KEY      = os.getenv('GOOGLE_API_KEY', '').strip()
SUPABASE_URL        = os.getenv('SUPABASE_URL', 'https://nbigfrdezkozzwqozvlp.supabase.co').strip().rstrip('/')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '').strip()
ADMIN_EMAIL         = os.getenv('ADMIN_EMAIL', 'carolinelima313@gmail.com').strip().lower()

_MAX_PAGES    = 2
_TOKEN_DELAY  = 2.0
_MAX_CITIES   = 3
_RETRY        = 2
_BACKOFF_BASE = 1

_BLOCK_WORDS = frozenset({
    'borracharia', 'borrachas', 'borracheiro',
    'reforma de pneu', 'conserto de pneu', 'recapagem', 'recauchutagem',
    'vulcanização', 'vulcanizacao', 'alinhamento', 'balanceamento',
    'oficina', 'mecânica', 'mecanica', 'auto center', 'autocenter',
    'funilaria', 'funileiro', 'pintura automotiva',
})

_CAPITAIS: dict[str, str] = {
    'AC': 'Rio Branco',     'AL': 'Maceió',           'AM': 'Manaus',
    'AP': 'Macapá',         'BA': 'Salvador',          'CE': 'Fortaleza',
    'DF': 'Brasília',       'ES': 'Vitória',           'GO': 'Goiânia',
    'MA': 'São Luís',       'MG': 'Belo Horizonte',    'MS': 'Campo Grande',
    'MT': 'Cuiabá',         'PA': 'Belém',             'PB': 'João Pessoa',
    'PE': 'Recife',         'PI': 'Teresina',          'PR': 'Curitiba',
    'RJ': 'Rio de Janeiro', 'RN': 'Natal',             'RO': 'Porto Velho',
    'RR': 'Boa Vista',      'RS': 'Porto Alegre',      'SC': 'Florianópolis',
    'SE': 'Aracaju',        'SP': 'São Paulo',         'TO': 'Palmas',
}


def _is_blocked_name(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in _BLOCK_WORDS)


def _places_request(query: str, api_key: str, page_token: Optional[str] = None) -> dict:
    params: dict = {
        'query':    query,
        'key':      api_key,
        'language': 'pt-BR',
        'region':   'BR',
    }
    if page_token:
        params['pagetoken'] = page_token

    for attempt in range(_RETRY):
        try:
            resp = requests.get(
                'https://maps.googleapis.com/maps/api/place/textsearch/json',
                params=params,
                timeout=12,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            wait = _BACKOFF_BASE ** attempt
            logger.warning('[places] tentativa %d/%d falhou — %s — retry em %ds',
                           attempt + 1, _RETRY, exc, wait)
            if attempt < _RETRY - 1:
                time.sleep(wait)

    return {'status': 'NETWORK_ERROR', 'results': []}


def _paginate(query: str, api_key: str) -> tuple[list[dict], list[str]]:
    results:    list[dict] = []
    errors:     list[str]  = []
    page_token: Optional[str] = None

    for page in range(_MAX_PAGES):
        if page > 0:
            time.sleep(_TOKEN_DELAY)

        data   = _places_request(query, api_key, page_token)
        status = data.get('status', 'UNKNOWN')

        if status == 'OK':
            batch = data.get('results', [])
            results.extend(batch)
            logger.info('[paginate] p%d — %d resultado(s) — "%s"', page + 1, len(batch), query[:70])
            page_token = data.get('next_page_token')
            if not page_token:
                break
        elif status == 'ZERO_RESULTS':
            break
        elif status in ('REQUEST_DENIED', 'INVALID_REQUEST'):
            msg = f'{status}: {data.get("error_message", "")}'
            errors.append(msg)
            logger.error('[paginate] %s', msg)
            break
        elif status == 'OVER_QUERY_LIMIT':
            errors.append('OVER_QUERY_LIMIT')
            logger.warning('[paginate] rate limit atingido')
            break
        else:
            errors.append(f'status={status}')
            logger.warning('[paginate] status inesperado: %s', status)
            break

    return results, errors


def _get_cidades(uf: str) -> list[str]:
    uf = uf.upper()
    if uf == 'DF':
        return ['Brasília']
    try:
        resp = requests.get(
            f'https://brasilapi.com.br/api/ibge/municipios/v1/{uf}',
            timeout=10,
        )
        resp.raise_for_status()
        cidades = [m['nome'].title() for m in resp.json()]
        logger.info('[ibge] %d municípios para %s', len(cidades), uf)
        return cidades
    except Exception as exc:
        logger.error('[ibge] erro ao buscar municípios de %s: %s', uf, exc)
        return []


def _format(raw: dict) -> dict:
    return {
        'place_id':          raw.get('place_id', ''),
        'name':              raw.get('name', ''),
        'formatted_address': raw.get('formatted_address', ''),
        'rating':            raw.get('rating'),
        'opening_hours':     raw.get('opening_hours', {}),
        'phone':             '',
        'website':           '',
        'place_types':       raw.get('types', []),
    }


def buscar_empresas(estado_uf: str, cidade: str, query: str,
                    api_key: str, max_cidades: int = _MAX_CITIES) -> dict:
    seen:   dict[str, dict] = {}
    errors: list[str]       = []

    if cidade:
        locais = [f'{cidade}, {estado_uf}, Brasil']
        logger.info('[buscar] modo cidade — %s/%s — query="%s"', cidade, estado_uf, query)
    else:
        cidades = _get_cidades(estado_uf)
        if cidades:
            capital = _CAPITAIS.get(estado_uf)
            if capital and capital in cidades:
                cidades = [capital] + [c for c in cidades if c != capital]
            sel    = cidades[:max_cidades]
            locais = [f'{c}, {estado_uf}, Brasil' for c in sel]
            logger.info('[buscar] modo estado — %d cidade(s) de %s — query="%s"',
                        len(sel), estado_uf, query)
        else:
            capital = _CAPITAIS.get(estado_uf, estado_uf)
            locais  = [f'{capital}, {estado_uf}, Brasil']
            logger.warning('[buscar] fallback capital — %s/%s', capital, estado_uf)

    for local in locais:
        raw, errs = _paginate(f'{query} em {local}', api_key)
        errors.extend(errs)
        for r in raw:
            pid = r.get('place_id', '')
            if not pid:
                continue
            if pid not in seen:
                seen[pid] = r
            else:
                cur = seen[pid].get('rating') or 0
                new = r.get('rating') or 0
                if new > cur:
                    seen[pid] = r

    results = [_format(r) for r in seen.values() if not _is_blocked_name(r.get('name', ''))]
    logger.info('[buscar] concluído — %d único(s), %d erro(s)', len(results), len(errors))
    return {
        'total_unique': len(results),
        'results':      results,
        'errors':       list(dict.fromkeys(errors)),
    }


# ─── ENDPOINTS ────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    """Cria usuário via Admin API do Supabase — auto-confirma sem enviar e-mail."""
    data     = request.get_json(silent=True) or {}
    email    = (data.get('email')    or '').strip()
    password = (data.get('password') or '').strip()
    name     = (data.get('name')     or '').strip()

    if not email or not password or not name:
        return jsonify({'ok': False, 'error': 'Dados incompletos'}), 400
    if not SUPABASE_SERVICE_KEY:
        return jsonify({'ok': False, 'error': 'SUPABASE_SERVICE_KEY não configurada no servidor'}), 500

    try:
        resp = requests.post(
            f'{SUPABASE_URL}/auth/v1/admin/users',
            headers=_sb_headers(),
            json={
                'email':          email,
                'password':       password,
                'user_metadata':  {'name': name},
                'email_confirm':  True,
            },
            timeout=10,
        )
        body = resp.json()
        if resp.status_code in (200, 201):
            logger.info('[register] usuário criado: %s', email)
            return jsonify({'ok': True})

        msg = body.get('message') or body.get('error') or 'Erro ao criar conta'
        if 'already registered' in msg.lower() or 'already exists' in msg.lower():
            msg = 'Este e-mail já está cadastrado. Faça login.'
        logger.warning('[register] falha para %s: %s', email, msg)
        return jsonify({'ok': False, 'error': msg}), 400
    except Exception as exc:
        logger.error('[register] %s', exc)
        return jsonify({'ok': False, 'error': 'Erro ao criar conta. Tente novamente.'}), 500


# ─── ADMINISTRAÇÃO DE USUÁRIOS ────────────────────────────────

def _sb_headers() -> dict:
    headers = {'apikey': SUPABASE_SERVICE_KEY, 'Content-Type': 'application/json'}
    # Chave legada (JWT service_role) também vai no Bearer; as novas (sb_secret_) só no apikey
    if SUPABASE_SERVICE_KEY.startswith('eyJ'):
        headers['Authorization'] = f'Bearer {SUPABASE_SERVICE_KEY}'
    return headers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_AUTH_CACHE: dict[str, tuple[str, bool, float]] = {}
_AUTH_TTL = 300  # segundos — evita validar o token a cada chamada de detalhes


def _require_user():
    """Exige usuário logado e aprovado (protege a cota paga do Google).
    Retorna None se autorizado, ou a resposta de erro pronta."""
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.lower().startswith('bearer ') else ''
    if not token:
        return jsonify({'ok': False, 'error': 'Faça login para usar o sistema'}), 401
    if not SUPABASE_SERVICE_KEY:
        return jsonify({'ok': False, 'error': 'SUPABASE_SERVICE_KEY não configurada no servidor'}), 500

    key = hashlib.sha256(token.encode()).hexdigest()
    hit = _AUTH_CACHE.get(key)
    if hit and hit[2] > time.time():
        email, approved = hit[0], hit[1]
    else:
        try:
            resp = requests.get(f'{SUPABASE_URL}/auth/v1/user',
                                headers={'apikey': SUPABASE_SERVICE_KEY, 'Authorization': f'Bearer {token}'},
                                timeout=10)
            if not resp.ok:
                return jsonify({'ok': False, 'error': 'Sessão expirada — saia e entre novamente'}), 401
            user = resp.json()
            email = (user.get('email') or '').lower()
            approved = email == ADMIN_EMAIL
            if not approved:
                r2 = requests.get(f'{SUPABASE_URL}/rest/v1/user_access', headers=_sb_headers(),
                                  params={'select': 'status', 'user_id': f"eq.{user.get('id', '')}"}, timeout=10)
                rows = r2.json() if r2.ok else []
                approved = bool(rows) and rows[0].get('status') == 'aprovado'
        except Exception as exc:
            logger.error('[auth] validação do token: %s', exc)
            return jsonify({'ok': False, 'error': 'Falha ao validar sessão'}), 500
        if len(_AUTH_CACHE) > 500:
            _AUTH_CACHE.clear()
        _AUTH_CACHE[key] = (email, approved, time.time() + _AUTH_TTL)

    if not approved:
        return jsonify({'ok': False, 'error': 'Acesso não aprovado pela administradora'}), 403
    return None


def _require_admin():
    """Valida o token do Supabase enviado pelo navegador e confere se é a adm.
    Retorna None se autorizado, ou a resposta de erro pronta."""
    if not SUPABASE_SERVICE_KEY:
        return jsonify({'ok': False, 'error': 'SUPABASE_SERVICE_KEY não configurada no servidor'}), 500
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.lower().startswith('bearer ') else ''
    if not token:
        return jsonify({'ok': False, 'error': 'Não autenticado'}), 401
    try:
        resp = requests.get(
            f'{SUPABASE_URL}/auth/v1/user',
            headers={'apikey': SUPABASE_SERVICE_KEY, 'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        if not resp.ok:
            logger.warning('[admin] token recusado (%d): %s', resp.status_code, resp.text[:200])
            msg = ('Chave SUPABASE_SERVICE_KEY inválida no servidor'
                   if 'api key' in resp.text.lower() else 'Sessão inválida — saia e entre novamente')
            return jsonify({'ok': False, 'error': msg}), 401
        email = (resp.json().get('email') or '').lower()
    except Exception as exc:
        logger.error('[admin] validação do token: %s', exc)
        return jsonify({'ok': False, 'error': 'Falha ao validar sessão'}), 500
    if email != ADMIN_EMAIL:
        return jsonify({'ok': False, 'error': 'Acesso restrito à administradora'}), 403
    return None


def _temp_password() -> str:
    """Senha temporária que já atende à regra de senha do sistema."""
    return (secrets.choice(string.ascii_uppercase)
            + secrets.token_urlsafe(6).replace('-', 'x').replace('_', 'y')
            + secrets.choice(string.digits) + '!')


@app.route('/api/reset-request', methods=['POST'])
def api_reset_request():
    """Usuário (deslogado) pede reset de senha — fica pendente para a adm."""
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'ok': False, 'error': 'E-mail inválido'}), 400
    if not SUPABASE_SERVICE_KEY:
        return jsonify({'ok': False, 'error': 'SUPABASE_SERVICE_KEY não configurada no servidor'}), 500
    try:
        requests.patch(
            f'{SUPABASE_URL}/rest/v1/user_access',
            headers={**_sb_headers(), 'Prefer': 'return=minimal'},
            params={'email': f'eq.{email}'},
            json={'reset_requested_at': _now_iso()},
            timeout=10,
        )
    except Exception as exc:
        logger.error('[reset-request] %s', exc)
        return jsonify({'ok': False, 'error': 'Erro ao registrar pedido'}), 500
    # Resposta igual exista ou não o e-mail, para não revelar quem tem conta
    return jsonify({'ok': True})


@app.route('/api/admin-users')
def api_admin_users():
    err = _require_admin()
    if err:
        return err
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/user_access',
        headers=_sb_headers(),
        params={'select': '*', 'order': 'created_at.desc'},
        timeout=10,
    )
    if not resp.ok:
        return jsonify({'ok': False, 'error': resp.text}), 500
    return jsonify({'ok': True, 'users': resp.json()})


def _target_user(user_id: str):
    resp = requests.get(
        f'{SUPABASE_URL}/rest/v1/user_access',
        headers=_sb_headers(),
        params={'select': 'user_id,email', 'user_id': f'eq.{user_id}'},
        timeout=10,
    )
    rows = resp.json() if resp.ok else []
    return rows[0] if rows else None


@app.route('/api/admin-decide', methods=['POST'])
def api_admin_decide():
    err = _require_admin()
    if err:
        return err
    data    = request.get_json(silent=True) or {}
    user_id = (data.get('user_id') or '').strip()
    status  = (data.get('status')  or '').strip()
    if status not in ('aprovado', 'recusado'):
        return jsonify({'ok': False, 'error': 'Status inválido'}), 400
    target = _target_user(user_id) if user_id else None
    if not target:
        return jsonify({'ok': False, 'error': 'Usuário não encontrado'}), 404
    if target['email'].lower() == ADMIN_EMAIL:
        return jsonify({'ok': False, 'error': 'A conta da administradora não pode ser alterada'}), 400
    resp = requests.patch(
        f'{SUPABASE_URL}/rest/v1/user_access',
        headers={**_sb_headers(), 'Prefer': 'return=minimal'},
        params={'user_id': f'eq.{user_id}'},
        json={'status': status, 'decided_at': _now_iso()},
        timeout=10,
    )
    if not resp.ok:
        return jsonify({'ok': False, 'error': resp.text}), 500
    logger.info('[admin] %s -> %s', target['email'], status)
    return jsonify({'ok': True})


@app.route('/api/admin-reset', methods=['POST'])
def api_admin_reset():
    """Define uma senha temporária e devolve para a adm repassar ao usuário."""
    err = _require_admin()
    if err:
        return err
    data    = request.get_json(silent=True) or {}
    user_id = (data.get('user_id') or '').strip()
    target  = _target_user(user_id) if user_id else None
    if not target:
        return jsonify({'ok': False, 'error': 'Usuário não encontrado'}), 404
    password = _temp_password()
    resp = requests.put(
        f'{SUPABASE_URL}/auth/v1/admin/users/{user_id}',
        headers=_sb_headers(),
        json={'password': password},
        timeout=10,
    )
    if not resp.ok:
        return jsonify({'ok': False, 'error': resp.text}), 500
    requests.patch(
        f'{SUPABASE_URL}/rest/v1/user_access',
        headers={**_sb_headers(), 'Prefer': 'return=minimal'},
        params={'user_id': f'eq.{user_id}'},
        json={'reset_requested_at': None},
        timeout=10,
    )
    logger.info('[admin] senha resetada: %s', target['email'])
    return jsonify({'ok': True, 'password': password})


# ─── CNPJ ─────────────────────────────────────────────────────
# Consulta as bases públicas gratuitas em paralelo e devolve a primeira resposta
# válida. Feito no servidor para não depender de proxies CORS (instáveis).

def _cnpj_brasilapi(d: dict) -> dict:
    tel = f"({d['ddd_telefone_1'][:2]}) {d['ddd_telefone_1'][2:]}" if d.get('ddd_telefone_1') else ''
    return {
        'razao_social': d.get('razao_social') or '', 'nome_fantasia': d.get('nome_fantasia') or '',
        'situacao': d.get('descricao_situacao_cadastral') or '',
        'data_inicio_atividade': d.get('data_inicio_atividade') or '',
        'municipio': d.get('municipio') or '', 'uf': d.get('uf') or '', 'telefone': tel,
        'cnae': d.get('cnae_fiscal_descricao') or '', 'cnae_code': str(d.get('cnae_fiscal') or ''),
        'porte': d.get('porte') or '',
        'natureza': (d.get('natureza_juridica') or '').split(' - ')[0],
        'is_mei': d.get('opcao_pelo_mei') is True,
    }


def _cnpj_receitaws(d: dict) -> Optional[dict]:
    if not d.get('nome') or d.get('status') == 'ERROR':
        return None
    ativ = (d.get('atividade_principal') or [{}])[0]
    abertura = d.get('abertura') or ''
    nat = d.get('natureza_juridica') or ''
    return {
        'razao_social': d.get('nome') or '', 'nome_fantasia': d.get('fantasia') or '',
        'situacao': d.get('situacao') or '',
        'data_inicio_atividade': '-'.join(reversed(abertura.split('/'))) if abertura else '',
        'municipio': d.get('municipio') or '', 'uf': d.get('uf') or '', 'telefone': d.get('telefone') or '',
        'cnae': ativ.get('text') or '', 'cnae_code': ''.join(ch for ch in (ativ.get('code') or '') if ch.isdigit()),
        'porte': d.get('porte') or '', 'natureza': nat,
        'is_mei': ((d.get('simei') or {}).get('optante') is True) or 'microempreendedor' in nat.lower(),
    }


def _cnpj_cnpja(d: dict) -> Optional[dict]:
    comp = d.get('company') or {}
    if not comp.get('name'):
        return None
    addr = d.get('address') or {}
    phones = d.get('phones') or []
    tel = f"({phones[0].get('area', '')}) {phones[0].get('number', '')}" if phones else ''
    ativ = d.get('mainActivity') or {}
    return {
        'razao_social': comp.get('name') or '', 'nome_fantasia': d.get('alias') or '',
        'situacao': (d.get('status') or {}).get('text') or '',
        'data_inicio_atividade': d.get('founded') or '',
        'municipio': addr.get('city') or '', 'uf': addr.get('state') or '', 'telefone': tel,
        'cnae': ativ.get('text') or '', 'cnae_code': str(ativ.get('id') or ''),
        'porte': (comp.get('size') or {}).get('text') or '',
        'natureza': (comp.get('nature') or {}).get('text') or '',
        'is_mei': (comp.get('simei') or {}).get('optant') is True,
    }


_CNPJ_SOURCES = [
    ('brasilapi', 'https://brasilapi.com.br/api/cnpj/v1/{}', _cnpj_brasilapi),
    ('receitaws', 'https://receitaws.com.br/v1/cnpj/{}',     _cnpj_receitaws),
    ('cnpja',     'https://open.cnpja.com/office/{}',        _cnpj_cnpja),
]


def _cnpj_fetch(name: str, url: str, parse, cnpj: str):
    """Retorna (dados | None, 'not_found' | 'erro')."""
    try:
        resp = requests.get(url.format(cnpj), timeout=8,
                            headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        if resp.status_code in (400, 404):
            return None, 'not_found'
        if not resp.ok:
            logger.warning('[cnpj] %s HTTP %d', name, resp.status_code)
            return None, 'erro'
        data = parse(resp.json())
        if data and data['razao_social']:
            return data, None
        return None, 'not_found'
    except Exception as exc:
        logger.warning('[cnpj] %s falhou: %s', name, exc)
        return None, 'erro'


@app.route('/api/cnpj')
def api_cnpj():
    err = _require_user()
    if err:
        return err
    cnpj = ''.join(ch for ch in request.args.get('cnpj', '') if ch.isdigit())
    if len(cnpj) != 14:
        return jsonify({'ok': False, 'error': 'CNPJ precisa ter 14 dígitos'}), 400

    from concurrent.futures import ThreadPoolExecutor, as_completed
    pool = ThreadPoolExecutor(max_workers=len(_CNPJ_SOURCES))
    futures = {pool.submit(_cnpj_fetch, n, u, p, cnpj): n for n, u, p in _CNPJ_SOURCES}
    motivos = []
    try:
        for fut in as_completed(futures, timeout=10):
            data, motivo = fut.result()
            if data:
                logger.info('[cnpj] %s respondido por %s', cnpj, futures[fut])
                return jsonify({'ok': True, 'source': futures[fut], 'data': data})
            motivos.append(motivo)
    except Exception:
        pass  # timeout geral — trata abaixo
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # não espera as fontes lentas

    if motivos and all(m == 'not_found' for m in motivos) and len(motivos) == len(_CNPJ_SOURCES):
        return jsonify({'ok': False, 'error': 'CNPJ não encontrado. Verifique o número.'}), 404
    return jsonify({'ok': False, 'error': 'Serviços de CNPJ indisponíveis no momento. Tente novamente em instantes.'}), 502


# ─── LOJAS NOVAS (base da Receita) ────────────────────────────
# Tabela lojas_receita, preenchida 2x por mês por scripts/atualizar_receita.py.
# Só consulta o nosso banco — nenhuma chamada ao Google.

_RF_COLS = ('cnpj,razao_social,nome_fantasia,data_abertura,cnae,logradouro,numero,'
            'complemento,bairro,cep,municipio,uf,telefone,referencia')
_RF_PAGE = 30
_RF_MAX_ITENS = 300
_CEP_RE = re.compile(r'\b(\d{5})-?(\d{3})\b')
_NUM_RE = re.compile(r'^[^,]*,\s*(\d{1,6})\b')
# Palavras que não identificam a loja (todas são de pneus) — ficam fora da comparação de nomes
_RF_STOP = frozenset({
    'LTDA', 'ME', 'EPP', 'EIRELI', 'SA', 'S/A', 'SLU', 'DE', 'DA', 'DO', 'DAS', 'DOS', 'E', 'EM',
    'COMERCIO', 'COM', 'PNEUS', 'PNEU', 'PNEUMATICOS', 'LOJA', 'DISTRIBUIDORA', 'ATACADO', 'VAREJO',
    'AUTO', 'CENTER', 'TRUCK', 'CAR', 'CENTRO', 'SERVICOS', 'ACESSORIOS', 'PECAS', 'RODAS',
})


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    return ' '.join(''.join(ch for ch in s if not unicodedata.combining(ch)).upper().split())


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r'[^A-Z0-9]+', _norm(s)) if len(t) >= 3 and t not in _RF_STOP}


def _sim_nome(nome_google: str, row: dict) -> float:
    a = _tokens(nome_google)
    melhor = 0.0
    for nome_rf in (row.get('nome_fantasia'), row.get('razao_social')):
        b = _tokens(nome_rf or '')
        if a and b:
            melhor = max(melhor, len(a & b) / min(len(a), len(b)))
    return melhor


def _rf_erro(resp):
    if resp.status_code == 404 or 'PGRST205' in resp.text:
        return jsonify({'ok': False, 'error': 'A base da Receita ainda não foi carregada.'}), 503
    logger.error('[receita] Supabase HTTP %d', resp.status_code)
    return jsonify({'ok': False, 'error': 'Erro ao consultar a base da Receita. Tente novamente.'}), 502


@app.route('/api/receita-lojas')
def api_receita_lojas():
    """Lista paginada das lojas novas da Receita, com filtros de local e de ano/mês de abertura."""
    err = _require_user()
    if err:
        return err
    uf = request.args.get('uf', '').strip().upper()
    if uf and uf not in _CAPITAIS:
        return jsonify({'ok': False, 'error': 'Estado inválido'}), 400
    cidade = re.sub(r"[^A-Z '\-]", '', _norm(request.args.get('cidade', '')))[:60].strip()
    try:
        ano  = int(request.args.get('ano') or 0)
        mes  = int(request.args.get('mes') or 0)
        page = max(0, min(int(request.args.get('page') or 0), 1000))
    except ValueError:
        return jsonify({'ok': False, 'error': 'Filtro inválido'}), 400
    if (ano and not 2000 <= ano <= 2100) or not 0 <= mes <= 12:
        return jsonify({'ok': False, 'error': 'Ano ou mês inválido'}), 400
    # CNPJs que já aparecem em cards do Google ou no CRM — não repetir aqui
    excluir = [c for c in request.args.get('excluir', '').split(',') if len(c) == 14 and c.isdigit()][:_RF_MAX_ITENS]

    params = {'select': _RF_COLS, 'order': 'data_abertura.desc,cnpj',
              'limit': _RF_PAGE, 'offset': page * _RF_PAGE}
    if uf:
        params['uf'] = f'eq.{uf}'
    if cidade:
        params['municipio'] = f'eq.{cidade}'
    if ano:
        params['ano'] = f'eq.{ano}'
    if mes:
        params['mes'] = f'eq.{mes}'
    if excluir:
        params['cnpj'] = f'not.in.({",".join(excluir)})'
    try:
        resp = requests.get(f'{SUPABASE_URL}/rest/v1/lojas_receita', params=params,
                            headers={**_sb_headers(), 'Prefer': 'count=exact'}, timeout=10)
    except requests.RequestException as exc:
        logger.error('[receita] lista: %s', exc)
        return jsonify({'ok': False, 'error': 'Erro ao consultar a base da Receita. Tente novamente.'}), 502
    if not resp.ok:
        return _rf_erro(resp)
    rows = resp.json()
    total = resp.headers.get('Content-Range', '*/0').split('/')[-1]
    return jsonify({'ok': True, 'rows': rows, 'total': int(total) if total.isdigit() else len(rows),
                    'page_size': _RF_PAGE})


@app.route('/api/receita-match', methods=['POST'])
def api_receita_match():
    """Cruza os cards do Google com a base da Receita: mesmo CEP e (mesmo número ou nome parecido).
    Na dúvida (dois candidatos empatados) não marca nada."""
    err = _require_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    uf = str(data.get('uf') or '').strip().upper()
    itens = data.get('itens') if isinstance(data.get('itens'), list) else []
    itens = [i for i in itens[:_RF_MAX_ITENS] if isinstance(i, dict)]

    por_cep: dict[str, list[dict]] = {}
    for it in itens:
        m = _CEP_RE.search(str(it.get('endereco') or '')[:300])
        if m:
            por_cep.setdefault(m.group(1) + m.group(2), []).append(it)
    if not por_cep:
        return jsonify({'ok': True, 'matches': {}})

    ceps = list(por_cep)
    candidatos: dict[str, list[dict]] = {}
    try:
        for i in range(0, len(ceps), 100):
            params = {'select': 'cnpj,razao_social,nome_fantasia,data_abertura,numero,cep,telefone',
                      'cep': f'in.({",".join(ceps[i:i + 100])})'}
            if uf in _CAPITAIS:
                params['uf'] = f'eq.{uf}'
            resp = requests.get(f'{SUPABASE_URL}/rest/v1/lojas_receita', params=params,
                                headers=_sb_headers(), timeout=10)
            if not resp.ok:
                return _rf_erro(resp)
            for row in resp.json():
                candidatos.setdefault(row['cep'], []).append(row)
    except requests.RequestException as exc:
        logger.error('[receita] cruzamento: %s', exc)
        return jsonify({'ok': False, 'error': 'Erro ao consultar a base da Receita. Tente novamente.'}), 502

    escolhas: dict[str, tuple[float, str, dict]] = {}  # cnpj -> (pontos, place_id, linha)
    for cep, lista in por_cep.items():
        for it in lista:
            pid = str(it.get('id') or '')[:200]
            endereco = str(it.get('endereco') or '')[:300]
            m = _NUM_RE.search(endereco)
            num_g = m.group(1).lstrip('0') if m else ''
            pontos = []
            for row in candidatos.get(cep, []):
                num_rf = re.sub(r'\D', '', row.get('numero') or '').lstrip('0')
                mesmo_num = bool(num_g) and num_g == num_rf
                sim = _sim_nome(str(it.get('nome') or '')[:200], row)
                if mesmo_num or sim >= 0.5:
                    pontos.append((int(mesmo_num) + sim, row))
            if not pid or not pontos:
                continue
            pontos.sort(key=lambda p: p[0], reverse=True)
            if len(pontos) > 1 and pontos[0][0] == pontos[1][0]:
                continue  # empate: não dá para saber qual é
            nota, row = pontos[0]
            atual = escolhas.get(row['cnpj'])
            if not atual or nota > atual[0]:
                escolhas[row['cnpj']] = (nota, pid, row)

    matches = {}
    for nota, pid, row in escolhas.values():
        if pid not in matches or nota > matches[pid][0]:
            matches[pid] = (nota, row)
    return jsonify({'ok': True, 'matches': {
        pid: {k: row.get(k) for k in ('cnpj', 'razao_social', 'nome_fantasia', 'data_abertura', 'telefone')}
        for pid, (nota, row) in matches.items()
    }})


@app.route('/api/buscar')
def api_buscar():
    err = _require_user()
    if err:
        return err
    uf          = request.args.get('uf',          '').strip().upper()
    query       = request.args.get('query',       '').strip()
    cidade      = request.args.get('cidade',      '').strip()
    try:  # limite fixo no servidor: cada cidade a mais é chamada paga ao Google
        max_cidades = max(1, min(int(request.args.get('max_cidades', _MAX_CITIES)), _MAX_CITIES))
    except ValueError:
        max_cidades = _MAX_CITIES

    if not uf:
        return jsonify({'error': 'Parâmetro uf obrigatório'}), 400
    if not query:
        return jsonify({'error': 'Parâmetro query obrigatório'}), 400
    if not GOOGLE_API_KEY:
        return jsonify({'error': 'GOOGLE_API_KEY não configurada no servidor'}), 500

    return jsonify(buscar_empresas(uf, cidade, query, GOOGLE_API_KEY, max_cidades=max_cidades))


@app.route('/api/details')
def api_details():
    err = _require_user()
    if err:
        return err
    place_id = request.args.get('place_id', '').strip()
    if not place_id:
        return jsonify({'error': 'place_id obrigatório'}), 400
    if not GOOGLE_API_KEY:
        return jsonify({'error': 'GOOGLE_API_KEY não configurada'}), 500
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/place/details/json',
            params={
                'place_id': place_id,
                'fields':   'place_id,name,formatted_address,formatted_phone_number,rating,geometry,types,website,url',
                'key':      GOOGLE_API_KEY,
                'language': 'pt-BR',
            },
            timeout=12,
        )
        return jsonify(resp.json())
    except Exception as exc:
        logger.error('[details] %s', exc)
        return jsonify({'error': 'Erro ao consultar detalhes'}), 500


@app.route('/api/index.py', methods=['GET', 'POST'])
def api_dispatch():
    """No Vercel o rewrite de vercel.json entrega o caminho original apenas
    via query string (?path=buscar), não como PATH_INFO real — sem isso o
    Flask cai na rota estática abaixo e serve o .py bruto em vez de executar."""
    action = request.args.get('path', '')
    if action == 'buscar':
        return api_buscar()
    if action == 'details':
        return api_details()
    if action == 'register':
        return api_register()
    if action == 'cnpj':
        return api_cnpj()
    if action == 'receita-lojas':
        return api_receita_lojas()
    if action == 'receita-match':
        return api_receita_match()
    if action == 'reset-request':
        return api_reset_request()
    if action == 'admin-users':
        return api_admin_users()
    if action == 'admin-decide':
        return api_admin_decide()
    if action == 'admin-reset':
        return api_admin_reset()
    return jsonify({'error': 'ação desconhecida'}), 404


# Rotas estáticas — usadas apenas no servidor local (no Vercel o frontend é servido diretamente).
# Whitelist: só o que o navegador precisa. Nunca servir .env, .py, .sql etc.
_STATIC_DIRS = ('css/', 'js/')
_STATIC_EXT  = ('.css', '.js', '.png', '.jpg', '.svg', '.ico', '.webp', '.woff', '.woff2')


@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    if path == 'index.html' or (path.startswith(_STATIC_DIRS) and path.lower().endswith(_STATIC_EXT)):
        return send_from_directory(FRONTEND_DIR, path)
    abort(404)


if __name__ == '__main__':
    port   = int(os.getenv('PORT', 3000))
    key_ok = bool(GOOGLE_API_KEY)
    print(f'\n✅  AutoLead Brasil rodando em http://localhost:{port}')
    print(f'🔑  Google API Key: {"configurada" if key_ok else "NÃO CONFIGURADA — crie o arquivo .env com GOOGLE_API_KEY"}')
    print('Pressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
