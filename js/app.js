// ─── CONFIG ──────────────────────────────────────────────────
const SUPA_URL = 'https://nbigfrdezkozzwqozvlp.supabase.co';
const SUPA_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5iaWdmcmRlemtvenp3cW96dmxwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5MDk2NjAsImV4cCI6MjA5MzQ4NTY2MH0.LWKWOvpIjkdd1w8aoAvixfNrpa1TuoX3B0mZ90_gXhM';
// Termos de busca por modo
const TERMS_VENDEDORES  = ['distribuidora de pneus','atacadista de pneus','loja de pneus','revenda de pneus','pneus truck center'];
const TERMS_COMPRADORES = ['transportadora cargas','empresa transporte rodoviario','logistica transporte cargas'];

// CNAEs: 4530-7/01 = Atacado pneus/peças | 4530-7/02 = Varejo pneus | 4930-2/02 = Transp. rodoviário cargas
const CNAE_VENDEDOR  = ['4530701','4530702'];
const CNAE_COMPRADOR = ['4930202'];
const CNAE_BLOQUEADO = ['4520006']; // Serviços de borracharia

const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'];
const MAX_DAILY = 10;
const CACHE_TTL_DAYS = 7;

// ─── ESTADO ───────────────────────────────────────────────────
let sb = null;
let user = null, signup = false, ctab = 'b';
let cos = [], favs = new Set(), favData = new Map(), hist = [], filterType = 'todos';
let searchMode = 'vendedores';
let theme = localStorage.getItem('al_theme') || 'dark';
let currentStoreIdx = undefined;
let currentPage = 0;
const PAGE_SIZE = 30;

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
  loadFavs();
  go('b');
}
function logout() {
  user = null; cos = []; favs = new Set(); favData = new Map(); hist = []; filterType = 'todos';
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
      <div class="mode-selector">
        <button class="mode-btn${searchMode==='vendedores'?' active':''}" onclick="setSearchMode('vendedores')">🏪 Lojas &amp; Atacadistas</button>
        <button class="mode-btn${searchMode==='compradores'?' active':''}" onclick="setSearchMode('compradores')">🚛 Frotistas / Compradores</button>
      </div>
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
        <span class="pill ${filterType==='atacado'?'active':''}" onclick="setFilter('atacado')">📦 Atacadistas</span>
        <span class="pill ${filterType==='loja'?'active':''}" onclick="setFilter('loja')">🔵 Lojas de Pneus</span>
        <span class="pill ${filterType==='frotista'?'active':''}" onclick="setFilter('frotista')">🚛 Frotistas</span>
        <span class="pill ${filterType==='novo'?'active':''}" onclick="setFilter('novo')">🆕 Leads Novos</span>
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
function setSearchMode(mode) { searchMode = mode; pBuscar(g('mc')); }

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

// ─── SUPABASE: CACHE / HISTÓRICO ──────────────────────────────
async function checkCache(searchKey) {
  if (!sb) return null;
  try {
    const { data, error } = await sb.from('searches')
      .select('results,updated_at').eq('user_email', user.email).eq('search_key', searchKey).maybeSingle();
    if (error) { console.warn('[cache] leitura:', error.message); return null; }
    if (!data || !data.results) return null;
    const ageDays = (Date.now() - new Date(data.updated_at).getTime()) / 86400000;
    return ageDays > CACHE_TTL_DAYS ? null : data.results;
  } catch(e) { console.warn('[cache] checkCache:', e); return null; }
}
async function saveToCache(searchKey, uf, city, results) {
  if (!sb) { showToast('Supabase não conectado — dados não salvos', 'red'); return; }
  try {
    const { error } = await sb.from('searches').upsert(
      { user_email: user.email, search_key: searchKey, state: uf, city: city || null, results, updated_at: new Date().toISOString() },
      { onConflict: 'user_email,search_key' }
    );
    if (error) throw error;
  } catch(e) {
    console.error('[cache] saveToCache:', e);
    showToast('Erro ao salvar no banco: ' + (e.message || e), 'red');
  }
}

// ─── SUPABASE: FAVORITOS ──────────────────────────────────────
async function loadFavs() {
  if (!sb || !user) return;
  try {
    const { data, error } = await sb.from('favorites')
      .select('place_id, company_data')
      .eq('user_email', user.email);
    if (error) throw error;
    (data || []).forEach(f => {
      favs.add(f.place_id);
      if (f.company_data) favData.set(f.place_id, { ...f.company_data, id: f.place_id });
    });
  } catch(e) { console.warn('[favs] loadFavs:', e); }
}

// ─── CHAMADAS AO BACKEND ──────────────────────────────────────

/**
 * Busca um termo com paginação automática no backend.
 * O backend percorre até 3 páginas (≤60 resultados) e, quando cidade está
 * vazia, itera sobre as principais cidades do estado via BrasilAPI.
 *
 * Retorna array de { place_id, name, formatted_address, rating, place_types }
 */
async function apiBuscarTermo(uf, cidade, termo) {
  const params = new URLSearchParams({ uf, query: termo });
  if (cidade) params.set('cidade', cidade);
  const r = await fetch('/api/buscar?' + params);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || 'Erro no servidor (' + r.status + ')');
  }
  const d = await r.json();
  const denied = (d.errors || []).find(e => e.includes('REQUEST_DENIED') || e.includes('DENIED'));
  if (denied) throw new Error('API Key recusada: ' + denied);
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
  if (n.includes('distribuidora') || n.includes('atacadista') || n.includes('atacado de pneu')) return 'Atacadista de Pneus';
  if (n.includes('pneu') || n.includes('tyre') || n.includes('tire') || n.includes('revenda de pneu')) return 'Loja de Pneus';
  if (n.includes('transport') || n.includes('frete') || n.includes('logística') || n.includes('logistica') || n.includes('frota')) return 'Frotista / Transportadora';
  if (n.includes('borracharia') || n.includes('borracha')) return 'Borracharia';
  if (n.includes('auto center') || n.includes('autocenter')) return 'Auto Center';
  if (types.includes('car_repair')) return 'Auto Center';
  return 'Comércio Automotivo';
}

