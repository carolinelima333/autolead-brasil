// ─── CONFIG ──────────────────────────────────────────────────
const SUPA_URL = 'https://nbigfrdezkozzwqozvlp.supabase.co';
const SUPA_KEY = 'sb_publishable_uH_lieeSpbZHADvMAcDAwA_uqppix7p';
const SEARCH_TERMS = ['borracharia', 'loja de pneus', 'auto center', 'pneus'];
const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'];
const MAX_DAILY = 10;
const CACHE_TTL_DAYS = 7;

// ─── ESTADO ───────────────────────────────────────────────────
let sb = null;
let user = null, signup = false, ctab = 'b';
let cos = [], favs = new Set(), hist = [], filterType = 'todos';
let theme = localStorage.getItem('al_theme') || 'dark';
let currentStoreIdx = undefined;

// ─── HELPERS ──────────────────────────────────────────────────
const g = id => document.getElementById(id);
const setErr = m => { g('aerr').textContent = m; g('aerr').style.display = 'block'; };
const clrErr = () => g('aerr').style.display = 'none';

// ─── INIT ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  try { sb = window.supabase.createClient(SUPA_URL, SUPA_KEY); } catch(e) { console.warn('Supabase:', e); }
  applyTheme(theme);
});

// ─── TEMA ─────────────────────────────────────────────────────
function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('al_theme', theme);
  applyTheme(theme);
}
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  const icon = t === 'dark' ? '☀️' : '🌙';
  document.querySelectorAll('.btn-theme').forEach(b => b.textContent = icon);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = t === 'dark' ? '#0d0d0d' : '#f4f4f5';
}

// ─── DRAWER ───────────────────────────────────────────────────
function toggleDrawer() {
  const open = g('mob-drawer').classList.contains('open');
  g('mob-drawer').classList.toggle('open', !open);
  g('mob-overlay').classList.toggle('open', !open);
  g('hambtn').classList.toggle('open', !open);
}
function closeDrawer() {
  ['mob-drawer','mob-overlay','hambtn'].forEach(id => g(id).classList.remove('open'));
}

// ─── AUTH ─────────────────────────────────────────────────────
function tgAuth() {
  signup = !signup;
  g('atitle').textContent = signup ? 'Criar sua conta' : 'Bem-vindo de volta';
  g('adesc').textContent = signup ? 'Preencha os dados para começar gratuitamente.' : 'Entre na sua conta para acessar os leads.';
  g('abtn').textContent = signup ? 'Criar conta' : 'Entrar';
  g('tgbtn').textContent = signup ? 'Já tenho conta' : 'Criar conta grátis';
  g('ifw').style.display = signup ? 'block' : 'none';
  g('ip2w').style.display = signup ? 'block' : 'none';
  clrErr();
}
function doAuth() {
  const e = g('ie').value.trim(), p = g('ip').value;
  if (!e || !p) { setErr('Preencha e-mail e senha.'); return; }
  if (!e.includes('@')) { setErr('E-mail inválido.'); return; }
  if (signup) {
    const n = g('iname').value.trim(), p2 = g('ip2').value;
    if (!n) { setErr('Digite seu nome.'); return; }
    if (p !== p2) { setErr('Senhas não conferem.'); return; }
    if (p.length < 6) { setErr('Mínimo 6 caracteres.'); return; }
    user = { email: e, name: n };
  } else {
    user = { email: e, name: e.split('@')[0].replace(/[._-]/g,' ').replace(/\b\w/g, c => c.toUpperCase()) };
  }
  clrErr();
  g('sc-auth').style.display = 'none';
  g('sc-main').style.display = 'flex';
  const n = user.name;
  ['sav','mob-av','drawer-av'].forEach(id => { const el = g(id); if (el) el.textContent = n[0].toUpperCase(); });
  if (g('snm')) g('snm').textContent = n;
  if (g('semail')) g('semail').textContent = user.email;
  if (g('drawer-nm')) g('drawer-nm').textContent = n;
  if (g('drawer-em')) g('drawer-em').textContent = user.email;
  go('b');
}
function logout() {
  user = null; cos = []; favs = new Set(); hist = []; filterType = 'todos';
  g('sc-main').style.display = 'none';
  g('sc-auth').style.display = 'flex';
  g('ie').value = ''; g('ip').value = '';
  closeDrawer();
}

// ─── NAVEGAÇÃO ────────────────────────────────────────────────
const TABS = ['b','f','h','e','s'];
function go(t) {
  ctab = t;
  TABS.forEach(x => ['n','dn','bn'].forEach(p => { const el = g(p+x); if(el) el.classList.toggle('on', x===t); }));
  render();
}
function render() {
  const c = g('mc');
  if (ctab==='b') pBuscar(c);
  else if (ctab==='f') pFavs(c);
  else if (ctab==='h') pHist(c);
  else if (ctab==='e') pExp(c);
  else if (ctab==='s') pStores(c);
}

