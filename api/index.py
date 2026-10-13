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

# Raiz do projeto — index.html e css/ ficam aqui (local e Vercel)
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
SUPABASE_URL        = os.getenv('SUPABASE_URL', 'https://nbigfrdezkozzwqozvlp.supabase.co').strip().rstrip('/')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '').strip()
ADMIN_EMAIL         = os.getenv('ADMIN_EMAIL', 'carolinelima313@gmail.com').strip().lower()


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
    """Exige usuário logado e aprovado.
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
# Só consulta o nosso banco.

_RF_COLS = ('cnpj,razao_social,nome_fantasia,data_abertura,cnae,logradouro,numero,'
            'complemento,bairro,cep,municipio,uf,telefone,referencia')
_RF_PAGE = 30
_RF_PAGE_EXPORT = 1000  # exportação (aba Exportar): blocos maiores; 1000 é o máximo por consulta do Supabase
# Tipos da tabela: lojas de pneus (atacado/varejo) e frotistas (transporte rodoviário de carga)
_RF_TIPOS = {'lojas': 'in.(4530702,4530705)', 'frotistas': 'eq.4930202'}
_RF_MAX_ITENS = 300
_UFS = frozenset('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split())


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    return ' '.join(''.join(ch for ch in s if not unicodedata.combining(ch)).upper().split())


def _rf_erro(resp):
    if resp.status_code == 404 or 'PGRST205' in resp.text:
        return jsonify({'ok': False, 'error': 'A base da Receita ainda não foi carregada.'}), 503
    logger.error('[receita] Supabase HTTP %d', resp.status_code)
    return jsonify({'ok': False, 'error': 'Erro ao consultar a base da Receita. Tente novamente.'}), 502


@app.route('/api/receita-lojas')
def api_receita_lojas():
    """Lista paginada das empresas novas da Receita (lojas ou frotistas), com filtros de local e de ano/mês.
    Com exportar=1 as páginas têm 1000 linhas (a aba Exportar busca todas, uma a uma)."""
    err = _require_user()
    if err:
        return err
    uf = request.args.get('uf', '').strip().upper()
    if uf and uf not in _UFS:
        return jsonify({'ok': False, 'error': 'Estado inválido'}), 400
    tipo = request.args.get('tipo', 'lojas')
    if tipo not in _RF_TIPOS:
        return jsonify({'ok': False, 'error': 'Tipo inválido'}), 400
    cidade = re.sub(r"[^A-Z '\-]", '', _norm(request.args.get('cidade', '')))[:60].strip()
    try:
        ano  = int(request.args.get('ano') or 0)
        mes  = int(request.args.get('mes') or 0)
        page = max(0, min(int(request.args.get('page') or 0), 1000))
    except ValueError:
        return jsonify({'ok': False, 'error': 'Filtro inválido'}), 400
    if (ano and not 2000 <= ano <= 2100) or not 0 <= mes <= 12:
        return jsonify({'ok': False, 'error': 'Ano ou mês inválido'}), 400
    # CNPJs já registrados no CRM — não repetir aqui
    excluir = [c for c in request.args.get('excluir', '').split(',') if len(c) == 14 and c.isdigit()][:_RF_MAX_ITENS]

    tam = _RF_PAGE_EXPORT if request.args.get('exportar') == '1' else _RF_PAGE
    params = {'select': _RF_COLS, 'order': 'data_abertura.desc,cnpj',
              'limit': tam, 'offset': page * tam, 'cnae': _RF_TIPOS[tipo]}
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
                    'page_size': tam})


@app.route('/api/receita-info')
def api_receita_info():
    """Mês da base da Receita carregada e quando foi gravada — a tela avisa quando muda."""
    err = _require_user()
    if err:
        return err
    try:
        resp = requests.get(f'{SUPABASE_URL}/rest/v1/lojas_receita',
                            params={'select': 'referencia,atualizado_em',
                                    'order': 'referencia.desc,atualizado_em.desc', 'limit': 1},
                            headers=_sb_headers(), timeout=10)
    except requests.RequestException as exc:
        logger.error('[receita] info: %s', exc)
        return jsonify({'ok': False, 'error': 'Erro ao consultar a base da Receita. Tente novamente.'}), 502
    if not resp.ok:
        return _rf_erro(resp)
    rows = resp.json()
    return jsonify({'ok': True, 'referencia': rows[0]['referencia'] if rows else None,
                    'atualizado_em': rows[0]['atualizado_em'] if rows else None})


@app.route('/api/index.py', methods=['GET', 'POST'])
def api_dispatch():
    """No Vercel o rewrite de vercel.json entrega o caminho original apenas
    via query string (?path=cnpj), não como PATH_INFO real — sem isso o
    Flask cai na rota estática abaixo e serve o .py bruto em vez de executar."""
    action = request.args.get('path', '')
    if action == 'register':
        return api_register()
    if action == 'cnpj':
        return api_cnpj()
    if action == 'receita-lojas':
        return api_receita_lojas()
    if action == 'receita-info':
        return api_receita_info()
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
_STATIC_DIRS = ('css/',)
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
    port = int(os.getenv('PORT', 3000))
    print(f'\n✅  AutoLead Brasil rodando em http://localhost:{port}')
    print('Pressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
