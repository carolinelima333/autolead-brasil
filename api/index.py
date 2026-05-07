from __future__ import annotations

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import logging
import time
import os
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

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

GOOGLE_API_KEY      = os.getenv('GOOGLE_API_KEY', '')
SUPABASE_URL        = os.getenv('SUPABASE_URL', 'https://nbigfrdezkozzwqozvlp.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')

_MAX_PAGES    = 2
_TOKEN_DELAY  = 2.0
_MAX_CITIES   = 3
_RETRY        = 2
_BACKOFF_BASE = 1

_BLOCK_WORDS = frozenset({
    'borracharia', 'borrachas', 'borracheiro',
    'reforma de pneu', 'conserto de pneu', 'recapagem',
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
            headers={
                'apikey':        SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                'Content-Type':  'application/json',
            },
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
        return jsonify({'ok': False, 'error': str(exc)}), 500


@app.route('/api/buscar')
def api_buscar():
    uf          = request.args.get('uf',          '').strip().upper()
    query       = request.args.get('query',       '').strip()
    cidade      = request.args.get('cidade',      '').strip()
    max_cidades = int(request.args.get('max_cidades', _MAX_CITIES))

    if not uf:
        return jsonify({'error': 'Parâmetro uf obrigatório'}), 400
    if not query:
        return jsonify({'error': 'Parâmetro query obrigatório'}), 400
    if not GOOGLE_API_KEY:
        return jsonify({'error': 'GOOGLE_API_KEY não configurada no servidor'}), 500

    return jsonify(buscar_empresas(uf, cidade, query, GOOGLE_API_KEY, max_cidades=max_cidades))


@app.route('/api/details')
def api_details():
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Rotas estáticas — usadas apenas no servidor local (no Vercel o frontend é servido diretamente)
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == '__main__':
    port   = int(os.getenv('PORT', 3000))
    key_ok = bool(GOOGLE_API_KEY)
    print(f'\n✅  AutoLead Brasil rodando em http://localhost:{port}')
    print(f'🔑  Google API Key: {"configurada" if key_ok else "NÃO CONFIGURADA — crie o arquivo .env com GOOGLE_API_KEY"}')
    print('Pressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