// Converte resultado bruto do Places Text Search para o formato de card.
// Telefone e site ficam vazios até o usuário clicar em "Carregar contato".
function textToCard(p, idx) {
  const nome = p.name || '';
  const rating = p.rating;
  return {
    _idx: idx,
    id: p.place_id || '',
    nome,
    endereco: p.formatted_address || '',
    cidade: '', uf: '',
    telefone: p.phone || '',
    website:  p.website || '',
    avaliacao: rating != null ? parseFloat(rating).toFixed(1) : '—',
    tipo: detectTipo(p.place_types || [], nome),
    lat: null, lon: null,
    abertura: null,
    gmaps_url: '',
    _detailsLoaded: !!(p.phone || p.website),
  };
}

// Carrega telefone/site/maps sob demanda para um card específico.
async function loadDetails(idx) {
  const co = cos[idx]; if (!co) return;
  const btn = g('det_' + idx);
  if (btn) { btn.disabled = true; btn.textContent = '⌛ Carregando...'; }
  const details = await apiDetails(co.id);
  if (details) {
    co.telefone  = details.telefone  || '';
    co.website   = details.website   || '';
    co.gmaps_url = details.gmaps_url || '';
    co.lat       = details.lat;
    co.lon       = details.lon;
  }
  co._detailsLoaded = true;
  const cardEl = document.querySelector(`.cc[data-idx="${idx}"]`);
  if (cardEl) cardEl.replaceWith(mkCard(co));
}