// ─── PÁGINA DE BUSCA ──────────────────────────────────────────
function pBuscar(c) {
  const opts = '<option value="">— Estado —</option>' + UFS.map(u => `<option value="${u}">${u}</option>`).join('');
  c.innerHTML = `
    <div class="page-header"><h1>Buscar Empresas</h1><p>Dados do Google Places — resultados salvos no banco para consulta rápida</p></div>
    <div class="stats-bar">
      <div class="stat"><div class="num">${cos.length}</div><div class="lbl">Empresas</div></div>
      <div class="stat"><div class="num">${favs.size}</div><div class="lbl">Favoritas</div></div>
      <div class="stat"><div class="num">${hist.length}</div><div class="lbl">Buscas</div></div>
      <div class="stat"><div class="num">${cos.filter(x=>x.abertura).length}</div><div class="lbl">c/ Abertura</div></div>
    </div>
    <div class="search-panel">
      <h3>🔍 Pesquise aqui</h3>
      <div class="srow">
        <select id="suf">${opts}</select>
        <input id="scid" placeholder="Cidade (opcional — vazio busca todo o estado)" autocomplete="off"/>
        <button class="bsc" id="bbs" onclick="buscar()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          Buscar agora
        </button>
      </div>
      <div class="type-pills">
        <span class="pill ${filterType==='todos'?'active':''}" onclick="setFilter('todos')">Todos</span>
        <span class="pill ${filterType==='pneus'?'active':''}" onclick="setFilter('pneus')">🔵 Pneus</span>
        <span class="pill ${filterType==='borr'?'active':''}" onclick="setFilter('borr')">🟡 Borracharias</span>
        <span class="pill ${filterType==='auto'?'active':''}" onclick="setFilter('auto')">⚙️ Auto Centers</span>
      </div>
    </div>
    <div class="cnpj-panel">
      <h3>📋 Consultar CNPJ — data de abertura</h3>
      <div class="cnpj-row">
        <input id="icnpj" placeholder="00.000.000/0001-00" maxlength="18" inputmode="numeric" oninput="maskCNPJ(this)" onkeydown="if(event.key==='Enter')qCNPJ()"/>
        <button class="bcnpj" id="bcnpjbtn" onclick="qCNPJ()">Consultar</button>
      </div>
      <div id="cres" class="cnpj-result"></div>
    </div>
    <div id="res"></div>`;
  if (cos.length > 0) exibir();
}
function setFilter(t) { filterType = t; pBuscar(g('mc')); }

// ─── SUPABASE: RATE LIMIT ─────────────────────────────────────
async function checkRateLimit(searchKey) {
  if (!sb || !user) return { ok: true, count: 0 };
  const today = new Date().toISOString().split('T')[0];
  try {
    const { data } = await sb.from('search_limits')
      .select('count').eq('user_email', user.email)
      .eq('search_key', searchKey).eq('search_date', today).maybeSingle();
    const count = data ? data.count : 0;
    return { ok: count < MAX_DAILY, count };
  } catch(e) { return { ok: true, count: 0 }; }
}
async function incrementRateLimit(searchKey) {
  if (!sb || !user) return;
  const today = new Date().toISOString().split('T')[0];
  try {
    const { data } = await sb.from('search_limits')
      .select('id,count').eq('user_email', user.email)
      .eq('search_key', searchKey).eq('search_date', today).maybeSingle();
    if (data) {
      await sb.from('search_limits').update({ count: data.count + 1 }).eq('id', data.id);
    } else {
      await sb.from('search_limits').insert({ user_email: user.email, search_key: searchKey, search_date: today, count: 1 });
    }
  } catch(e) { console.warn('Rate limit:', e); }
}

// ─── SUPABASE: CACHE ──────────────────────────────────────────
async function checkCache(searchKey) {
  if (!sb) return null;
  try {
    const { data } = await sb.from('searches')
      .select('results,updated_at').eq('search_key', searchKey).maybeSingle();
    if (!data || !data.results) return null;
    const ageDays = (Date.now() - new Date(data.updated_at).getTime()) / 86400000;
    return ageDays > CACHE_TTL_DAYS ? null : data.results;
  } catch(e) { return null; }
}
async function saveToCache(searchKey, uf, city, results) {
  if (!sb) return;
  try {
    await sb.from('searches').upsert(
      { search_key: searchKey, state: uf, city: city || null, results, updated_at: new Date().toISOString() },
      { onConflict: 'search_key' }
    );
  } catch(e) { console.warn('Cache save:', e); }
}

