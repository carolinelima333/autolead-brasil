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
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend')
CORS(app)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# ─── CONSTANTES DE BUSCA ──────────────────────────────────────
# Termos de vendedores (lojas/distribuidoras de pneus)
SEARCH_TERMS = [
    'distribuidora de pneus',
    'atacadista de pneus',
    'loja de pneus',
    'revenda de pneus',
    'pneus truck center',
]
# Termos de compradores (frotas/transportadoras)
SEARCH_TERMS_COMPRADORES = [
    'transportadora cargas',
    'empresa transporte rodoviario',
    'logistica transporte cargas',
]

# Palavras no nome da empresa que indicam borracharia/serviço → descartar
_BLOCK_WORDS = frozenset({
    'borracharia', 'borrachas', 'borracheiro',
    'reforma de pneu', 'conserto de pneu', 'recapagem',
})

_MAX_PAGES     = 2      # Google Places retorna até 20/página → máx 40 por query
_TOKEN_DELAY   = 2.0    # delay obrigatório entre páginas (next_page_token)
_MAX_CITIES    = 3      # cidades a varrer quando nenhuma cidade é informada (reduzido para Vercel)
_RETRY         = 2      # tentativas por requisição
_BACKOFF_BASE  = 1      # segundos base para backoff exponencial

# Capital de cada UF — usada como fallback quando BrasilAPI falha
_CAPITAIS: dict[str, str] = {
    'AC': 'Rio Branco',    'AL': 'Maceió',          'AM': 'Manaus',
    'AP': 'Macapá',        'BA': 'Salvador',         'CE': 'Fortaleza',
    'DF': 'Brasília',      'ES': 'Vitória',          'GO': 'Goiânia',
    'MA': 'São Luís',      'MG': 'Belo Horizonte',   'MS': 'Campo Grande',
    'MT': 'Cuiabá',        'PA': 'Belém',            'PB': 'João Pessoa',
    'PE': 'Recife',        'PI': 'Teresina',         'PR': 'Curitiba',
    'RJ': 'Rio de Janeiro','RN': 'Natal',            'RO': 'Porto Velho',
    'RR': 'Boa Vista',     'RS': 'Porto Alegre',     'SC': 'Florianópolis',
    'SE': 'Aracaju',       'SP': 'São Paulo',        'TO': 'Palmas',
}


# ══════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════

def _is_blocked_name(name: str) -> bool:
    """Retorna True se o nome da empresa indica borracharia/serviço de reparo."""
    n = name.lower()
    return any(w in n for w in _BLOCK_WORDS)


