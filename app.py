from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder='frontend')
CORS(app)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')


@app.route('/api/search')
def api_search():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query obrigatória'}), 400
    if not GOOGLE_API_KEY:
        return jsonify({'error': 'GOOGLE_API_KEY não configurada no servidor. Adicione-a no arquivo .env'}), 500
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/place/textsearch/json',
            params={'query': query, 'key': GOOGLE_API_KEY, 'language': 'pt-BR', 'region': 'BR'},
            timeout=12
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
                'fields': 'place_id,name,formatted_address,formatted_phone_number,rating,geometry,types,website,url',
                'key': GOOGLE_API_KEY,
                'language': 'pt-BR'
            },
            timeout=12
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
    port = int(os.getenv('PORT', 3000))
    key_ok = bool(GOOGLE_API_KEY)
    print(f'\n✅ AutoLead Brasil rodando!')
    print(f'👉 Acesse: http://localhost:{port}')
    print(f'🔑 Google API Key: {"configurada" if key_ok else "NÃO CONFIGURADA — crie o arquivo .env com GOOGLE_API_KEY"}')
    print(f'\nPressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