// ─── CHAMADAS AO BACKEND ──────────────────────────────────────
async function apiTextSearch(query) {
  const r = await fetch('/api/search?query=' + encodeURIComponent(query));
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || 'Erro no servidor (' + r.status + ')');
  }
  const d = await r.json();
  if (d.status === 'REQUEST_DENIED') throw new Error('API Key recusada: ' + (d.error_message || 'verifique a chave no .env do servidor'));
  if (d.status === 'ZERO_RESULTS') return [];
  if (d.status !== 'OK') throw new Error('Google Places: ' + d.status);
  return d.results || [];
}
async function apiDetails(placeId) {
  try {
    const r = await fetch('/api/details?place_id=' + encodeURIComponent(placeId));
    if (!r.ok) return null;
    const d = await r.json();
    if (d.status !== 'OK' || !d.result) return null;
    const p = d.result;
    return {
      id: p.place_id, nome: p.name || '', endereco: p.formatted_address || '',
      cidade: '', uf: '', telefone: p.formatted_phone_number || '',
      avaliacao: p.rating ? p.rating.toFixed(1) : '—',
      tipo: detectTipo(p.types || [], p.name || ''),
      lat: p.geometry?.location?.lat || null, lon: p.geometry?.location?.lng || null,
      abertura: null, gmaps_url: p.url || '', website: p.website || '',
    };
  } catch(e) { return null; }
}
function detectTipo(types, nome) {
  const n = (nome || '').toLowerCase();
  if (n.includes('pneu') || n.includes('tyre') || n.includes('tire')) return 'Loja de Pneus';
  if (n.includes('borracharia')) return 'Borracharia';
  if (n.includes('auto center') || n.includes('autocenter')) return 'Auto Center';
  if (types.includes('car_repair')) return 'Mecânica / Auto Center';
  return 'Auto Center';
}

// ─── BUSCAR ───────────────────────────────────────────────────
async function buscar() {
  const uf = g('suf').value;
  const cid = (g('scid').value || '').trim();
  if (!uf) { alert('Selecione o estado.'); return; }

  const searchKey = cid ? `${uf}_${cid.replace(/\s+/g,'_').toLowerCase()}` : uf;
  const local = cid ? `${cid}, ${uf}, Brasil` : `estado ${uf}, Brasil`;
  const displayLoc = cid ? `${cid}, ${uf}` : `${uf} (estado inteiro)`;

  const limit = await checkRateLimit(searchKey);
  if (!limit.ok) {
    g('res').innerHTML = `<div class="empty"><div class="ei">🚫</div><p style="color:var(--red);font-weight:700">Limite diário atingido</p><small>Você já realizou ${MAX_DAILY} pesquisas para <strong>${displayLoc}</strong> hoje.<br>Tente novamente amanhã ou pesquise outra localidade.</small></div>`;
    return;
  }

  g('bbs').disabled = true;
  g('res').innerHTML = `
    <div class="ld">
      <div class="spin"></div>
      <div style="color:var(--txt);font-weight:600;margin-bottom:.3rem">Buscando em ${displayLoc}...</div>
      <div style="font-size:12px;color:var(--txt3)">Consultando Google Places</div>
      <div class="prog-bar"><div class="prog-fill" id="prog" style="width:5%"></div></div>
      <div class="prog-text" id="progtxt">Verificando banco de dados...</div>
    </div>`;

  const setP = (pct, txt) => {
    const pf = g('prog'); if (pf) pf.style.width = pct + '%';
    const pt = g('progtxt'); if (pt) pt.textContent = txt;
  };

  try {
    setP(10, 'Verificando banco de dados...');
    const cached = await checkCache(searchKey);
    if (cached && cached.length > 0) {
      cos = cached;
      cos.forEach((c, i) => c._idx = i);
      hist.push({ uf, cidade: cid, data: new Date().toLocaleString('pt-BR'), qtd: cos.length, fromCache: true });
      setP(100, 'Carregado do banco!');
      setTimeout(() => exibir(), 350);
      g('bbs').disabled = false;
      return;
    }

    setP(20, 'Buscando no Google Places...');
    const allResults = [], seenIds = new Set();

    for (let i = 0; i < SEARCH_TERMS.length; i++) {
      const termo = SEARCH_TERMS[i];
      setP(20 + Math.round((i / SEARCH_TERMS.length) * 40), 'Buscando ' + termo + '...');
      try {
        const items = await apiTextSearch(termo + ' em ' + local);
        for (const p of items) {
          if (!seenIds.has(p.place_id)) { seenIds.add(p.place_id); allResults.push(p); }
        }
      } catch(e) {
        if (e.message.includes('recusada') || e.message.includes('DENIED')) throw e;
      }
    }

    if (allResults.length === 0) {
      cos = [];
      hist.push({ uf, cidade: cid, data: new Date().toLocaleString('pt-BR'), qtd: 0 });
      await incrementRateLimit(searchKey);
      g('res').innerHTML = `<div class="empty"><div class="ei">🔍</div><p>Nenhuma empresa encontrada em ${displayLoc}.</p><small>Tente outra cidade ou verifique se a Places API está ativada na chave do servidor.</small></div>`;
      g('bbs').disabled = false;
      return;
    }

    const slice = allResults.slice(0, 30);
    const resultados = [];
    for (let i = 0; i < slice.length; i += 5) {
      setP(65 + Math.round((i / slice.length) * 30), `Detalhes (${Math.min(i+5,slice.length)}/${slice.length})...`);
      const lote = await Promise.allSettled(slice.slice(i, i+5).map(p => apiDetails(p.place_id)));
      lote.forEach(r => { if (r.status === 'fulfilled' && r.value) resultados.push(r.value); });
    }

    setP(97, 'Salvando no banco...');
    cos = resultados;
    cos.forEach((c, i) => c._idx = i);
    await incrementRateLimit(searchKey);
    await saveToCache(searchKey, uf, cid, resultados);
    hist.push({ uf, cidade: cid, data: new Date().toLocaleString('pt-BR'), qtd: cos.length });
    setP(100, 'Concluído!');
    setTimeout(() => exibir(), 300);

  } catch(e) {
    g('res').innerHTML = `
      <div class="empty">
        <div class="ei">⚠️</div>
        <p style="color:var(--red);font-weight:700">Erro ao buscar dados</p>
        <small style="line-height:1.8">${e.message || 'Erro desconhecido'}<br>Verifique: servidor rodando · GOOGLE_API_KEY no .env · Places API ativada no Google Cloud</small>
      </div>`;
  }
  g('bbs').disabled = false;
}

