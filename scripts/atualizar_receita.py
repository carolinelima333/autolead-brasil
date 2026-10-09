"""Atualiza a tabela lojas_receita com as lojas de pneus abertas nos últimos 3 anos.

Fonte: dados abertos do CNPJ da Receita Federal (publicados uma vez por mês).
Roda sozinho pelo GitHub Actions (.github/workflows/atualizar-receita.yml) ou à mão:

    python scripts/atualizar_receita.py                # baixa, filtra e atualiza o Supabase
    python scripts/atualizar_receita.py --teste x.csv  # só baixa e filtra, grava num CSV local

Precisa de SUPABASE_URL e SUPABASE_SERVICE_KEY (no .env ou nos Secrets do GitHub).
A lista é substituída inteira a cada execução, e só depois que tudo deu certo.
O repositório é público: o log mostra apenas contagens, nunca dados das lojas.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import tempfile
import time
import unicodedata
import zipfile
from datetime import date, datetime, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Link público dos dados abertos do CNPJ (divulgado em gov.br/receitafederal).
# O servidor é um Nextcloud: os arquivos são lidos via WebDAV usando o código do link.
RF_LINK_PUBLICO = os.getenv('RF_LINK_PUBLICO', 'https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9')
RF_WEBDAV = 'https://arquivos.receitafederal.gov.br/public.php/webdav/'
RF_SHARE = (RF_LINK_PUBLICO.rstrip('/').rsplit('/', 1)[-1], '')

# 4530-7/02 atacado e 4530-7/05 varejo de pneumáticos e câmaras de ar (autopeças fica de fora)
CNAES = {'4530702', '4530705'}
ATIVA = '02'
# Mesmas exclusões da validação de lead do sistema
NOMES_BLOQUEADOS = ('BORRACHARIA', 'BORRACHAS', 'BORRACHEIRO', 'REFORMA DE PNEU',
                    'CONSERTO DE PNEU', 'RECAPAGEM', 'RECAUCHUTAGEM')

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://nbigfrdezkozzwqozvlp.supabase.co').strip().rstrip('/')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '').strip()
TABELA = 'lojas_receita'
LOTE = 500


def log(msg: str) -> None:
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)


def sem_acento(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    return ' '.join(''.join(ch for ch in s if not unicodedata.combining(ch)).upper().split())


# ─── Download ─────────────────────────────────────────────────

def mes_mais_recente() -> str:
    resp = requests.request('PROPFIND', RF_WEBDAV, auth=RF_SHARE, headers={'Depth': '1'}, timeout=60)
    resp.raise_for_status()
    meses = sorted(set(re.findall(r'/webdav/(\d{4}-\d{2})/', resp.text)))
    if not meses:
        raise RuntimeError('Nenhuma pasta mensal encontrada no servidor da Receita')
    return meses[-1]


def baixar(mes: str, nome: str, pasta: str) -> str:
    """Baixa para o disco (o zip precisa de acesso aleatório). Retoma de onde parou se cair."""
    url, destino = f'{RF_WEBDAV}{mes}/{nome}', os.path.join(pasta, nome)
    for tentativa in range(1, 6):
        feito = os.path.getsize(destino) if os.path.exists(destino) else 0
        headers = {'Range': f'bytes={feito}-'} if feito else {}
        try:
            with requests.get(url, auth=RF_SHARE, headers=headers, stream=True, timeout=120) as resp:
                if resp.status_code == 416:  # já estava completo
                    return destino
                resp.raise_for_status()
                modo = 'ab' if feito and resp.status_code == 206 else 'wb'
                with open(destino, modo) as f:
                    for bloco in resp.iter_content(chunk_size=1 << 20):
                        f.write(bloco)
            zipfile.ZipFile(destino).close()  # confere se o arquivo está inteiro
            return destino
        except (requests.RequestException, zipfile.BadZipFile) as exc:
            log(f'  {nome}: tentativa {tentativa} falhou ({type(exc).__name__}) — tentando de novo')
            time.sleep(15 * tentativa)
    raise RuntimeError(f'Não foi possível baixar {nome}')


def linhas(caminho: str):
    """Linhas (bytes) do CSV dentro do zip, sem descompactar no disco."""
    with zipfile.ZipFile(caminho) as z:
        for membro in z.namelist():
            with z.open(membro) as f:
                yield from f


def campos(linha: bytes) -> list[str]:
    return next(csv.reader(io.StringIO(linha.decode('latin-1')), delimiter=';'))


# ─── Filtragem ────────────────────────────────────────────────

def ler_estabelecimentos(mes: str, pasta: str, ano_min: int) -> dict[str, list[str]]:
    achados: dict[str, list[str]] = {}
    marcas = tuple(f'"{c}"'.encode() for c in CNAES)
    for i in range(10):
        nome = f'Estabelecimentos{i}.zip'
        caminho = baixar(mes, nome, pasta)
        antes = len(achados)
        for linha in linhas(caminho):
            if not any(m in linha for m in marcas):  # pré-filtro rápido antes do parse
                continue
            f = campos(linha)
            if len(f) < 28 or f[11] not in CNAES or f[5] != ATIVA or f[10][:4] < str(ano_min):
                continue
            achados[f[0] + f[1] + f[2]] = f
        os.remove(caminho)
        log(f'{nome}: +{len(achados) - antes} loja(s)')
    return achados


def ler_por_basico(mes: str, pasta: str, nome: str, basicos: set[bytes], coluna: int) -> dict[bytes, str]:
    caminho = baixar(mes, nome, pasta)
    out = {}
    for linha in linhas(caminho):
        b = linha[1:9]
        if b in basicos:
            out[b] = campos(linha)[coluna]
    os.remove(caminho)
    return out


def montar(mes: str, pasta: str, ano_min: int) -> list[dict]:
    est = ler_estabelecimentos(mes, pasta, ano_min)
    basicos = {cnpj[:8].encode() for cnpj in est}

    razao: dict[bytes, str] = {}
    for i in range(10):
        razao.update(ler_por_basico(mes, pasta, f'Empresas{i}.zip', basicos, 1))
    log(f'Empresas: {len(razao)} razão(ões) social(is) encontrada(s)')
    mei = ler_por_basico(mes, pasta, 'Simples.zip', basicos, 4)
    caminho = baixar(mes, 'Municipios.zip', pasta)
    municipios = dict(campos(l)[:2] for l in linhas(caminho))
    os.remove(caminho)

    agora = datetime.now(timezone.utc).isoformat()
    rows, sem_mei, sem_nome = [], 0, 0
    for cnpj, f in est.items():
        b = cnpj[:8].encode()
        if mei.get(b) == 'S':
            sem_mei += 1
            continue
        rz, fant = sem_acento(razao.get(b, '')), sem_acento(f[4])
        if any(w in rz or w in fant for w in NOMES_BLOQUEADOS):
            sem_nome += 1
            continue
        d = f[10]
        ddd, tel = f[21].strip(), f[22].strip()
        rows.append({
            'cnpj': cnpj,
            'razao_social': rz or fant or cnpj,
            'nome_fantasia': fant or None,
            'data_abertura': f'{d[:4]}-{d[4:6]}-{d[6:8]}',
            'ano': int(d[:4]), 'mes': int(d[4:6]),
            'cnae': f[11],
            'logradouro': sem_acento(f'{f[13]} {f[14]}') or None,
            'numero': f[15].strip() or None,
            'complemento': sem_acento(f[16]) or None,
            'bairro': sem_acento(f[17]) or None,
            'cep': f[18].strip() or None,
            'municipio': sem_acento(municipios.get(f[20], '')),
            'uf': f[19].strip(),
            'telefone': f'({ddd}) {tel}' if ddd and tel else (tel or None),
            'referencia': mes,
            'atualizado_em': agora,
        })
    log(f'Excluídas: {sem_mei} MEI, {sem_nome} borracharia/recapagem')
    return rows


# ─── Supabase ─────────────────────────────────────────────────

def sb_headers(**extra) -> dict:
    h = {'apikey': SUPABASE_KEY, 'Content-Type': 'application/json', **extra}
    if SUPABASE_KEY.startswith('eyJ'):
        h['Authorization'] = f'Bearer {SUPABASE_KEY}'
    return h


def total_atual() -> int:
    resp = requests.get(f'{SUPABASE_URL}/rest/v1/{TABELA}', params={'select': 'cnpj', 'limit': 1},
                        headers=sb_headers(Prefer='count=exact'), timeout=30)
    resp.raise_for_status()
    return int(resp.headers.get('Content-Range', '*/0').split('/')[-1] or 0)


def enviar(rows: list[dict], mes: str, forcar: bool) -> None:
    atual = total_atual()
    # Proteção: base corrompida ou incompleta não pode apagar a lista boa que já está no ar
    if not forcar and atual and len(rows) < atual * 0.5:
        raise RuntimeError(f'Nova lista tem {len(rows)} lojas, menos da metade das {atual} atuais — '
                           'nada foi alterado. Confira e rode com --forcar se estiver certo.')
    for i in range(0, len(rows), LOTE):
        resp = requests.post(f'{SUPABASE_URL}/rest/v1/{TABELA}', params={'on_conflict': 'cnpj'},
                             json=rows[i:i + LOTE], timeout=60,
                             headers=sb_headers(Prefer='resolution=merge-duplicates,return=minimal'))
        if not resp.ok:
            raise RuntimeError(f'Supabase recusou o lote {i // LOTE + 1} (HTTP {resp.status_code})')
    # Só agora remove o que não está mais na base (fechou, mudou de atividade ou saiu da janela de 3 anos)
    resp = requests.delete(f'{SUPABASE_URL}/rest/v1/{TABELA}', params={'referencia': f'neq.{mes}'},
                           headers=sb_headers(Prefer='return=minimal'), timeout=60)
    if not resp.ok:
        raise RuntimeError(f'Falha ao remover lojas antigas (HTTP {resp.status_code})')
    log(f'Supabase: {len(rows)} loja(s) gravada(s); antes havia {atual}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--teste', metavar='ARQUIVO.csv', help='não grava no Supabase; salva o resultado neste CSV')
    ap.add_argument('--mes', help='pasta da Receita (AAAA-MM); padrão: a mais recente')
    ap.add_argument('--forcar', action='store_true', help='grava mesmo se a lista nova for bem menor')
    ap.add_argument('--de-csv', metavar='ARQUIVO.csv', help='grava no Supabase um CSV gerado antes com --teste')
    args = ap.parse_args()

    if not args.teste and not SUPABASE_KEY:
        log('SUPABASE_SERVICE_KEY não configurada (use o .env ou os Secrets do GitHub).')
        return 1

    if args.de_csv:
        with open(args.de_csv, encoding='utf-8-sig', newline='') as f:
            rows = [{k: (int(v) if k in ('ano', 'mes') else v or None) for k, v in r.items()}
                    for r in csv.DictReader(f, delimiter=';')]
        if not rows:
            log('CSV vazio — nada foi alterado.')
            return 1
        log(f'CSV: {len(rows)} loja(s) da base {rows[0]["referencia"]}')
        enviar(rows, rows[0]['referencia'], args.forcar)
        return 0

    mes = args.mes or mes_mais_recente()
    ano_min = date.today().year - 2
    log(f'Base da Receita: {mes} — lojas de pneus ativas abertas desde {ano_min}')
    with tempfile.TemporaryDirectory() as pasta:
        rows = montar(mes, pasta, ano_min)
    log(f'Total: {len(rows)} loja(s)')
    if not rows:
        log('Nenhuma loja encontrada — nada foi alterado.')
        return 1

    if args.teste:
        with open(args.teste, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=';')
            w.writeheader()
            w.writerows(rows)
        log(f'Modo teste: resultado salvo em {args.teste}')
    else:
        enviar(rows, mes, args.forcar)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        log(f'ERRO: {type(exc).__name__}: {exc}')
        sys.exit(1)