// ─── BUSCAR ───────────────────────────────────────────────────
async function buscar() {
  const uf = g('suf').value;
  const cid = (g('scid').value || '').trim();
  if (!uf) { alert('Selecione o estado.'); return; }

  const baseKey    = cid ? `${uf}_${cid.replace(/\s+/g,'_').toLowerCase()}` : uf;
  const searchKey  = `${baseKey}_${searchMode}`;
  const modeLabel  = searchMode === 'compradores' ? '🚛 Frotistas' : '🏪 Lojas & Atacadistas';
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
    const termos = searchMode === 'compradores' ? TERMS_COMPRADORES : TERMS_VENDEDORES;

    for (let i = 0; i < termos.length; i++) {
      const termo = termos[i];
      setP(20 + Math.round((i / termos.length) * 60), 'Buscando "' + termo + '"...');
      try {
        // Backend faz paginação automática (até 60 resultados) e
        // itera cidades via BrasilAPI quando cidade não é informada.
        const items = await apiBuscarTermo(uf, cid, termo);
        for (const p of items) {
          if (!seenIds.has(p.place_id)) { seenIds.add(p.place_id); allResults.push(p); }
        }
      } catch(e) {
        if (e.message.includes('recusada') || e.message.includes('DENIED')) throw e;
      }
    }

    if (allResults.length === 0) {
      cos = [];
      hist.push({ uf, cidade: cid, data: new Date().toLocaleString('pt-BR'), qtd: 0, mode: searchMode });
      await incrementRateLimit(searchKey);
      g('res').innerHTML = `<div class="empty"><div class="ei">🔍</div><p>Nenhuma empresa encontrada em ${displayLoc}.</p><small>Tente outra cidade ou verifique se a Places API está ativada na chave do servidor.</small></div>`;
      g('bbs').disabled = false;
      return;
    }

    setP(85, `Processando ${allResults.length} resultados...`);
    cos = allResults.map((p, i) => textToCard(p, i));
    currentPage = 0;

    setP(95, 'Salvando no banco...');
    await incrementRateLimit(searchKey);
    await saveToCache(searchKey, uf, cid, cos);
    hist.push({ uf, cidade: cid, data: new Date().toLocaleString('pt-BR'), qtd: cos.length, mode: searchMode });
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

// ─── EXIBIR (paginado) ────────────────────────────────────────
function exibir() {
  const el = g('res'); if (!el) return;
  let lista = cos;
  if      (filterType === 'atacado')  lista = cos.filter(x => x.tipo === 'Atacadista de Pneus');
  else if (filterType === 'loja')     lista = cos.filter(x => x.tipo === 'Loja de Pneus');
  else if (filterType === 'frotista') lista = cos.filter(x => x.tipo === 'Frotista / Transportadora');
  else if (filterType === 'novo')     lista = cos.filter(x => x._isNovo === true);

  const total = lista.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage >= totalPages) currentPage = 0;
  const start = currentPage * PAGE_SIZE;
  const pagina = lista.slice(start, start + PAGE_SIZE);

  el.innerHTML = `
    <div class="results-header">
      <div class="count"><span>${total}</span> empresa${total!==1?'s':''} encontrada${total!==1?'s':''}</div>
      ${totalPages > 1 ? `<div class="page-info">Página ${currentPage+1} de ${totalPages}</div>` : ''}
    </div>`;

  if (!pagina.length) {
    el.innerHTML += `<div class="empty"><div class="ei">🔍</div><p>Nenhuma empresa nesta categoria.</p><small>Tente outro filtro.</small></div>`;
    return;
  }
  const gr = document.createElement('div'); gr.className = 'grid';
  pagina.forEach(x => gr.appendChild(mkCard(x)));
  el.appendChild(gr);
  if (totalPages > 1) el.appendChild(mkPagination(currentPage, totalPages));
}

function mkPagination(current, total) {
  const nav = document.createElement('div'); nav.className = 'pagination';
  const pages = [];
  if (total <= 7) {
    for (let i = 0; i < total; i++) pages.push(i);
  } else {
    pages.push(0);
    if (current > 2) pages.push('…');
    for (let i = Math.max(1, current - 1); i <= Math.min(total - 2, current + 1); i++) pages.push(i);
    if (current < total - 3) pages.push('…');
    pages.push(total - 1);
  }
  const prev = current > 0
    ? `<button class="page-btn" onclick="setPage(${current-1})">← Anterior</button>` : '';
  const next = current < total - 1
    ? `<button class="page-btn" onclick="setPage(${current+1})">Próxima →</button>` : '';
  const nums = pages.map(p => p === '…'
    ? `<span class="page-ellipsis">…</span>`
    : `<button class="page-btn${p===current?' active':''}" onclick="setPage(${p})">${p+1}</button>`
  ).join('');
  nav.innerHTML = prev + nums + next;
  return nav;
}