// ─── EXIBIR ───────────────────────────────────────────────────
function exibir() {
  const el = g('res'); if (!el) return;
  let lista = cos;
  if (filterType === 'pneus') lista = cos.filter(x => x.tipo === 'Loja de Pneus');
  else if (filterType === 'borr') lista = cos.filter(x => x.tipo.includes('Borracharia'));
  else if (filterType === 'auto') lista = cos.filter(x => x.tipo === 'Auto Center' || x.tipo.includes('Mecânica'));
  el.innerHTML = `<div class="results-header"><div class="count"><span>${lista.length}</span> empresa${lista.length!==1?'s':''} encontrada${lista.length!==1?'s':''}</div></div>`;
  if (!lista.length) { el.innerHTML += `<div class="empty"><div class="ei">🔍</div><p>Nenhuma empresa nesta categoria.</p><small>Tente outro filtro.</small></div>`; return; }
  const gr = document.createElement('div'); gr.className = 'grid';
  lista.forEach(x => gr.appendChild(mkCard(x)));
  el.appendChild(gr);
}

// ─── CARD ─────────────────────────────────────────────────────
function mkCard(co) {
  const d = document.createElement('div'); d.className = 'cc';
  const idx = co._idx !== undefined ? co._idx : 0;
  const iF = favs.has(co.id);
  const rat = parseFloat(co.avaliacao) || 0;
  const st = '★'.repeat(Math.round(rat)) + '☆'.repeat(5 - Math.round(rat));
  const aHTML = co.abertura
    ? `<div class="cc-since">📅 Aberta desde ${fmtData(co.abertura)} · ${calcIdade(co.abertura)}</div>`
    : `<div class="cc-no-since" id="abe_${idx}">📅 Data de abertura — consulte o CNPJ</div>`;
  d.innerHTML = `
    <div class="cc-top">
      <div class="cc-name">${co.nome}</div>
      <div class="cc-rating"><div class="stars">${st}</div><div class="rnum">${co.avaliacao}</div></div>
    </div>
    <div class="cc-type">${co.tipo}</div>
    <div class="cc-addr">📍 ${co.endereco}${co.cidade?', '+co.cidade:''}${co.uf?'/'+co.uf:''}</div>
    <div class="cc-phone">${co.telefone?'📞 '+co.telefone:'<span style="color:var(--txt3);font-size:11px">Telefone não disponível</span>'}</div>
    ${aHTML}
    <hr class="cc-sep"/>
    <div class="cacts">
      ${co.gmaps_url?`<button class="ab" onclick="window.open('${co.gmaps_url}','_blank')">🗺 Maps</button>`:co.lat?`<button class="ab" onclick="openMap(${co.lat},${co.lon})">🗺 Mapa</button>`:''}
      ${co.website?`<button class="ab" onclick="window.open('${co.website}','_blank')">🌐 Site</button>`:''}
      ${co.telefone?`<button class="ab wpp" onclick="wppIdx(${idx})">💬 WhatsApp</button>`:''}
      <button class="ab ${iF?'fva':''}" id="fv_${idx}" onclick="tgFav(${idx})">${iF?'★ Salvo':'☆ Favoritar'}</button>
      <button class="ab ${co.abertura?'cnpj-loaded':''}" onclick="tgCNPJ(${idx})" id="cbtn_${idx}">${co.abertura?'✅ CNPJ':'🔎 CNPJ'}</button>
      <button class="ab ab-store" onclick="openStoreModal(${idx})">📋 Registrar</button>
    </div>
    <div class="cnpj-inline" id="ci_${idx}">
      <p>Informe o CNPJ para buscar a data de abertura:</p>
      <div class="cinp-row">
        <input id="cv_${idx}" placeholder="00.000.000/0001-00" maxlength="18" inputmode="numeric" oninput="maskCNPJ(this)" onkeydown="if(event.key==='Enter')bCNPJCard(${idx})"/>
        <button onclick="bCNPJCard(${idx})">Buscar</button>
      </div>
      <div class="cinp-result" id="cr_${idx}"></div>
    </div>`;
  return d;
}
function tgFav(idx) {
  const co = cos[idx]; if (!co) return;
  favs.has(co.id) ? favs.delete(co.id) : favs.add(co.id);
  const b = g('fv_'+idx); if (!b) return;
  b.textContent = favs.has(co.id) ? '★ Salvo' : '☆ Favoritar';
  b.classList.toggle('fva', favs.has(co.id));
}
function tgCNPJ(idx) {
  const f = g('ci_'+idx); if (!f) return;
  f.style.display = f.style.display === 'block' ? 'none' : 'block';
}
function wppIdx(idx) { const co = cos[idx]; if (co) wpp(co.telefone, co.nome); }

