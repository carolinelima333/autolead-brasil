from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# ── Proxy para Google Places API ──────────────────────────────
@app.route('/google')
def google_proxy():
    target_url = request.args.get('url')
    if not target_url or 'googleapis.com' not in target_url:
        return jsonify({'error': 'URL inválida'}), 400
    try:
        resp = requests.get(target_url, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Serve o index.html ────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    print(f'\n✅ AutoLead Brasil rodando!')
    print(f'👉 Acesse: http://localhost:{port}')
    print(f'\nPressione Ctrl+C para parar.\n')
    app.run(host='0.0.0.0', port=port, debug=False)