def _places_request(query: str, api_key: str,
                    page_token: Optional[str] = None) -> dict:
    """
    Uma requisição à Places Text Search API com retry + backoff exponencial.
    """
    params: dict = {
        'query': query,
        'key': api_key,
        'language': 'pt-BR',
        'region': 'BR',
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
            logger.warning(
                '[places] tentativa %d/%d falhou — %s — retry em %ds',
                attempt + 1, _RETRY, exc, wait,
            )
            if attempt < _RETRY - 1:
                time.sleep(wait)

    return {'status': 'NETWORK_ERROR', 'results': []}


def _paginate(query: str, api_key: str) -> tuple[list[dict], list[str]]:
    """
    Percorre até _MAX_PAGES páginas de resultados para uma query.

    Lógica de paginação:
      - Google Places retorna `next_page_token` quando há mais resultados.
      - É obrigatório aguardar ≥2 s antes de usar o token (API retorna
        INVALID_REQUEST caso contrário).
      - Até 3 páginas × 20 resultados = máx. 60 por query.
    """
    results: list[dict] = []
    errors:  list[str]  = []
    page_token: Optional[str] = None

    for page in range(_MAX_PAGES):
        if page > 0:
            time.sleep(_TOKEN_DELAY)

        data   = _places_request(query, api_key, page_token)
        status = data.get('status', 'UNKNOWN')

        if status == 'OK':
            batch = data.get('results', [])
            results.extend(batch)
            logger.info(
                '[paginate] p%d — %d resultado(s) — "%s"',
                page + 1, len(batch), query[:70],
            )
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
            logger.warning('[paginate] rate limit — aguardando 5 s')
            time.sleep(5)
            break

        else:
            errors.append(f'status={status}')
            logger.warning('[paginate] status inesperado: %s', status)
            break

    return results, errors


def _get_cidades(uf: str) -> list[str]:
    """
    Retorna lista de municípios do estado via BrasilAPI IBGE.

    Casos especiais:
      - DF: retorna ['Brasília'] diretamente (único município oficial).
    Normalização:
      - Nomes vêm em maiúsculas da API; aplicamos .title() para legibilidade
        e melhor compatibilidade com a query do Google Places.
    Em caso de falha retorna [] e o chamador aplica fallback por capital.
    """
    uf = uf.upper()
    if uf == 'DF':
        logger.info('[ibge] DF — retornando Brasília diretamente')
        return ['Brasília']

    try:
        resp = requests.get(
            f'https://brasilapi.com.br/api/ibge/municipios/v1/{uf}',
            timeout=10,
        )
        resp.raise_for_status()
        municipios = resp.json()
        cidades = [m['nome'].title() for m in municipios]
        logger.info('[ibge] %d municípios encontrados para %s', len(cidades), uf)
        return cidades
    except Exception as exc:
        logger.error('[ibge] erro ao buscar municípios de %s: %s', uf, exc)
        return []


def _format(raw: dict) -> dict:
    """Normaliza um resultado bruto do Places para o contrato de retorno."""
    return {
        'place_id':          raw.get('place_id', ''),
        'name':              raw.get('name', ''),
        'formatted_address': raw.get('formatted_address', ''),
        'rating':            raw.get('rating'),
        'opening_hours':     raw.get('opening_hours', {}),
        'phone':             '',   # disponível apenas via place/details
        'website':           '',   # disponível apenas via place/details
        'place_types':       raw.get('types', []),
    }


# ══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL DE BUSCA
# ══════════════════════════════════════════════════════════════

def buscar_empresas(
    estado_uf:  str,
    cidade:     str,
    query:      str,
    api_key:    str,
    max_cidades: int = _MAX_CITIES,
) -> dict:
    """
    Busca empresas via Google Places Text Search.

    Parâmetros
    ----------
    estado_uf   : sigla do estado (ex: 'GO')
    cidade      : nome da cidade ou string vazia para varrer o estado
    query       : termo de busca (ex: 'borracharia')
    api_key     : chave Google Places API
    max_cidades : máximo de cidades a varrer quando cidade não é informada

    Retorno
    -------
    {
        "total_unique": int,
        "results":      list[dict],  # place_id, name, address, rating, types, ...
        "errors":       list[str],
    }

    Deduplicação
    ------------
    Usa `place_id` como chave única. Quando o mesmo estabelecimento aparece
    em múltiplas cidades/páginas, mantém o registro com maior rating.
    Se os ratings forem iguais, mantém o primeiro encontrado.

    Paginação
    ---------
    Chama _paginate() por localidade, que internamente consome até 3 páginas
    via next_page_token (máx. 60 resultados por query/localidade).

    Divisão por cidades
    -------------------
    Quando `cidade` está vazio, obtém a lista de municípios via BrasilAPI
    e seleciona os primeiros `max_cidades`. Isso aumenta a cobertura ao
    custo de mais chamadas de API e tempo de resposta.
    """
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
            logger.info(
                '[buscar] modo estado — %d/%d cidade(s) de %s — query="%s"',
                len(sel), len(cidades), estado_uf, query,
            )
        else:
            # BrasilAPI falhou: usa a capital como ponto de busca
            capital = _CAPITAIS.get(estado_uf, '')
            if capital:
                locais = [f'{capital}, {estado_uf}, Brasil']
                logger.warning('[buscar] fallback capital — %s/%s', capital, estado_uf)
            else:
                locais = [f'{estado_uf}, Brasil']
                logger.warning('[buscar] fallback UF — BrasilAPI e capital indisponíveis para %s', estado_uf)

    for local in locais:
        full_query = f'{query} em {local}'
        raw, errs  = _paginate(full_query, api_key)
        errors.extend(errs)

        for r in raw:
            pid = r.get('place_id', '')
            if not pid:
                continue
            if pid not in seen:
                seen[pid] = r
            else:
                # Deduplicação: mantém o de maior rating
                cur = seen[pid].get('rating') or 0
                new = r.get('rating')       or 0
                if new > cur:
                    seen[pid] = r

    results = [
        _format(r) for r in seen.values()
        if not _is_blocked_name(r.get('name', ''))
    ]
    logger.info(
        '[buscar] concluído — %d único(s), %d erro(s) — query="%s"',
        len(results), len(errors), query,
    )
    return {
        'total_unique': len(results),
        'results':      results,
        'errors':       list(dict.fromkeys(errors)),  # deduplica preservando ordem
    }


# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.route('/api/buscar')
def api_buscar():
    """
    Endpoint de busca avançada com paginação e divisão por cidades.

    Parâmetros (query string)
    -------------------------
    uf          : sigla do estado          (obrigatório)
    query       : termo de busca           (obrigatório)
    cidade      : nome da cidade           (opcional)
    max_cidades : cidades a varrer s/ cidade (opcional, padrão=5)
    """
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

    result = buscar_empresas(uf, cidade, query, GOOGLE_API_KEY, max_cidades=max_cidades)
    return jsonify(result)


@app.route('/api/details')
def api_details():
    """Busca detalhes de um lugar pelo place_id (telefone, website, coordenadas)."""
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


@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('frontend', path)


if __name__ == '__main__':
    port    = int(os.getenv('PORT', 3000))
    key_ok  = bool(GOOGLE_API_KEY)
    print(f'\n✅ AutoLead Brasil rodando!')
    print(f'👉 Acesse: http://localhost:{port}')
    print(f'🔑 Google API Key: {"configurada" if key_ok else "NÃO CONFIGURADA — crie o arquivo .env com GOOGLE_API_KEY"}')
    print(f'\nPressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