// ─── CNPJ ─────────────────────────────────────────────────────
function maskCNPJ(inp) {
  let v = inp.value.replace(/\D/g,'');
  if (v.length > 14) v = v.slice(0,14);
  if (v.length > 12) v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,'$1.$2.$3/$4-$5');
  else if (v.length > 8) v = v.replace(/^(\d{2})(\d{3})(\d{3})(\d+)$/,'$1.$2.$3/$4');
  else if (v.length > 5) v = v.replace(/^(\d{2})(\d{3})(\d+)$/,'$1.$2.$3');
  else if (v.length > 2) v = v.replace(/^(\d{2})(\d+)$/,'$1.$2');
  inp.value = v;
}
async function bCNPJCard(idx) {
  const inp = g('cv_'+idx), res = g('cr_'+idx);
  if (!inp || !res) return;
  const raw = inp.value.replace(/\D/g,'');
  if (raw.length !== 14) { res.textContent = '⚠ CNPJ precisa ter 14 dígitos.'; res.style.display = 'block'; return; }
  res.innerHTML = '<span class="spin-sm"></span> Consultando...'; res.style.display = 'block';
  try {
    const d = await fetchCNPJ(raw);
    const co = cos[idx];
    if (co) { co.abertura = d.data_inicio_atividade || null; co.cnpj = raw; }
    const ok = (d.situacao||'').toLowerCase().includes('ativa');
    const badge = ok ? '<span class="badge-ok">● Ativa</span>' : `<span class="badge-bad">● ${d.situacao||'Inativa'}</span>`;
    res.innerHTML = `${badge} Aberta em <strong>${fmtData(d.data_inicio_atividade)}</strong> · ${calcIdade(d.data_inicio_atividade)}<br><span style="font-size:10px;color:var(--txt3)">${d.razao_social||''}</span>`;
    const abeEl = g('abe_'+idx);
    if (abeEl && d.data_inicio_atividade) abeEl.outerHTML = `<div class="cc-since">📅 Aberta desde ${fmtData(d.data_inicio_atividade)} · ${calcIdade(d.data_inicio_atividade)}</div>`;
    const cbtn = g('cbtn_'+idx); if (cbtn) { cbtn.textContent = '✅ CNPJ'; cbtn.classList.add('cnpj-loaded'); }
  } catch(e) {
    res.innerHTML = `<span style="color:var(--red)">⚠ CNPJ não encontrado. Verifique o número.</span>`;
  }
}
async function qCNPJ() {
  const raw = g('icnpj').value.replace(/\D/g,'');
  if (raw.length !== 14) { alert('CNPJ precisa ter 14 dígitos.'); return; }
  const btn = g('bcnpjbtn'); btn.disabled = true; btn.textContent = 'Consultando...';
  const r = g('cres'); r.style.display = 'block';
  r.innerHTML = '<div style="display:flex;align-items:center;gap:.5rem;font-size:13px;color:var(--txt2)"><div class="spin-sm"></div> Consultando bases públicas...</div>';
  try {
    const d = await fetchCNPJ(raw);
    const ok = (d.situacao||'').toLowerCase().includes('ativa');
    r.innerHTML = `
      <div class="cnpj-card">
        <div class="razao">${d.razao_social||'—'}</div>
        ${d.nome_fantasia?`<div style="font-size:12px;color:var(--txt2);margin-bottom:.5rem">${d.nome_fantasia}</div>`:''}
        <div style="margin-bottom:.8rem">
          ${ok?'<span class="badge-ok">● Ativa</span>':`<span class="badge-bad">● ${d.situacao||'Inativa'}</span>`}
          ${d.natureza?`<span class="badge-yel" style="margin-left:6px">${d.natureza}</span>`:''}
        </div>
        <div class="cnpj-grid">
          <div class="cnpj-item"><div class="k">📅 Data de Abertura</div><div class="v" style="color:var(--green);font-weight:700">${d.data_inicio_atividade?fmtData(d.data_inicio_atividade):'Não informado'}</div></div>
          <div class="cnpj-item"><div class="k">⏳ Tempo de atividade</div><div class="v">${calcIdade(d.data_inicio_atividade)}</div></div>
          <div class="cnpj-item"><div class="k">🏙 Município</div><div class="v">${d.municipio||'—'} / ${d.uf||'—'}</div></div>
          <div class="cnpj-item"><div class="k">📞 Telefone</div><div class="v">${d.telefone||'—'}</div></div>
          <div class="cnpj-item"><div class="k">📂 CNAE</div><div class="v" style="font-size:10px">${d.cnae||'—'}</div></div>
          <div class="cnpj-item"><div class="k">🏢 Porte</div><div class="v">${d.porte||'—'}</div></div>
        </div>
      </div>`;
  } catch(e) {
    r.innerHTML = `<div style="color:var(--red);font-size:12px;padding:.5rem">⚠ CNPJ não encontrado ou serviço indisponível. Tente novamente.</div>`;
  }
  btn.disabled = false; btn.textContent = 'Consultar';
}
async function fetchCNPJ(raw) {
  function parseBrasil(d) {
    return { razao_social:d.razao_social||'', nome_fantasia:d.nome_fantasia||'', situacao:d.descricao_situacao_cadastral||'', data_inicio_atividade:d.data_inicio_atividade||'', municipio:d.municipio||'', uf:d.uf||'', telefone:d.ddd_telefone_1?'('+d.ddd_telefone_1+') '+(d.telefone_1||''):'', cnae:d.cnae_fiscal_descricao||'', porte:d.porte||'', natureza:d.natureza_juridica?d.natureza_juridica.split(' - ')[0]:'' };
  }
  function parseReceita(d) {
    if (!d.nome||d.status==='ERROR') return null;
    const dt = d.abertura?d.abertura.split('/').reverse().join('-'):'';
    return { razao_social:d.nome||'', nome_fantasia:d.fantasia||'', situacao:d.situacao||'', data_inicio_atividade:dt, municipio:d.municipio||'', uf:d.uf||'', telefone:d.telefone||'', cnae:(d.atividade_principal&&d.atividade_principal[0]&&d.atividade_principal[0].text)||'', porte:d.porte||'', natureza:d.natureza_juridica||'' };
  }
  function parsePub(d) {
    if (!d.razao_social) return null;
    const est = d.estabelecimento||{};
    return { razao_social:d.razao_social||'', nome_fantasia:est.nome_fantasia||'', situacao:est.situacao_cadastral||'', data_inicio_atividade:est.data_inicio_atividade||'', municipio:(est.cidade&&est.cidade.nome)||'', uf:(est.estado&&est.estado.sigla)||'', telefone:est.ddd1?'('+est.ddd1+') '+(est.telefone1||''):'', cnae:(est.atividade_principal&&est.atividade_principal.descricao)||'', porte:(d.porte&&d.porte.descricao)||'', natureza:(d.natureza_juridica&&d.natureza_juridica.descricao)||'' };
  }
  const APIS = [
    { url:'https://brasilapi.com.br/api/cnpj/v1/'+raw, parse:parseBrasil },
    { url:'https://receitaws.com.br/v1/cnpj/'+raw, parse:parseReceita },
    { url:'https://publica.cnpj.ws/cnpj/'+raw, parse:parsePub }
  ];
  const PROXIES = [
    u=>'https://corsproxy.io/?'+encodeURIComponent(u),
    u=>'https://api.allorigins.win/raw?url='+encodeURIComponent(u),
    u=>'https://api.codetabs.com/v1/proxy?quest='+encodeURIComponent(u)
  ];
  const tentativas = [];
  for (const api of APIS) { tentativas.push({url:api.url,parse:api.parse}); for (const px of PROXIES) tentativas.push({url:px(api.url),parse:api.parse}); }
  let lastErr = 'Sem resposta';
  for (const t of tentativas) {
    try {
      const ctrl = new AbortController(); const timer = setTimeout(()=>ctrl.abort(), 6000);
      const r = await fetch(t.url,{headers:{'Accept':'application/json'},signal:ctrl.signal});
      clearTimeout(timer);
      if (!r.ok){lastErr='HTTP '+r.status;continue;}
      const json = await r.json(); const parsed = t.parse(json);
      if (!parsed||!parsed.razao_social){lastErr='Dados vazios';continue;}
      return parsed;
    } catch(e){ lastErr=e.name==='AbortError'?'Timeout':(e.message||'Erro de rede'); }
  }
  throw new Error(lastErr);
}