function setPage(n) {
  currentPage = n;
  exibir();
  const el = g('res'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── CARD ─────────────────────────────────────────────────────
function mkCard(co) {
  const d = document.createElement('div'); d.className = 'cc';
  const idx = co._idx !== undefined ? co._idx : 0;
  d.dataset.idx = idx;
  const iF = favs.has(co.id);
  const rat = parseFloat(co.avaliacao) || 0;
  const st = '★'.repeat(Math.round(rat)) + '☆'.repeat(5 - Math.round(rat));
  const aHTML = co.abertura
    ? `<div class="cc-since">📅 Aberta desde ${fmtData(co.abertura)} · ${calcIdade(co.abertura)}</div>`
    : `<div class="cc-no-since" id="abe_${idx}">📅 Data de abertura — consulte o CNPJ</div>`;

  // Telefone: carrega sob demanda se ainda não foi buscado
  const phoneHtml = co.telefone
    ? `<div class="cc-phone">📞 ${co.telefone}</div>`
    : co._detailsLoaded
      ? `<div class="cc-phone" style="color:var(--txt3);font-size:11px">Telefone não disponível</div>`
      : `<div class="cc-phone"><button class="ab" id="det_${idx}" onclick="loadDetails(${idx})">📞 Carregar contato</button></div>`;

  const mapsBtn = co.gmaps_url
    ? `<button class="ab" onclick="window.open('${co.gmaps_url}','_blank')">🗺 Maps</button>`
    : co.lat ? `<button class="ab" onclick="openMap(${co.lat},${co.lon})">🗺 Mapa</button>` : '';
  const siteBtn = co.website ? `<button class="ab" onclick="window.open('${co.website}','_blank')">🌐 Site</button>` : '';
  const wppBtn  = co.telefone ? `<button class="ab wpp" onclick="wppIdx(${idx})">💬 WhatsApp</button>` : '';

  const leadBadge = co._isNovo
    ? `<span class="badge-novo">🆕 Lead Novo</span>`
    : co._leadStatus === 'bloqueado' ? `<span class="badge-bad">🚫 Descartado</span>`
    : co._leadStatus === 'comprador' ? `<span class="badge-blue">🚛 Frotista</span>`
    : co._leadStatus === 'aprovado'  ? `<span class="badge-ok">✅ Aprovado</span>`
    : '';

  d.innerHTML = `
    <div class="cc-top">
      <div class="cc-name">${co.nome}</div>
      <div class="cc-rating"><div class="stars">${st}</div><div class="rnum">${co.avaliacao}</div></div>
    </div>
    ${leadBadge ? `<div style="margin-bottom:5px">${leadBadge}</div>` : ''}
    <div class="cc-type">${co.tipo}</div>
    <div class="cc-addr">📍 ${co.endereco}${co.cidade?', '+co.cidade:''}${co.uf?'/'+co.uf:''}</div>
    ${phoneHtml}
    ${aHTML}
    <hr class="cc-sep"/>
    <div class="cacts">
      ${mapsBtn}${siteBtn}${wppBtn}
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
async function tgFav(idx) {
  const co = cos[idx]; if (!co) return;
  const isFav = favs.has(co.id);
  if (isFav) {
    favs.delete(co.id); favData.delete(co.id);
    if (sb && user) {
      const { error } = await sb.from('favorites').delete()
        .eq('user_email', user.email).eq('place_id', co.id);
      if (error) { favs.add(co.id); favData.set(co.id, co); showToast('Erro ao remover favorito', 'red'); return; }
    }
  } else {
    favs.add(co.id); favData.set(co.id, co);
    if (sb && user) {
      const { error } = await sb.from('favorites').upsert(
        { user_email: user.email, place_id: co.id, company_data: co },
        { onConflict: 'user_email,place_id' }
      );
      if (error) { favs.delete(co.id); favData.delete(co.id); showToast('Erro ao salvar favorito', 'red'); return; }
    }
    showToast('Favorito salvo!');
  }
  const b = g('fv_'+idx); if (!b) return;
  b.textContent = favs.has(co.id) ? '★ Salvo' : '☆ Favoritar';
  b.classList.toggle('fva', favs.has(co.id));
}

async function unfavById(placeId) {
  favs.delete(placeId); favData.delete(placeId);
  if (sb && user) {
    const { error } = await sb.from('favorites').delete()
      .eq('user_email', user.email).eq('place_id', placeId);
    if (error) { showToast('Erro ao remover favorito', 'red'); return; }
  }
  // Atualiza card na aba de busca se ainda visível
  const i = cos.findIndex(c => c.id === placeId);
  if (i >= 0) { const b = g('fv_'+i); if (b) { b.textContent = '☆ Favoritar'; b.classList.remove('fva'); } }
  if (ctab === 'f') pFavs(g('mc'));
}
function tgCNPJ(idx) {
  const f = g('ci_'+idx); if (!f) return;
  f.style.display = f.style.display === 'block' ? 'none' : 'block';
}
function wppIdx(idx) { const co = cos[idx]; if (co) wpp(co.telefone, co.nome); }

// ─── VALIDAÇÃO DE LEAD (CNAE / MEI / Porte / Novo) ────────────
function isWithin24Months(isoDate) {
  if (!isoDate) return false;
  const parts = isoDate.split(/[-\/]/);
  const d = new Date(+parts[0], +parts[1] - 1, +(parts[2] || 1));
  return (new Date() - d) / (30.44 * 24 * 3600 * 1000) <= 24;
}

function validateLead(d) {
  const code  = (d.cnae_code || '').replace(/\D/g, '');
  const nome  = ((d.razao_social || '') + ' ' + (d.nome_fantasia || '')).toLowerCase();
  const porte = (d.porte || '').toUpperCase();
  const BLOCK_NOME = ['borracharia','borrachas','borracheiro','reforma de pneu','conserto de pneu','recapagem'];
  const nomeBlock = BLOCK_NOME.some(w => nome.includes(w));
  const isMEI     = d.is_mei === true;
  const isNovo    = isWithin24Months(d.data_inicio_atividade);
  const isVend    = CNAE_VENDEDOR.includes(code);
  const isComp    = CNAE_COMPRADOR.includes(code);
  const isCnaeBlk = CNAE_BLOQUEADO.includes(code);
  const isME_EPP  = porte.includes('MICRO') || porte.includes('PEQUENO');

  if (nomeBlock || isCnaeBlk) return { status:'bloqueado', label:'🚫 Descartado',       cls:'badge-bad',  msg:`CNAE ${code||'?'} — serviço de reparo/borracharia` };
  if (isMEI)                  return { status:'filtrado',  label:'⚠️ MEI',              cls:'badge-yel',  msg:'Microempreendedor Individual — fora do foco comercial' };
  if (isComp)                 return { status:'comprador', label:'🚛 Frotista',          cls:'badge-blue', msg:'Transportadora — potencial compradora de pneus em larga escala' };
  if (isVend && isNovo)       return { status:'novo',      label:'🆕 Lead Novo',         cls:'badge-novo', msg:'CNAE de comércio de pneus · empresa aberta há < 24 meses — prioridade alta' };
  if (isVend)                 return { status:'aprovado',  label:'✅ Aprovado',           cls:'badge-ok',   msg:'CNAE confirma comércio de pneus (atacado ou varejo)' };
  if (isME_EPP)               return { status:'potencial', label:'📦 ME/EPP — Verificar', cls:'badge-yel',  msg:`Porte compatível · CNAE ${code||'não mapeado'} — verifique manualmente` };
  return { status:'indefinido', label:'❓ Verificar', cls:'badge-yel', msg:`CNAE ${code||'não informado'} — classificação manual necessária` };
}

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
    const lead = validateLead(d);
    const isNovo = isWithin24Months(d.data_inicio_atividade);
    if (co) {
      co.abertura     = d.data_inicio_atividade || null;
      co.cnpj         = raw;
      co.porte        = d.porte || '';
      co.cnae         = d.cnae || '';
      co.cnae_code    = d.cnae_code || '';
      co._leadStatus  = lead.status;
      co._isNovo      = isNovo;
    }
    const ok = (d.situacao||'').toLowerCase().includes('ativa');
    const situBadge = ok ? '<span class="badge-ok">● Ativa</span>' : `<span class="badge-bad">● ${d.situacao||'Inativa'}</span>`;
    res.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px">
        ${situBadge}
        <span class="${lead.cls}">${lead.label}</span>
        ${isNovo ? '<span class="badge-novo">🆕 &lt; 24 meses</span>' : ''}
      </div>
      <div style="font-size:11px;color:var(--txt3);margin-bottom:5px">${lead.msg}</div>
      <strong>${fmtData(d.data_inicio_atividade)}</strong> · ${calcIdade(d.data_inicio_atividade)}<br>
      <span style="font-size:10px;color:var(--txt3)">${d.razao_social||''} · Porte: ${d.porte||'—'} · CNAE: ${d.cnae_code||'—'} ${d.cnae?'('+d.cnae.substring(0,45)+')':''}</span>`;
    const abeEl = g('abe_'+idx);
    if (abeEl && d.data_inicio_atividade) abeEl.outerHTML = `<div class="cc-since">📅 Aberta desde ${fmtData(d.data_inicio_atividade)} · ${calcIdade(d.data_inicio_atividade)}</div>`;
    const cbtn = g('cbtn_'+idx);
    if (cbtn) {
      cbtn.textContent = isNovo ? '🆕 Lead Novo' : lead.status === 'bloqueado' ? '🚫 CNPJ' : lead.status === 'aprovado' ? '✅ CNPJ' : '📋 CNPJ';
      cbtn.classList.add('cnpj-loaded');
    }
    // Atualiza badge no card caso seja novo
    if (isNovo || lead.status === 'aprovado' || lead.status === 'bloqueado') {
      const cardEl = document.querySelector(`.cc[data-idx="${idx}"]`);
      if (cardEl) cardEl.replaceWith(mkCard(co));
    }
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
        <div style="margin-bottom:.8rem;display:flex;flex-wrap:wrap;gap:5px">
          ${ok?'<span class="badge-ok">● Ativa</span>':`<span class="badge-bad">● ${d.situacao||'Inativa'}</span>`}
          ${(()=>{ const l=validateLead(d); return `<span class="${l.cls}">${l.label}</span>`; })()}
          ${isWithin24Months(d.data_inicio_atividade)?'<span class="badge-novo">🆕 Lead Novo</span>':''}
          ${d.natureza?`<span class="badge-yel">${d.natureza}</span>`:''}
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
    return { razao_social:d.razao_social||'', nome_fantasia:d.nome_fantasia||'', situacao:d.descricao_situacao_cadastral||'', data_inicio_atividade:d.data_inicio_atividade||'', municipio:d.municipio||'', uf:d.uf||'', telefone:d.ddd_telefone_1?'('+d.ddd_telefone_1+') '+(d.telefone_1||''):'', cnae:d.cnae_fiscal_descricao||'', cnae_code:String(d.cnae_fiscal||''), porte:d.porte||'', natureza:d.natureza_juridica?d.natureza_juridica.split(' - ')[0]:'', is_mei:d.opcao_pelo_mei===true };
  }
  function parseReceita(d) {
    if (!d.nome||d.status==='ERROR') return null;
    const dt = d.abertura?d.abertura.split('/').reverse().join('-'):'';
    const cnaeCode = ((d.atividade_principal&&d.atividade_principal[0]&&d.atividade_principal[0].code)||'').replace(/\D/g,'');
    return { razao_social:d.nome||'', nome_fantasia:d.fantasia||'', situacao:d.situacao||'', data_inicio_atividade:dt, municipio:d.municipio||'', uf:d.uf||'', telefone:d.telefone||'', cnae:(d.atividade_principal&&d.atividade_principal[0]&&d.atividade_principal[0].text)||'', cnae_code:cnaeCode, porte:d.porte||'', natureza:d.natureza_juridica||'', is_mei:d.opcao_pelo_mei===true||(d.natureza_juridica||'').toLowerCase().includes('microempreendedor') };
  }
  function parsePub(d) {
    if (!d.razao_social) return null;
    const est = d.estabelecimento||{};
    const cnaeCode = ((est.cnae_fiscal_principal&&est.cnae_fiscal_principal.codigo)||'').replace(/\D/g,'');
    return { razao_social:d.razao_social||'', nome_fantasia:est.nome_fantasia||'', situacao:est.situacao_cadastral||'', data_inicio_atividade:est.data_inicio_atividade||'', municipio:(est.cidade&&est.cidade.nome)||'', uf:(est.estado&&est.estado.sigla)||'', telefone:est.ddd1?'('+est.ddd1+') '+(est.telefone1||''):'', cnae:(est.atividade_principal&&est.atividade_principal.descricao)||'', cnae_code:cnaeCode, porte:(d.porte&&d.porte.descricao)||'', natureza:(d.natureza_juridica&&d.natureza_juridica.descricao)||'', is_mei:false };
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
  // Mescla: favoritos do banco + itens favoritados na sessão atual
  const map = new Map(favData);
  cos.filter(x => favs.has(x.id)).forEach(x => map.set(x.id, x));
  const fs = Array.from(map.values());

  c.innerHTML = `<div class="page-header"><h1>Favoritos</h1><p>${fs.length} empresa${fs.length!==1?'s':''} salva${fs.length!==1?'s':''} — persistido no banco</p></div>`;
  if (!fs.length) { c.innerHTML += `<div class="empty"><div class="ei">⭐</div><p>Nenhum favorito ainda.</p><small>Favorite empresas na aba de busca.</small></div>`; return; }
  const gr = document.createElement('div'); gr.className = 'grid';
  fs.forEach(co => gr.appendChild(mkFavCard(co)));
  c.appendChild(gr);
}

function mkFavCard(co) {
  const d = document.createElement('div'); d.className = 'cc';
  const rat = parseFloat(co.avaliacao) || 0;
  const st = '★'.repeat(Math.round(rat)) + '☆'.repeat(5 - Math.round(rat));
  const pid = (co.id || '').replace(/'/g, '');
  const phoneHtml = co.telefone
    ? `<div class="cc-phone">📞 ${co.telefone}</div>`
    : `<div class="cc-phone" style="color:var(--txt3);font-size:11px">Sem telefone registrado</div>`;
  const aHTML = co.abertura
    ? `<div class="cc-since">📅 Aberta desde ${fmtData(co.abertura)} · ${calcIdade(co.abertura)}</div>`
    : '';
  const mapsBtn = co.gmaps_url ? `<button class="ab" onclick="window.open('${co.gmaps_url}','_blank')">🗺 Maps</button>` : '';
  const siteBtn = co.website ? `<button class="ab" onclick="window.open('${co.website}','_blank')">🌐 Site</button>` : '';
  const wppBtn  = co.telefone ? `<button class="ab wpp" onclick="wpp('${co.telefone.replace(/'/g,'').replace(/"/g,'')}','${co.nome.replace(/'/g,'').replace(/"/g,'')}')">💬 WhatsApp</button>` : '';
  d.innerHTML = `
    <div class="cc-top">
      <div class="cc-name">${co.nome}</div>
      <div class="cc-rating"><div class="stars">${st}</div><div class="rnum">${co.avaliacao}</div></div>
    </div>
    <div class="cc-type">${co.tipo || ''}</div>
    <div class="cc-addr">📍 ${co.endereco || ''}${co.cidade?', '+co.cidade:''}${co.uf?'/'+co.uf:''}</div>
    ${phoneHtml}${aHTML}
    <hr class="cc-sep"/>
    <div class="cacts">
      ${mapsBtn}${siteBtn}${wppBtn}
      <button class="ab fva" onclick="unfavById('${pid}')">★ Remover</button>
    </div>`;
  return d;
}

// ─── HISTÓRICO ────────────────────────────────────────────────
async function pHist(c) {
  c.innerHTML = `
    <div class="page-header"><h1>Histórico de Pesquisas</h1><p>Clique em <strong>Restaurar</strong> para recarregar sem consumir a API</p></div>
    <div id="hist-content"><div class="ld"><div class="spin"></div><div style="color:var(--txt2)">Carregando...</div></div></div>`;

  let supaHist = [];
  if (sb) {
    try {
      const { data } = await sb.from('searches')
        .select('search_key, state, city, results, updated_at')
        .eq('user_email', user.email)
        .order('updated_at', { ascending: false })
        .limit(100);
      supaHist = data || [];
    } catch(e) { console.warn('Hist load:', e); }
  }

  // Adiciona buscas da sessão atual que ainda não estão no banco
  const supaKeys = new Set(supaHist.map(h => h.search_key));
  for (const h of hist.slice().reverse()) {
    const base = h.cidade ? `${h.uf}_${h.cidade.replace(/\s+/g,'_').toLowerCase()}` : h.uf;
    const key  = `${base}_${h.mode || 'vendedores'}`;
    if (!supaKeys.has(key)) {
      supaHist.unshift({ search_key: key, state: h.uf, city: h.cidade || null,
        results: null, updated_at: null, _qtd: h.qtd, _data: h.data });
    }
  }

  const el = g('hist-content'); if (!el) return;
  if (!supaHist.length) {
    el.innerHTML = `<div class="empty"><div class="ei">🕐</div><p>Nenhuma busca ainda.</p><small>Faça sua primeira pesquisa na aba Buscar.</small></div>`;
    return;
  }

  const w = document.createElement('div'); w.className = 'hist-list';
  supaHist.forEach(h => {
    const d = document.createElement('div'); d.className = 'hi';
    const loc = h.city ? `${h.city} — ${h.state}` : `${h.state} (estado inteiro)`;
    const qtd  = h.results ? h.results.length : (h._qtd ?? '—');
    const dt   = h.updated_at
      ? new Date(h.updated_at).toLocaleString('pt-BR')
      : (h._data || '');
    const canRestore = h.results && h.results.length > 0;
    const safeKey  = h.search_key.replace(/'/g, "\\'");
    const hMode    = h.search_key.endsWith('_compradores') ? 'compradores' : 'vendedores';
    const modeBadge = hMode === 'compradores'
      ? `<span class="hi-mode-badge hi-mode-comp">🚛 Frotistas</span>`
      : `<span class="hi-mode-badge hi-mode-vend">🏪 Lojas & Atacadistas</span>`;
    d.innerHTML = `
      <div style="flex:1;min-width:0">
        <div class="hi-city">${loc}</div>
        <div style="margin-top:3px">${modeBadge}</div>
        <div class="hi-dt">🕐 ${dt}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
        <div style="text-align:right"><div class="hi-count">${qtd}</div><div class="hi-lbl">resultados</div></div>
        <div style="display:flex;gap:5px">
          ${canRestore ? `<button class="ab hist-restore" onclick="restoreSearch('${safeKey}')">↩ Restaurar</button>` : ''}
          ${h.updated_at ? `<button class="ab hist-del" onclick="deleteHistory('${safeKey}')">🗑</button>` : ''}
        </div>
      </div>`;
    w.appendChild(d);
  });
  el.innerHTML = '';
  el.appendChild(w);
}

async function restoreSearch(searchKey) {
  const cached = await checkCache(searchKey);
  if (!cached || !cached.length) {
    showToast('Cache expirado — pesquise novamente para atualizar', 'red');
    return;
  }
  // Restaura o modo de busca a partir da chave
  if (searchKey.endsWith('_compradores')) searchMode = 'compradores';
  else if (searchKey.endsWith('_vendedores')) searchMode = 'vendedores';
  cos = cached;
  cos.forEach((c, i) => c._idx = i);
  currentPage = 0;
  filterType = 'todos';
  const modeLabel = searchMode === 'compradores' ? '🚛 Frotistas' : '🏪 Lojas & Atacadistas';
  showToast(`${cos.length} empresas restauradas · ${modeLabel}`);
  go('b');
}

async function deleteHistory(searchKey) {
  if (!confirm('Excluir este histórico de pesquisa?')) return;
  if (!sb) { showToast('Supabase não conectado', 'red'); return; }
  try {
    const { error } = await sb.from('searches').delete().eq('user_email', user.email).eq('search_key', searchKey);
    if (error) throw error;
    // Remove da lista em memória também
    hist = hist.filter(h => {
      const k = h.cidade ? `${h.uf}_${h.cidade.replace(/\s+/g,'_').toLowerCase()}` : h.uf;
      return k !== searchKey;
    });
    showToast('Histórico excluído.');
    pHist(g('mc'));
  } catch(e) {
    showToast('Erro ao excluir: ' + (e.message || e), 'red');
  }
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
  if (!sb || !user) return [];
  try {
    const { data, error } = await sb.from('stores')
      .select('*')
      .eq('user_email', user.email)
      .order('created_at', { ascending: false });
    if (error) { console.error('[stores] loadStores:', error); return []; }
    return data || [];
  } catch(e) { console.warn('[stores] loadStores:', e); return []; }
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
    user_email:   user ? user.email : null,
    company_name: nome,
    company_id:   (g('st-coid')?g('st-coid').value:'')||null,
    phone:        (g('st-tel').value||'').trim()||null,
    address:      (g('st-end').value||'').trim()||null,
    city:         (g('st-cid').value||'').trim()||null,
    state:        (g('st-uf').value||'').trim().toUpperCase()||null,
    status:       g('st-status').value||'contato',
    notes:        (g('st-obs').value||'').trim()||null,
  };
  try {
    if (!sb) throw new Error('Supabase não conectado — verifique a configuração.');
    if (!user) throw new Error('Faça login para salvar registros.');
    const { error } = await sb.from('stores').insert(storeData);
    if (error) throw new Error(error.message || JSON.stringify(error));
    closeStoreModal();
    showToast('Loja registrada com sucesso!');
    if (ctab === 's') go('s');
  } catch(e) {
    console.error('[stores] submitStore:', e);
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
