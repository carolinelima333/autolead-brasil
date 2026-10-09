"""Varredura de segurança e qualidade — roda antes de cada commit (.githooks/pre-commit).

Uso manual:  python scripts/security_check.py
Sai com código 1 se encontrar problema bloqueante.
"""
from __future__ import annotations

import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

erros: list[str] = []
avisos: list[str] = []

SECRET_RE = re.compile(r'AIza[0-9A-Za-z_-]{20,}|sb_secret_[A-Za-z0-9_-]{8,}|"role"\s*:\s*"service_role"')


def git(*args: str) -> str:
    try:
        return subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8').stdout
    except FileNotFoundError:
        return ''


def ler(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


# ─── 1. Segredos ──────────────────────────────────────────────
staged = [f for f in git('diff', '--cached', '--name-only').splitlines() if f]
if any(os.path.basename(f) == '.env' for f in staged):
    erros.append('.env está no commit — ele contém as chaves e nunca pode ir para o git.')

for f in git('ls-files').splitlines() + staged:
    if f.endswith(('.png', '.jpg', '.ico', '.docx', '.pdf')) or not os.path.isfile(f) or f == '.env':
        continue
    try:
        for n, linha in enumerate(ler(f).splitlines(), 1):
            if SECRET_RE.search(linha):
                erros.append(f'Chave secreta em {f}:{n} — mova para o .env / variáveis da Vercel.')
    except UnicodeDecodeError:
        pass

# ─── 2. Sintaxe ───────────────────────────────────────────────
try:
    py_compile.compile('api/index.py', doraise=True)
except py_compile.PyCompileError as exc:
    erros.append(f'Erro de sintaxe Python: {exc.msg}')

html = ler('index.html')
scripts = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', html, re.S)
if scripts and shutil.which('node'):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as tmp:
        tmp.write(max(scripts, key=len))
    r = subprocess.run(['node', '--check', tmp.name], capture_output=True, text=True)
    os.unlink(tmp.name)
    if r.returncode != 0:
        erros.append('Erro de sintaxe JavaScript no index.html:\n' + r.stderr.strip()[:500])
elif scripts:
    avisos.append('Node não encontrado — sintaxe do JavaScript não verificada.')

# ─── 3. Frontend: injeção de script (XSS) ─────────────────────
EXTERNOS = (r'nome|endereco|telefone|website|gmaps_url|company_name|notes|razao_social|nome_fantasia'
            r'|phone|cnae|municipio|email|name|situacao|natureza|porte|city|state|cidade|tipo')
OBJ = r'(co|c|s|d|h|u|x|it)'
# Valor impresso direto: ${co.nome} ou ${co.nome||'—'}  (condições como ${co.nome ? ...} não imprimem)
raw_interp = re.compile(r'\$\{\s*' + OBJ + r'\.(' + EXTERNOS + r')\s*(\|\|[^}?]*)?\}')
# Concatenação dentro de template: '...'+co.cidade
raw_concat = re.compile(r"\+\s*" + OBJ + r"\.(" + EXTERNOS + r")\b")
for n, linha in enumerate(html.splitlines(), 1):
    if re.search(r"window\.open\('\$\{", linha):
        erros.append(f'index.html:{n} — window.open com valor interpolado; use linkBtn()/safeUrl().')
    if '`' in linha or '${' in linha:
        for rx in (raw_interp, raw_concat):
            m = rx.search(linha)
            if m:
                erros.append(f'index.html:{n} — `{m.group(0).strip()}` vai para a tela sem escH()/escJs() (risco de XSS).')
                break
    if re.search(r'\beval\(|new Function\(', linha):
        erros.append(f'index.html:{n} — uso de eval/new Function.')

# ─── 4. Backend ───────────────────────────────────────────────
py = ler('api/index.py')
PUBLICAS = {'api_register', 'api_reset_request', 'api_dispatch', 'index', 'static_files'}
for m in re.finditer(r"@app\.route\([^)]*\)\s*\ndef (\w+)\(.*?\):\n(.*?)(?=\n@app\.route|\nif __name__|\Z)", py, re.S):
    nome, corpo = m.group(1), m.group(2)
    if nome not in PUBLICAS and '_require_user()' not in corpo and '_require_admin()' not in corpo:
        erros.append(f'api/index.py: rota {nome}() sem _require_user()/_require_admin() — '
                     'qualquer pessoa poderia chamá-la (e gastar a cota do Google).')
for n, linha in enumerate(py.splitlines(), 1):
    if re.search(r"jsonify\(.*str\((e|exc|err)\)", linha):
        erros.append(f'api/index.py:{n} — resposta expõe detalhe interno do erro (str(exc)).')
    if re.search(r'debug\s*=\s*True', linha):
        erros.append(f'api/index.py:{n} — debug=True não pode ir para produção.')
    if re.search(r'verify\s*=\s*False', linha):
        erros.append(f'api/index.py:{n} — verify=False desliga a checagem de certificado.')
if 'CORS(app' in py:
    avisos.append('CORS reativado no backend — confirme se é mesmo necessário.')

# ─── 5. Dependências vulneráveis (se pip-audit estiver instalado) ─
if shutil.which('pip-audit'):
    r = subprocess.run(['pip-audit', '-r', 'requirements.txt', '--progress-spinner', 'off'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        avisos.append('pip-audit encontrou dependências vulneráveis:\n' + (r.stdout or r.stderr).strip()[:800])

# ─── Resultado ────────────────────────────────────────────────
for a in avisos:
    print(f'⚠  {a}')
if erros:
    print('\n❌ Varredura de segurança/qualidade BLOQUEOU o commit:\n')
    for e in dict.fromkeys(erros):
        print(f'  • {e}')
    print('\nCorrija e tente de novo. (Emergência: git commit --no-verify)')
    sys.exit(1)
print('✅ Varredura de segurança/qualidade: nenhum problema bloqueante.')