// ─── FAVORITOS ────────────────────────────────────────────────
function pFavs(c) {
  const fs = cos.filter(x => favs.has(x.id));
  c.innerHTML = `<div class="page-header"><h1>Favoritos</h1><p>${fs.length} empresa${fs.length!==1?'s':''} salva${fs.length!==1?'s':''}</p></div>`;
  if (!fs.length) { c.innerHTML += `<div class="empty"><div class="ei">⭐</div><p>Nenhum favorito ainda.</p><small>Favorite empresas na aba de busca.</small></div>`; return; }
  const gr = document.createElement('div'); gr.className = 'grid';
  fs.forEach(x => gr.appendChild(mkCard(x)));
  c.appendChild(gr);
}

// ─── HISTÓRICO ────────────────────────────────────────────────
function pHist(c) {
  c.innerHTML = `<div class="page-header"><h1>Histórico</h1><p>${hist.length} busca${hist.length!==1?'s':''} realizada${hist.length!==1?'s':''}</p></div>`;
  if (!hist.length) { c.innerHTML += `<div class="empty"><div class="ei">🕐</div><p>Nenhuma busca ainda.</p><small>Faça sua primeira busca.</small></div>`; return; }
  const w = document.createElement('div'); w.className = 'hist-list';
  hist.slice().reverse().forEach(h => {
    const d = document.createElement('div'); d.className = 'hi';
    const loc = h.cidade ? `${h.cidade} — ${h.uf}` : `${h.uf} (estado)`;
    const cache = h.fromCache ? '<span class="badge-cache">⚡ cache</span>' : '';
    d.innerHTML = `<div><div class="hi-city">${loc} ${cache}</div><div class="hi-dt">🕐 ${h.data}</div></div><div style="text-align:right"><div class="hi-count">${h.qtd}</div><div class="hi-lbl">resultados</div></div>`;
    w.appendChild(d);
  });
  c.appendChild(w);
}

// ─── EXPORTAR ─────────────────────────────────────────────────
function pExp(c) {
  const ca = cos.filter(x=>x.abertura).length;
  c.innerHTML = `
    <div class="page-header"><h1>Exportar Dados</h1><p>Baixe seus leads em CSV para qualquer CRM ou planilha.</p></div>
    <div class="stats-bar">
      <div class="stat"><div class="num">${cos.length}</div><div class="lbl">Total</div></div>
      <div class="stat"><div class="num">${favs.size}</div><div class="lbl">Favoritas</div></div>
      <div class="stat"><div class="num">${ca}</div><div class="lbl">c/ Abertura</div></div>
      <div class="stat"><div class="num">${hist.length}</div><div class="lbl">Buscas</div></div>
    </div>
    <div class="export-wrap">
      <div class="export-card"><h3>📊 Exportar todas as empresas</h3><p>Nome, tipo, telefone, endereço, cidade, estado, avaliação e data de abertura.</p><button class="bex" onclick="expCSV('todas')" ${!cos.length?'disabled':''}>⬇ CSV Completo (${cos.length})</button></div>
      <div class="export-card"><h3>⭐ Exportar favoritas</h3><p>Apenas as empresas marcadas como favorita para prospecção prioritária.</p><button class="bex" onclick="expCSV('favs')" ${!favs.size?'disabled':''}>⬇ CSV Favoritas (${favs.size})</button></div>
      <div class="export-card"><h3>📅 Exportar com data de abertura</h3><p>Empresas com data identificada via CNPJ — segmente por tempo de mercado.</p><button class="bex" onclick="expCSV('abertura')" ${!ca?'disabled':''}>⬇ CSV c/ Abertura (${ca})</button></div>
    </div>`;
}
function expCSV(modo) {
  let lista = cos;
  if (modo==='favs') lista = cos.filter(x=>favs.has(x.id));
  else if (modo==='abertura') lista = cos.filter(x=>x.abertura);
  if (!lista.length) { alert('Nenhum dado para exportar.'); return; }
  const h = 'Nome,Tipo,Telefone,Endereço,Cidade,Estado,Avaliação,Data de Abertura,Tempo de Atividade\n';
  const rows = lista.map(c=>`"${c.nome}","${c.tipo}","${c.telefone}","${c.endereco}","${c.cidade}","${c.uf}","${c.avaliacao}","${c.abertura?fmtData(c.abertura):''}","${c.abertura?calcIdade(c.abertura):''}"`).join('\n');
  const b = new Blob(['﻿'+h+rows],{type:'text/csv;charset=utf-8;'});
  const u = URL.createObjectURL(b); const a = document.createElement('a');
  a.href=u; a.download=`autolead_${modo}_${new Date().toLocaleDateString('pt-BR').replace(/\//g,'-')}.csv`;
  a.click(); URL.revokeObjectURL(u);
}

// ─── LOJAS REGISTRADAS ────────────────────────────────────────
async function pStores(c) {
  c.innerHTML = `
    <div class="page-header"><h1>Lojas Registradas</h1><p>Gerencie o relacionamento com cada estabelecimento.</p></div>
    <div style="margin-bottom:1.2rem"><button class="bsc" style="width:auto;padding:11px 20px" onclick="openStoreModal()">+ Nova Loja</button></div>
    <div id="stores-list"><div class="ld"><div class="spin"></div><div style="color:var(--txt2)">Carregando...</div></div></div>`;
  const lista = await loadStores();
  const el = g('stores-list'); if (!el) return;
  if (!lista.length) {
    el.innerHTML = `<div class="empty"><div class="ei">🏪</div><p>Nenhuma loja registrada ainda.</p><small>Clique em "📋 Registrar" em um card de empresa ou em "+ Nova Loja" acima.</small></div>`;
    return;
  }
  const w = document.createElement('div'); w.className = 'stores-grid';
  lista.forEach(s => {
    const d = document.createElement('div'); d.className = 'store-card';
    const statusMap = { contato:'Em contato', cliente:'Já é cliente', retorno:'Possível retorno' };
    const classMap = { contato:'badge-blue', cliente:'badge-ok', retorno:'badge-yel' };
    const sLabel = statusMap[s.status] || s.status;
    const sClass = classMap[s.status] || 'badge-yel';
    const safeNome = (s.company_name||'').replace(/'/g,"\\'");
    const safeTel = (s.phone||'').replace(/'/g,"\\'");
    d.innerHTML = `
      <div class="store-card-top">
        <div class="store-name">${s.company_name}</div>
        <span class="${sClass}">${sLabel}</span>
      </div>
      ${s.phone?`<div class="store-info">📞 ${s.phone}</div>`:''}
      ${(s.city||s.state)?`<div class="store-info">📍 ${[s.city,s.state].filter(Boolean).join(', ')}</div>`:''}
      ${s.notes?`<div class="store-notes">${s.notes}</div>`:''}
      <div class="store-meta">Registrado em ${new Date(s.created_at).toLocaleDateString('pt-BR')}</div>
      <div class="cacts" style="margin-top:.7rem">
        ${s.phone?`<button class="ab wpp" onclick="wpp('${safeTel}','${safeNome}')">💬 WhatsApp</button>`:''}
        <button class="ab" style="color:var(--red);border-color:rgba(239,68,68,.3)" onclick="deleteStore('${s.id}')">🗑 Remover</button>
      </div>`;
    w.appendChild(d);
  });
  el.appendChild(w);
}
async function loadStores() {
  if (!sb) return [];
  try {
    const { data } = await sb.from('stores').select('*').order('created_at',{ascending:false});
    return data || [];
  } catch(e) { return []; }
}
function openStoreModal(idx) {
  currentStoreIdx = idx;
  const co = idx !== undefined ? cos[idx] : null;
  ['st-nome','st-tel','st-end','st-cid','st-uf','st-obs','st-coid'].forEach(id => { const el=g(id); if(el) el.value=''; });
  if (g('st-status')) g('st-status').value = 'contato';
  if (co) {
    if (g('st-nome')) g('st-nome').value = co.nome||'';
    if (g('st-tel')) g('st-tel').value = co.telefone||'';
    if (g('st-end')) g('st-end').value = co.endereco||'';
    if (g('st-cid')) g('st-cid').value = co.cidade||'';
    if (g('st-uf')) g('st-uf').value = co.uf||'';
    if (g('st-coid')) g('st-coid').value = co.id||'';
  }
  const modal = g('modal-store'); if (modal) modal.style.display = 'flex';
  const err = g('st-err'); if (err) err.style.display = 'none';
}
function closeStoreModal() {
  const modal = g('modal-store'); if (modal) modal.style.display = 'none';
  currentStoreIdx = undefined;
}
async function submitStore() {
  const nome = (g('st-nome').value||'').trim();
  if (!nome) { const e=g('st-err'); if(e){e.textContent='Nome da empresa é obrigatório.';e.style.display='block';} return; }
  const btn = g('st-btn');
  if (btn) { btn.disabled=true; btn.textContent='Salvando...'; }
  const storeData = {
    company_name: nome,
    company_id: (g('st-coid')?g('st-coid').value:'')||null,
    phone: (g('st-tel').value||'').trim()||null,
    address: (g('st-end').value||'').trim()||null,
    city: (g('st-cid').value||'').trim()||null,
    state: (g('st-uf').value||'').trim().toUpperCase()||null,
    status: g('st-status').value||'contato',
    notes: (g('st-obs').value||'').trim()||null
  };
  try {
    if (!sb) throw new Error('Banco de dados não conectado. Verifique a conexão com o Supabase.');
    const { error } = await sb.from('stores').insert(storeData);
    if (error) throw new Error(error.message);
    closeStoreModal();
    showToast('Loja registrada com sucesso!');
    if (ctab === 's') go('s');
  } catch(e) {
    const err = g('st-err'); if (err){ err.textContent='Erro: '+(e.message||'Tente novamente.'); err.style.display='block'; }
  }
  if (btn) { btn.disabled=false; btn.textContent='Salvar Loja'; }
}
async function deleteStore(id) {
  if (!confirm('Remover esta loja do registro?')) return;
  if (!sb) { alert('Banco de dados não conectado.'); return; }
  try {
    const { error } = await sb.from('stores').delete().eq('id', id);
    if (error) throw new Error(error.message);
    go('s');
  } catch(e) { alert('Erro ao remover: '+e.message); }
}

// ─── TOAST ────────────────────────────────────────────────────
function showToast(msg, color) {
  const t = document.createElement('div'); t.className = 'toast';
  t.style.cssText = `position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(0);background:${color==='red'?'var(--red)':'var(--green)'};color:#000;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:700;z-index:9999;white-space:nowrap;box-shadow:0 4px 20px rgba(0,0,0,.3)`;
  t.textContent = msg; document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}

// ─── UTILS ────────────────────────────────────────────────────
function fmtData(iso) {
  if (!iso) return '—';
  const [y,m,d] = (iso||'').split(/[-\/]/);
  return d ? `${d.padStart(2,'0')}/${m.padStart(2,'0')}/${y}` : iso;
}
function calcIdade(iso) {
  if (!iso) return '—';
  const [y,m,d] = (iso||'').split(/[-\/]/);
  const anos = Math.floor((new Date()-new Date(+y,+m-1,+(d||1)))/(365.25*24*3600*1e3));
  if (anos <= 0) return 'menos de 1 ano';
  return `${anos} ano${anos!==1?'s':''} no mercado`;
}
function openMap(lat,lon) { window.open(`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}&zoom=17`,'_blank'); }
function wpp(tel,nome) {
  const n = tel.replace(/\D/g,''), br = n.startsWith('55')?n:'55'+n;
  window.open(`https://wa.me/${br}?text=${encodeURIComponent('Olá '+nome+'! Entrei em contato pelo AutoLead Brasil. Gostaria de apresentar uma proposta comercial.')}`,'_blank');
}
