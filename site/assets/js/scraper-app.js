import { machines } from './scraper/machines.js';
import { crc32, parseDat } from './scraper/libretro-dat.js';

const $ = (id) => document.getElementById(id);
const extension = (name) => name.split('.').at(-1).toLowerCase();
const slash = (path) => path.replaceAll('\\', '/').replace(/^\.\//, '');
const basename = (path) => slash(path).split('/').at(-1);
const dirname = (path) => slash(path).split('/').slice(0, -1).join('/');
const stem = (path) => basename(path).replace(/\.[^.]+$/, '');
const artTypes = { boxart: 'Named_Boxarts', snap: 'Named_Snaps', title: 'Named_Titles' };
const datBase = 'https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/no-intro/';
const artFolders = { boxart: 'box', snap: 'preview', title: 'preview' };
const mediaFolders = { boxart: 'covers', snap: 'screenshots', title: 'titlescreens' };
const esdeNames = {
  'Nintendo - Game Boy Color': 'gbc', 'Nintendo - Game Boy Advance': 'gba', 'Nintendo - Game Boy': 'gb',
  'Nintendo - Super Nintendo Entertainment System': 'snes', 'Nintendo - Nintendo 64DD': 'n64dd', 'Nintendo - Nintendo 64': 'n64',
  'Nintendo - Family Computer Disk System': 'fds', 'Nintendo - Nintendo DSi': 'dsiware', 'Nintendo - Nintendo DS': 'nds',
  'Nintendo - Nintendo Entertainment System': 'nes', 'Nintendo - Pokemon Mini': 'pokemini', 'Nintendo - Virtual Boy': 'virtualboy',
  'Handheld Electronic Game': 'gameandwatch', 'Sega - 32X': 'sega32x', 'Sega - Dreamcast': 'dreamcast',
  'Sega - Mega-CD - Sega CD': 'segacd', 'Sega - Mega Drive - Genesis': 'megadrive', 'Sega - Game Gear': 'gamegear',
  'Sega - Master System - Mark III': 'mastersystem', 'Sega - Saturn': 'saturn', 'Sony - PlayStation Portable': 'psp',
  'Sony - PlayStation': 'psx', 'Sega - Naomi 2': 'naomi2', 'Sega - Naomi': 'naomi', 'Amstrad - CPC': 'amstradcpc',
  'Atari - ST': 'atarist', 'Atari - 2600': 'atari2600', 'Atari - 5200': 'atari5200', 'Atari - 7800': 'atari7800',
  'Atari - Jaguar': 'atarijaguar', 'Atari - Lynx': 'atarilynx', 'Bandai - WonderSwan Color': 'wonderswancolor',
  'Bandai - WonderSwan': 'wonderswan', 'Coleco - ColecoVision': 'colecovision', 'Commodore - Amiga': 'amiga',
  'Commodore - VIC-20': 'vic20', 'Commodore - 64': 'c64', 'FBNeo - Arcade Games': 'arcade', 'GCE - Vectrex': 'vectrex',
  'GamePark - GP32': 'gp32', MAME: 'mame', 'Microsoft - MSX2': 'msx2', 'Microsoft - MSX': 'msx',
  'Mattel - Intellivision': 'intellivision', 'NEC - PC Engine CD - TurboGrafx-CD': 'pcenginecd',
  'NEC - PC Engine SuperGrafx': 'supergrafx', 'NEC - PC Engine - TurboGrafx 16': 'pcengine', 'SNK - Neo Geo CD': 'neogeocd',
  'SNK - Neo Geo Pocket Color': 'ngpc', 'SNK - Neo Geo Pocket': 'ngp', 'SNK - Neo Geo': 'neogeo',
  'Magnavox - Odyssey2': 'odyssey2', 'TIC-80': 'tic80', 'Sharp - X68000': 'x68000', 'Watara - Supervision': 'supervision',
  DOS: 'dos', DOOM: 'doom', ScummVM: 'scummvm', Atomiswave: 'atomiswave'
};
const muosNames = {
  'Nintendo - Game Boy Color': 'Nintendo Game Boy Color', 'Nintendo - Game Boy Advance': 'Nintendo Game Boy Advance',
  'Nintendo - Game Boy': 'Nintendo Game Boy', 'Nintendo - Super Nintendo Entertainment System': 'Nintendo SNES-SFC',
  'Nintendo - Nintendo 64DD': 'Nintendo N64', 'Nintendo - Nintendo 64': 'Nintendo N64',
  'Nintendo - Family Computer Disk System': 'Nintendo NES-Famicom', 'Nintendo - Nintendo Entertainment System': 'Nintendo NES-Famicom',
  'Nintendo - Nintendo DSi': 'Nintendo DS', 'Nintendo - Nintendo DS': 'Nintendo DS', 'Nintendo - Pokemon Mini': 'Nintendo Pokemon Mini',
  'Nintendo - Virtual Boy': 'Nintendo Virtual Boy', 'Handheld Electronic Game': 'Handheld Electronic - Game and Watch',
  'Sega - 32X': 'Sega 32X', 'Sega - Dreamcast': 'Sega Dreamcast', 'Sega - Mega-CD - Sega CD': 'Sega Mega CD - Sega CD',
  'Sega - Mega Drive - Genesis': 'Sega Mega Drive - Genesis', 'Sega - Game Gear': 'Sega Game Gear',
  'Sega - Master System - Mark III': 'Sega Master System', 'Sega - Saturn': 'Sega Saturn',
  'Sony - PlayStation Portable': 'Sony Playstation Portable', 'Sony - PlayStation': 'Sony PlayStation',
  'Sega - Naomi 2': 'Sega Atomiswave Naomi', 'Sega - Naomi': 'Sega Atomiswave Naomi', 'Amstrad - CPC': 'Amstrad',
  'Atari - ST': 'Atari ST-STE-TT-Falcon', 'Atari - 2600': 'Atari 2600', 'Atari - 5200': 'Atari 5200',
  'Atari - 7800': 'Atari 7800', 'Atari - Jaguar': 'Atari Jaguar', 'Atari - Lynx': 'Atari Lynx',
  'Bandai - WonderSwan Color': 'Bandai WonderSwan-Color', 'Bandai - WonderSwan': 'Bandai WonderSwan-Color',
  'Coleco - ColecoVision': 'ColecoVision', 'Commodore - Amiga': 'Commodore Amiga', 'Commodore - VIC-20': 'Commodore VIC-20',
  'Commodore - 64': 'Commodore C64', 'FBNeo - Arcade Games': 'Arcade', 'GCE - Vectrex': 'GCE-Vectrex',
  MAME: 'Arcade', 'Microsoft - MSX2': 'Microsoft - MSX', 'Microsoft - MSX': 'Microsoft - MSX',
  'Mattel - Intellivision': 'Mattel - Intellivision', 'NEC - PC Engine CD - TurboGrafx-CD': 'NEC PC Engine CD',
  'NEC - PC Engine SuperGrafx': 'NEC PC Engine SuperGrafx', 'NEC - PC Engine - TurboGrafx 16': 'NEC PC Engine',
  'SNK - Neo Geo CD': 'SNK Neo Geo CD', 'SNK - Neo Geo Pocket Color': 'SNK Neo Geo Pocket - Color',
  'SNK - Neo Geo Pocket': 'SNK Neo Geo Pocket - Color', 'SNK - Neo Geo': 'SNK Neo Geo',
  'Magnavox - Odyssey2': 'Odyssey2 - VideoPac', 'TIC-80': 'TIC-80', 'Sharp - X68000': 'Sharp X68000',
  'Watara - Supervision': 'Watara Supervision', DOS: 'DOS', DOOM: 'DOOM', ScummVM: 'ScummVM',
  Atomiswave: 'Sega Atomiswave Naomi'
};
const consoleIds = {
  'Nintendo - Game Boy Color': 6, 'Nintendo - Game Boy Advance': 5, 'Nintendo - Game Boy': 4,
  'Nintendo - Super Nintendo Entertainment System': 3, 'Nintendo - Nintendo 64DD': 2, 'Nintendo - Nintendo 64': 2,
  'Nintendo - Family Computer Disk System': 81, 'Nintendo - Nintendo DSi': 78, 'Nintendo - Nintendo DS': 18,
  'Nintendo - Nintendo Entertainment System': 7, 'Nintendo - Pokemon Mini': 24, 'Nintendo - Virtual Boy': 28,
  'Handheld Electronic Game': 60, 'Sega - 32X': 10, 'Sega - Dreamcast': 40, 'Sega - Mega-CD - Sega CD': 9,
  'Sega - Mega Drive - Genesis': 1, 'Sega - Game Gear': 15, 'Sega - Master System - Mark III': 11,
  'Sega - Saturn': 39, 'Sony - PlayStation Portable': 41, 'Sony - PlayStation': 12,
  'Sega - Naomi 2': 27, 'Sega - Naomi': 27, 'Amstrad - CPC': 37, 'Atari - ST': 36, 'Atari - 5200': 50,
  'Atari - 7800': 51, 'Atari - Jaguar': 17, 'Atari - Lynx': 13, 'Atari - 2600': 25,
  'Bandai - WonderSwan Color': 53, 'Bandai - WonderSwan': 53, 'Coleco - ColecoVision': 44,
  'Commodore - Amiga': 35, 'Commodore - VIC-20': 34, 'Commodore - 64': 30, 'FBNeo - Arcade Games': 27,
  'GCE - Vectrex': 46, MAME: 27, 'Microsoft - MSX2': 29, 'Microsoft - MSX': 29,
  'Mattel - Intellivision': 45, 'NEC - PC Engine CD - TurboGrafx-CD': 76, 'NEC - PC Engine SuperGrafx': 8,
  'NEC - PC Engine - TurboGrafx 16': 8, 'SNK - Neo Geo CD': 56, 'SNK - Neo Geo Pocket Color': 14,
  'SNK - Neo Geo Pocket': 14, 'SNK - Neo Geo': 27, 'Magnavox - Odyssey2': 23, 'TIC-80': 65,
  'Sharp - X68000': 52, 'Watara - Supervision': 63, DOS: 26, Atomiswave: 27
};
const invalid = new Set(['"', '&', '*', '/', ':', '<', '>', '?', '`', '|']);
let files = new Map();
let library = null;
let directoryHandle = null;
let selectedSystem = null;
let controller = null;
let previewController = null;
let previewTimer = null;
let writeDirectly = false;
let raHash = null;
let previewCount = 0;
const previewUrls = [];
const previewLimit = 80;
const machineCache = new Map();
const raGames = new Map();
const raDetails = new Map();
const cacheDb = new Promise((resolve) => {
  if (!('indexedDB' in window)) return resolve(null);
  const req = indexedDB.open('treefrogui-art-cache', 1);
  req.onupgradeneeded = () => req.result.createObjectStore('art', { keyPath: 'url' });
  req.onsuccess = () => resolve(req.result);
  req.onerror = () => resolve(null);
});

function slugMachine(folder) {
  const value = folder.toLowerCase().replace(/[^0-9a-z]+/g, ' ').trim();
  const compact = value.replaceAll(' ', '');
  return Object.entries(machines).find(([, m]) => m.alias.some((a) => {
    const alias = a.toLowerCase().replace(/[^0-9a-z]+/g, ' ').trim();
    return compact === alias.replaceAll(' ', '') || ` ${value} `.includes(` ${alias} `);
  }))?.[0];
}

function countRom(file, machine) {
  const ext = extension(file.path);
  if (!(machines[machine]?.extensions || []).includes(ext)) return false;
  return !/ \(Disc \d+\)/i.test(stem(file.path)) || !files.has(`${file.path.replace(/ \(Disc \d+\).+$/i, '')}.m3u`);
}

function scan(filesMap) {
  if (selectedSystem) {
    const machine = slugMachine(selectedSystem);
    const games = [...filesMap.values()].map((f) => ({ ...f, rel: f.path })).filter((f) => countRom(f, machine));
    return { root: '', systems: games.length ? [{ name: selectedSystem, machine, prefix: '', systemPath: '', games }] : [], total: games.length };
  }
  const paths = [...filesMap.keys()];
  let root = '';
  const romsDir = paths.map((p) => p.split('/')).find((parts) => parts.some((part) => part.toLowerCase() === 'roms'));
  if (romsDir) root = romsDir.slice(0, romsDir.findIndex((part) => part.toLowerCase() === 'roms') + 1).join('/');
  const userdata = paths.find((p) => /(^|\/)userdata\/roms\//i.test(p));
  if (userdata) root = userdata.slice(0, userdata.toLowerCase().indexOf('userdata/roms') + 'userdata/roms'.length);
  if (!root) {
    const candidates = paths.filter((p) => p.includes('/')).map((p) => dirname(p));
    const systemPath = candidates.find((p) => slugMachine(basename(p)));
    if (systemPath && candidates.every((p) => p === systemPath || p.startsWith(systemPath + '/'))) root = dirname(systemPath);
  }
  const children = new Set(paths.map((p) => p.slice(root ? root.length + 1 : 0).split('/')[0]).filter(Boolean));
  const systems = [];
  for (const folder of children) {
    const machine = slugMachine(folder);
    if (!machine) continue;
    const prefix = root ? `${root}/${folder}/` : `${folder}/`;
    const games = paths.filter((p) => p.startsWith(prefix)).map((p) => ({ ...filesMap.get(p), rel: p.slice(prefix.length), systemPath: prefix.slice(0, -1) })).filter((f) => countRom(f, machine));
    if (games.length) systems.push({ name: folder, machine, prefix, systemPath: prefix.slice(0, -1), games });
  }
  systems.sort((a, b) => a.name.localeCompare(b.name));
  return { root, systems, total: systems.reduce((n, s) => n + s.games.length, 0) };
}

async function scanDirectory(handle, prefix = '') {
  if (!prefix) selectedSystem = slugMachine(handle.name) ? handle.name : null;
  for await (const [name, entry] of handle.entries()) {
    if (name.startsWith('.')) continue;
    const path = prefix ? `${prefix}/${name}` : name;
    if (entry.kind === 'directory') await scanDirectory(entry, path);
    else files.set(path, { path, getFile: () => entry.getFile() });
  }
}

function scanFiles(fileList) {
  files = new Map();
  const first = fileList[0]?.webkitRelativePath?.split('/')[0] || '';
  selectedSystem = slugMachine(first) ? first : null;
  for (const file of fileList) {
    const listed = slash(file.webkitRelativePath || file.name);
    const path = listed.split('/').slice(1).join('/');
    if (path && !path.split('/').some((part) => part.startsWith('.'))) files.set(path, { path, file, getFile: async () => file });
  }
}

function renderLibrary() {
  library = scan(files);
  if (!library.total) throw new Error('No supported ROMs found. Choose the SD card root, Roms folder, or a supported system folder.');
  $('library-label').textContent = `${library.total} games in ${library.systems.length} systems`;
  $('library-count').textContent = `${library.total} games · ${library.systems.length} systems`;
  $('system-list').replaceChildren(...library.systems.map((system) => {
    const li = document.createElement('li');
    li.textContent = `${system.name} — ${system.games.length} games`;
    return li;
  }));
  $('library-summary').hidden = false;
  $('start').disabled = false;
  const detected = detectFormat([...files.keys()]);
  if (detected) $('format').value = detected;
  updateExtractInstructions();
  $('scraper-message').textContent = '';
  schedulePreviews();
}

function detectFormat(paths) {
  const found = new Set();
  for (const path of paths.map((p) => slash(p).toLowerCase())) {
    const parts = path.split('/');
    for (let i = 1; i <= parts.length; i++) found.add(parts.slice(0, i).join('/'));
  }
  const profiles = [
    ['esde', [['es-de/settings/es_settings.xml', 65], ['es-de/downloaded_media', 30], ['es-de/gamelists', 20], ['es-de', 15]]],
    ['muos', [['muos', 65], ['muos/info/catalogue', 25], ['autorun.inf', 15]]],
    ['treefrogui', [['frogui', 65], ['cubegm', 25], ['roms', 10]]],
    ['knulli', [['userdata/system/batocera.conf', 70], ['system/batocera.conf', 70], ['userdata/roms', 15], ['system', 10]]],
    ['onionos', [['.tmp_update', 55], ['emu', 20], ['themes', 10], ['roms', 5]]],
    ['garlicos', [['cfw', 55], ['roms', 10], ['bios', 10], ['saves', 5]]],
    ['spruceos', [['spruce', 70], ['emu', 10], ['roms', 5]]],
    ['alliumos', [['allium', 70], ['roms', 5], ['bios', 5]]],
    ['nextui', [['nextui.zip', 75], ['.system', 10], ['roms', 5]]],
    ['minui', [['minui.zip', 75], ['.system', 10], ['roms', 5]]]
  ];
  const candidates = profiles.map(([format, signatures]) => [format, signatures.reduce((score, [path, weight]) => score + (found.has(path) ? weight : 0), 0)])
    .filter(([, score]) => score > 0).toSorted((a, b) => b[1] - a[1]);
  return candidates[0]?.[1] >= 45 && candidates[0][1] - (candidates[1]?.[1] || 0) >= 15 ? candidates[0][0] : null;
}

function sanitize(value) {
  return [...value.replace(/^\d+\)\s*/, '')].map((c) => invalid.has(c) ? '_' : c).join('');
}

function stripMetadata(value) {
  return value.replace(/\([^)]*\)|\[[^\]]*\]/g, '').trim();
}

function distance(a, b) {
  const row = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let prev = row[0]; row[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const old = row[j]; row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1)); prev = old;
    }
  }
  return row[b.length];
}

function jaroWinkler(a, b) {
  if (a === b) return 1;
  const range = Math.max(0, Math.floor(Math.max(a.length, b.length) / 2) - 1);
  const am = Array(a.length).fill(false), bm = Array(b.length).fill(false);
  let matches = 0;
  for (let i = 0; i < a.length; i++) for (let j = Math.max(0, i - range); j < Math.min(b.length, i + range + 1); j++) {
    if (!bm[j] && a[i] === b[j]) { am[i] = true; bm[j] = true; matches++; break; }
  }
  if (!matches) return 0;
  let k = 0, transpositions = 0;
  for (let i = 0; i < a.length; i++) if (am[i]) { while (!bm[k]) k++; if (a[i] !== b[k++]) transpositions++; }
  const m = matches, jaro = (m / a.length + m / b.length + (m - transpositions / 2) / m) / 3;
  let prefix = 0; while (prefix < Math.min(4, a.length, b.length) && a[prefix] === b[prefix]) prefix++;
  return jaro + prefix * 0.1 * (1 - jaro);
}

async function aiMatch(search, romName, choices, options) {
  if (!options.ai || !choices.length) return null;
  const prompt = `## Candidates\n${choices.join('\n')}\n\n## Instructions\nFind the best matching image for ROM name "${romName}" (searched name: "${search}"). Prefer a direct or translated title match; do not match a sequel to its predecessor. Prefer the ROM region where possible, otherwise use this order: ${options.regions}. Return null if no close match exists.\n\n## Output\nReturn JSON: {"bestMatch":"exact candidate filename or null"}.`;
  for (let attempt = 0; attempt < 3; attempt++) {
    const response = await request(`${options.aiUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.aiKey ? { Authorization: `Bearer ${options.aiKey}` } : {}) },
      body: JSON.stringify({ model: options.aiModel, temperature: 0.3, response_format: { type: 'json_object' }, messages: [{ role: 'user', content: prompt }] })
    }, options);
    try {
      const result = JSON.parse((await response.json()).choices?.[0]?.message?.content || '{}').bestMatch;
      if (typeof result !== 'string' || !result) return null;
      if (choices.includes(result)) return result;
    } catch { /* Retry malformed model output, as the standalone scraper does. */ }
  }
  return null;
}

async function candidatesFor(machine, options) {
  if (!machineCache.has(machine)) machineCache.set(machine, (async () => {
    const url = new URL(`${encodeURIComponent(machine)}.dat`, datBase).href;
    try {
      const database = parseDat(await (await request(url, {}, options)).text());
      database.artNames = database.names.map((name) => sanitize(`${name}.png`));
      return database;
    }
    catch (error) { if (error.message === 'HTTP 404') return { names: [], byCrc: new Map() }; throw error; }
  })());
  const database = await machineCache.get(machine);
  return database.artNames || [];
}

async function findArt(game, machine, type, options, fallback = true) {
  const list = await candidatesFor(machine, options);
  let name = stem(game.path);
  const database = await machineCache.get(machine);
  const fileType = extension(game.path);
  if (!game.artworkNamePromise && database.names.length && !['zip', 'chd', 'cue', 'm3u', 'gdi', 'iso', 'cso', 'pbp', '7z'].includes(fileType)) {
    game.artworkNamePromise = game.getFile().then(async (file) => file.size <= 256 * 1024 * 1024 ? database.byCrc.get(await crc32(file)) : null);
  }
  name = await game.artworkNamePromise || name;
  const exact = sanitize(`${name}.png`);
  // Systems without a No-Intro DAT still get a direct filename lookup, without listing a remote folder.
  if (!list.length) return { url: rawUrl(machine, artTypes[type], exact), match: 'perfect' };
  if (list.includes(exact) || name !== stem(game.path)) return { url: rawUrl(machine, artTypes[type], exact), match: 'perfect' };
  let search = stripMetadata(name);
  const tryName = async (query) => {
    const found = list.filter((item) => item.toLowerCase().includes(sanitize(query).toLowerCase()));
    if (!found.length) return null;
    const ai = await aiMatch(query, name, found, options);
    const best = ai || found.toSorted((a, b) => distance(stripMetadata(a), query) - distance(stripMetadata(b), query))[0];
    return { url: rawUrl(machine, artTypes[type], best), match: ai ? 'ai' : 'partial' };
  };
  let result = await tryName(search);
  if (result) return result;
  const fuzzy = list.map((candidate) => ({ candidate, score: jaroWinkler(sanitize(search), stripMetadata(candidate)) }))
    .filter((entry) => entry.score >= 0.85).toSorted((a, b) => b.score - a.score).slice(0, 25).map((entry) => entry.candidate);
  if (fuzzy.length) {
    const ai = await aiMatch(search, name, fuzzy, options), best = ai || fuzzy[0];
    return { url: rawUrl(machine, artTypes[type], best), match: ai ? 'ai' : 'partial' };
  }
  search = search.replaceAll('DX', '').trim(); result = await tryName(search); if (result) return result;
  search = search.split(': ', 1)[0].trim(); result = await tryName(search); if (result) return result;
  search = search.split('- ', 1)[0].trim(); result = await tryName(search); if (result) return result;
  const fallbacks = machines[machine]?.fallbacks || [];
  if (fallback) for (const fallbackMachine of fallbacks) {
    result = await findArt(game, fallbackMachine, type, options, false);
    if (result) return result;
  }
  return null;
}

function rawUrl(machine, type, filename) {
  return `https://raw.githubusercontent.com/libretro-thumbnails/${encodeURIComponent(machine.replaceAll(' ', '_'))}/master/${type}/${encodeURIComponent(filename)}`;
}

async function getCache(url) {
  const db = await cacheDb;
  if (!db) return null;
  return new Promise((resolve) => { const req = db.transaction('art').objectStore('art').get(url); req.onsuccess = () => resolve(req.result?.bytes || null); req.onerror = () => resolve(null); });
}

async function putCache(url, bytes) {
  const db = await cacheDb; if (!db) return;
  await new Promise((resolve) => { const req = db.transaction('art', 'readwrite').objectStore('art').put({ url, bytes }); req.onsuccess = req.onerror = () => resolve(); });
}

async function deleteCache(url) {
  const db = await cacheDb; if (!db) return;
  await new Promise((resolve) => { const req = db.transaction('art', 'readwrite').objectStore('art').delete(url); req.onsuccess = req.onerror = () => resolve(); });
}

async function request(url, init = {}, options = {}) {
  const signal = options.signal || controller?.signal;
  if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  const cacheable = !init.method && !url.includes('/API/');
  const cached = cacheable ? await getCache(url) : null;
  if (cached) return new Response(cached, { status: 200 });
  const tries = Number(options.retries ?? 2);
  let error;
  for (let attempt = 0; attempt <= tries; attempt++) {
    if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
    if (options.batchSize && options.requestCount && options.requestCount % options.batchSize === 0 && options.batchDelay) await delay(options.batchDelay, signal);
    try {
      const response = await fetch(url, { ...init, signal });
      if (response.status === 429 || response.status >= 500) throw Object.assign(new Error(`HTTP ${response.status}`), { retryAfter: response.headers.get('Retry-After') });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      options.requestCount = (options.requestCount || 0) + 1;
      if (cacheable) { const clone = response.clone(); putCache(url, new Uint8Array(await clone.arrayBuffer())).catch(() => {}); }
      return response;
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      error = e; if (e.message === 'HTTP 404' || attempt >= tries) break;
      const seconds = Number(e.retryAfter);
      const dateDelay = Date.parse(e.retryAfter || '') - Date.now();
      const retryAfter = Number.isFinite(seconds) && seconds >= 0 ? seconds * 1000 : dateDelay;
      await delay(retryAfter >= 0 ? retryAfter : Math.min(1000 * (attempt + 1), 5000), signal);
    }
  }
  throw error;
}

function delay(ms, signal = controller?.signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Cancelled', 'AbortError'));
    const finish = () => { signal?.removeEventListener('abort', abort); resolve(); };
    const abort = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(new DOMException('Cancelled', 'AbortError')); };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener('abort', abort, { once: true });
  });
}

async function downloadArtwork(url, options) {
  const cached = await getCache(url);
  if (cached) {
    try { const image = await createImageBitmap(new Blob([cached])); image.close(); return cached; }
    catch { await deleteCache(url); }
  }
  const response = await request(url, {}, options);
  const bytes = new Uint8Array(await response.arrayBuffer());
  try { const image = await createImageBitmap(new Blob([bytes])); image.close(); }
  catch (error) { await deleteCache(url); throw new Error(`Artwork could not be decoded from ${url}`, { cause: error }); }
  return bytes;
}

async function resize(bytes, width, height) {
  const image = await createImageBitmap(new Blob([bytes]));
  const useWidth = !height || image.width >= image.height;
  const targetWidth = useWidth ? width : Math.max(1, Math.round(image.width * height / image.height));
  const targetHeight = useWidth ? Math.max(1, Math.round(image.height * width / image.width)) : height;
  const canvas = document.createElement('canvas'); canvas.width = targetWidth; canvas.height = targetHeight;
  canvas.getContext('2d').drawImage(image, 0, 0, targetWidth, targetHeight); image.close();
  return new Uint8Array(await new Promise((resolve) => canvas.toBlob((blob) => blob.arrayBuffer().then(resolve), 'image/png')));
}

async function compose(first, second, width, height) {
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d'); const margin = Math.round(width * .05);
  const draw = async (bytes, kind) => {
    if (!bytes) return;
    const image = await createImageBitmap(new Blob([bytes]));
    let w, h, x, y;
    if (kind === 2) { w = image.width >= image.height ? width - margin : Math.round(image.width * (height - margin) / image.height); h = image.width < image.height ? height - margin : Math.round(image.height * (width - margin) / image.width); x = 0; y = (height - h) / 2 - margin; }
    else { w = image.width >= image.height ? width / 2 - margin : Math.round(image.width * (height / 2 - margin) / image.height); h = image.width < image.height ? height / 2 - margin : Math.round(image.height * (width / 2 - margin) / image.width); x = width - w; y = height - h; }
    ctx.drawImage(image, x, y, w, h); image.close();
  };
  await draw(second, 2); await draw(first, 1);
  return new Uint8Array(await new Promise((resolve) => canvas.toBlob((blob) => blob.arrayBuffer().then(resolve), 'image/png')));
}

function outputPath(game, machine, format, type, options) {
  const folder = dirname(game.path), file = basename(game.path), name = stem(game.path);
  const relativeFolder = dirname(game.rel || file);
  if (format === 'treefrogui') return `${folder}/.res/${name}.png`;
  if (format === 'minui') return `${folder}/.res/${file}.png`;
  if (format === 'nextui') return `${folder}/.media/${name}.png`;
  if (format === 'onionos' || format === 'garlicos' || format === 'spruceos' || format === 'alliumos' || format === 'anbernic') return `${folder}/Imgs/${name}.png`;
  if (format === 'funkey') return `${folder}/${name}.png`;
  if (format === 'knulli') return `${game.systemPath ? `${game.systemPath}/` : ''}images/${relativeFolder ? `${relativeFolder}/` : ''}${name}-${({boxart:'box',snap:'image',title:'titleshot'})[type]}.png`;
  if (format === 'esde') return `${options.mediaPath}/${esdeNames[machine] || folder.split('/').at(-1).toLowerCase()}/${mediaFolders[type]}/${relativeFolder ? `${relativeFolder}/` : ''}${name}.png`;
  if (format === 'muos') return `MUOS/info/catalogue/${muosNames[machine] || machine}/${artFolders[type]}/${name}.png`;
  return `${folder}/.res/${name}.png`;
}

function gameTypes(value) {
  return value.includes('+') ? value.split('+').map((v) => v === 'box' ? 'boxart' : v === 'snap' ? 'snap' : 'title') : [value];
}

function registerKnulli(game, artPath, type, opts, zipFiles) {
  const path = `${game.systemPath ? `${game.systemPath}/` : ''}gamelist.xml`;
  const mediaTag = { boxart: 'boxart', snap: 'image', title: 'titleshot' }[type];
  const relRom = slash(game.rel || basename(game.path));
  const existing = files.get(path);
  if (!zipFiles[path]) zipFiles[path] = existing ? existing.getFile().then((f) => f.text()) : Promise.resolve('<?xml version="1.0"?><gameList/>');
  zipFiles[path] = Promise.resolve(zipFiles[path]).then((xml) => {
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    const root = doc.documentElement;
    if (doc.querySelector('parsererror') || root.tagName !== 'gameList') throw new Error(`Invalid Knulli gamelist.xml: ${path}`);
    let entry = [...root.getElementsByTagName('game')].find((el) => el.querySelector('path')?.textContent === `./${relRom}`);
    if (!entry) { entry = doc.createElement('game'); const p = doc.createElement('path'); p.textContent = `./${relRom}`; const n = doc.createElement('name'); n.textContent = stem(game.path); entry.append(p, n); root.append(entry); }
    let media = entry.querySelector(mediaTag); if (!media) { media = doc.createElement(mediaTag); entry.append(media); }
    const prefix = game.systemPath ? `${game.systemPath}/` : '';
    media.textContent = `./${slash(artPath).slice(prefix.length)}`;
    return new TextEncoder().encode(`<?xml version="1.0"?>\n${new XMLSerializer().serializeToString(doc)}\n`);
  });
}

function addMuosConfig(width, zipFiles) {
  for (const path of ['theme/override/muxfavourite.txt', 'theme/override/muxhistory.txt', 'theme/override/muxplore.txt']) {
    const existing = files.get(path);
    zipFiles[path] = (async () => {
      let text = existing ? await (await existing.getFile()).text() : '[misc]\nCONTENT_WIDTH=300\n';
      if (text.includes('CONTENT_WIDTH')) text = text.replace(/^CONTENT_WIDTH=\d+$/m, `CONTENT_WIDTH=${width}`);
      return new TextEncoder().encode(text);
    })();
  }
}

function directWriteAllowed(format = $('format').value) {
  if (!directoryHandle || !library) return false;
  if (['treefrogui', 'minui', 'nextui', 'onionos', 'garlicos', 'spruceos', 'alliumos', 'anbernic', 'funkey', 'knulli'].includes(format)) return true;
  const name = directoryHandle.name.toLowerCase();
  if (selectedSystem || ['roms', 'es-de'].includes(name)) return false;
  return format !== 'muos' || (name !== 'muos' && [...files.keys()].some((path) => /^muos\//i.test(path)));
}

async function directoryAt(root, path) {
  if (slash(path).startsWith('/') || slash(path).split('/').some((part) => part === '..')) throw new Error('Unsafe artwork path.');
  let dir = root;
  for (const part of slash(path).split('/').filter(Boolean)) {
    if (part === '.' || part === '..') throw new Error('Unsafe artwork path.');
    dir = await dir.getDirectoryHandle(part);
  }
  return dir;
}

async function removeTree(dir) {
  for await (const [name, entry] of dir.entries()) {
    if (entry.kind === 'directory') await removeTree(entry);
    await dir.removeEntry(name);
  }
}

async function removeMatchingFiles(dir, endings) {
  for await (const [name, entry] of dir.entries()) {
    if (entry.kind === 'directory') await removeMatchingFiles(entry, endings);
    else if (endings.some((ending) => name.endsWith(ending))) await dir.removeEntry(name);
  }
}

async function cleanup() {
  if (!directWriteAllowed()) throw new Error('Choose a writable card folder first.');
  if (!confirm('Remove generated artwork for the selected frontend and artwork types from this folder?')) return;
  const format = $('format').value, types = [...new Set(gameTypes($('art-type').value))], removed = new Set();
  if (format === 'muos' && library.systems.some((system) => !muosNames[system.machine])) throw new Error('This library contains a system that Mini Scraper does not support in the muOS output format.');
  const mediaPath = slash($('media-path').value.trim() || 'ES-DE/downloaded_media').replace(/^\/+/, '');
  if (format === 'esde' && (mediaPath.split('/').some((part) => part === '..') || $('media-path').value.trim().startsWith('/'))) throw new Error('The ES-DE media path must stay inside the selected card.');
  const remove = async (path) => {
    if (removed.has(path)) return;
    removed.add(path);
    try { await removeTree(await directoryAt(directoryHandle, path)); }
    catch (error) { if (error.name !== 'NotFoundError') throw error; }
  };
  if (['treefrogui', 'minui', 'nextui', 'onionos', 'garlicos', 'spruceos', 'alliumos', 'anbernic'].includes(format)) {
    const media = format === 'treefrogui' || format === 'minui' ? '.res' : format === 'nextui' ? '.media' : 'Imgs';
    for (const system of library.systems) for (const game of system.games) await remove(`${dirname(game.path)}/${media}`);
  } else if (format === 'knulli') {
    const suffixes = types.map((type) => `-${({ boxart: 'box', snap: 'image', title: 'titleshot' })[type]}.png`);
    for (const system of library.systems) {
      const base = system.systemPath ? `${system.systemPath}/` : '';
      try { await removeMatchingFiles(await directoryAt(directoryHandle, `${base}images`), suffixes); }
      catch (error) { if (error.name !== 'NotFoundError') throw error; }
      const xmlPath = `${base}gamelist.xml`;
      try {
        const file = await (await directoryAt(directoryHandle, dirname(xmlPath))).getFileHandle(basename(xmlPath));
        const doc = new DOMParser().parseFromString(await (await file.getFile()).text(), 'application/xml');
        if (doc.querySelector('parsererror') || doc.documentElement.tagName !== 'gameList') throw new Error(`Invalid Knulli gamelist.xml: ${xmlPath}`);
        for (const entry of doc.querySelectorAll('game')) for (const type of types) {
          const tag = { boxart: 'boxart', snap: 'image', title: 'titleshot' }[type];
          const media = [...entry.children].find((child) => child.tagName === tag);
          if (media?.textContent?.startsWith('./images/')) media.remove();
        }
        const handle = await (await directoryAt(directoryHandle, dirname(xmlPath))).getFileHandle(basename(xmlPath), { create: true });
        const writer = await handle.createWritable(); await writer.write(`<?xml version="1.0"?>\n${new XMLSerializer().serializeToString(doc)}\n`); await writer.close();
      } catch (error) { if (error.name !== 'NotFoundError') throw error; }
    }
  } else if (format === 'muos') {
    const folders = [...new Set(types.map((type) => artFolders[type]))];
    for (const system of library.systems) for (const folder of folders) await remove(`MUOS/info/catalogue/${muosNames[system.machine]}/${folder}`);
  } else if (format === 'esde') {
    for (const system of library.systems) for (const type of types) await remove(`${mediaPath}/${esdeNames[system.machine] || system.name.toLowerCase()}/${mediaFolders[type]}`);
  } else if (format !== 'funkey') throw new Error(`Cleanup is not supported for ${format}.`);
  $('scraper-message').textContent = `Cleanup complete · processed ${removed.size} artwork folders.`;
}

async function authRetroAchievements(options) {
  const response = await request(`https://retroachievements.org/API/API_GetUserProfile.php?u=${encodeURIComponent(options.raUser)}&y=${encodeURIComponent(options.raKey)}`, {}, options);
  const profile = await response.json();
  if (!(profile.User || profile.user)) throw new Error('RetroAchievements did not accept that username and API key.');
}

async function findRA(game, machine, type, options) {
  const id = consoleIds[machine]; const romFile = await game.getFile();
  if (!id || romFile.size > 512 * 1024 * 1024 || extension(game.path) === 'm3u') return null;
  if (!raHash) {
    const { RCheevos } = await import('./scraper/rcheevos.js');
    raHash = await RCheevos.initialize();
  }
  const hash = raHash.computeHash(id, await romFile.arrayBuffer()); if (!hash) return null;
  if (!raGames.has(id)) {
    const url = `https://retroachievements.org/API/API_GetGameList.php?y=${encodeURIComponent(options.raKey)}&i=${id}&h=1&f=0`;
    raGames.set(id, request(url, {}, options).then((r) => r.json()));
  }
  const games = await raGames.get(id); const found = games.find((g) => (g.Hashes || []).some((h) => h.toLowerCase() === hash.toLowerCase()));
  if (!found) return null;
  const gameId = found.ID || found.id;
  if (!raDetails.has(gameId)) raDetails.set(gameId, request(`https://retroachievements.org/API/API_GetGameExtended.php?y=${encodeURIComponent(options.raKey)}&i=${gameId}`, {}, options).then((r) => r.json()));
  const detail = await raDetails.get(gameId);
  const image = type === 'boxart' ? detail.ImageBoxArt : type === 'snap' ? detail.ImageIngame : detail.ImageTitle;
  return image ? { url: new URL(image, 'https://retroachievements.org/').href, match: 'perfect' } : null;
}

async function getArt(game, machine, type, options) {
  if (options.source === 'retroachievements') {
    const found = await findRA(game, machine, type, options);
    if (found) return found;
  }
  return findArt(game, machine, type, options);
}

async function run() {
  if (!library?.total) return;
  const format = $('format').value;
  if (!format) throw new Error('Choose a frontend output format.');
  const width = Number($('width').value); const height = Number($('height').value) || null;
  if (!Number.isInteger(width) || width < 50 || width > 2000 || (height && (!Number.isInteger(height) || height < 50 || height > 2000))) throw new Error('Image dimensions must be between 50 and 2000 pixels.');
  const options = {
    format, width, height, source: $('source').value, force: $('force').checked, ai: $('ai').checked,
    aiUrl: $('ai-url').value.trim(), aiModel: $('ai-model').value.trim(), aiKey: $('ai-key').value,
    regions: $('regions').value, batchSize: Math.max(1, Number($('batch-size').value) || 100),
    batchDelay: Math.max(0, Number($('batch-delay').value) || 0), retries: Math.max(0, Number($('batch-retries').value) || 0),
    mediaPath: slash($('media-path').value.trim() || 'ES-DE/downloaded_media').replace(/^\/+/, ''), requestCount: 0,
    types: gameTypes($('art-type').value)
  };
  if (options.ai && (!options.aiUrl || !options.aiModel)) throw new Error('Enter an AI endpoint and model, or turn off AI matching.');
  if (format === 'muos' && library.systems.some((system) => !muosNames[system.machine])) throw new Error('This library contains a system that Mini Scraper does not support in the muOS output format.');
  if (format === 'esde' && (options.mediaPath.startsWith('/') || options.mediaPath.split('/').some((part) => part === '..'))) throw new Error('The ES-DE media path must stay inside the selected card.');
  if (options.source === 'retroachievements') {
    options.raUser = $('ra-user').value.trim(); options.raKey = $('ra-key').value;
    if (!options.raUser || !options.raKey) throw new Error('Enter your RetroAchievements username and Web API key.');
    await authRetroAchievements(options);
  }
  previewController?.abort();
  const total = library.total * options.types.length;
  const zipFiles = {}; const stats = { perfect: 0, partial: 0, ai: 0, none: 0, skipped: 0, failures: 0 }; let done = 0;
  controller = new AbortController(); $('cancel').hidden = false; $('start').disabled = true; $('progress-wrap').hidden = false; $('scraper-log').hidden = false; $('scraper-log').textContent = '';
  const log = (line) => { $('scraper-log').textContent += line + '\n'; $('scraper-log').scrollTop = $('scraper-log').scrollHeight; };
  try {
    for (const system of library.systems) {
      for (let offset = 0; offset < system.games.length; offset += 4) {
        const batch = system.games.slice(offset, offset + 4);
        await Promise.all(batch.map(async (game) => {
          controller.signal.throwIfAborted();
          const types = options.types;
          let arts = [];
          for (const type of types) {
            let result = null;
            try { result = await getArt(game, system.machine, type, options); }
            catch (error) { if (error.name === 'AbortError') throw error; stats.failures++; log(`Could not match ${game.path}: ${error.message}`); }
            if (result) arts.push({ type, result }); else stats.none++;
            done++; $('progress').value = done / total; $('progress-text').textContent = `${done} of ${total} · ${system.name} / ${basename(game.path)}`;
          }
          if (!arts.length) { log(`No artwork: ${game.path}`); return; }
          const separate = format === 'esde' || format === 'knulli';
          const outputTypes = separate ? arts : [arts[0]];
          let sourceBytes = [];
          for (const item of arts) {
            try { sourceBytes.push({ ...item, bytes: await downloadArtwork(item.result.url, options) }); }
            catch (error) { if (error.name === 'AbortError') throw error; if (error.message === 'HTTP 404') stats.none++; else stats.failures++; }
          }
          for (const item of outputTypes) {
            const art = sourceBytes.find((a) => a.type === item.type); if (!art) continue;
            const path = outputPath(game, system.machine, format, item.type, options);
            const bytes = separate ? await resize(art.bytes, width, height) : options.types.length > 1
              ? await compose(sourceBytes.find((a) => a.type === options.types[0])?.bytes, sourceBytes.find((a) => a.type === options.types[1])?.bytes, width, height || width)
              : await resize(art.bytes, width, height);
            stats[item.result.match]++;
            if (!options.force && files.has(path)) { stats.skipped++; continue; }
            zipFiles[path] = bytes;
            if (format === 'knulli') registerKnulli(game, path, item.type, options, zipFiles);
            log(`${item.result.match}: ${game.path} → ${path}`);
          }
        }));
      }
    }
    if (format === 'muos') addMuosConfig(width, zipFiles);
    const resolved = {};
    for (const [path, value] of Object.entries(zipFiles)) resolved[path] = await value;
    if (!Object.keys(resolved).length) throw new Error('No new artwork was produced. Check matching results, existing files, and retry if downloads failed.');
    if (directoryHandle && writeDirectly) await writeDirect(resolved);
    else {
      const { zipSync } = await import('./scraper/fflate.js');
      const zip = zipSync(resolved, { level: 6 });
      download(new Blob([zip], { type: 'application/zip' }), 'treefrogui-artwork.zip');
    }
    $('scraper-message').textContent = `Done · ${stats.perfect} exact, ${stats.partial} best-match, ${stats.ai} AI, ${stats.none} missing, ${stats.skipped} already present, ${stats.failures} matching or download failures.`;
  } catch (error) {
    if (error.name === 'AbortError') $('scraper-message').textContent = 'Cancelled.';
    else throw error;
  } finally { controller = null; writeDirectly = false; $('cancel').hidden = true; $('start').disabled = false; }
}

async function writeDirect(entries) {
  for (const [path, bytes] of Object.entries(entries)) {
    let dir = directoryHandle;
    const parts = slash(path).split('/');
    for (const part of parts.slice(0, -1)) dir = await dir.getDirectoryHandle(part, { create: true });
    const file = await dir.getFileHandle(parts.at(-1), { create: true });
    const writer = await file.createWritable(); await writer.write(bytes); await writer.close();
  }
}

function download(blob, filename) {
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 30000);
}

function clearPreviews() {
  for (const url of previewUrls.splice(0)) URL.revokeObjectURL(url);
  previewCount = 0;
  $('art-previews').replaceChildren();
  $('preview-count').textContent = 'Loading sample artwork…';
}

function showPreview(system, game, label, bytes) {
  previewCount++;
  if (previewCount > previewLimit) {
    $('preview-count').textContent = `Showing the first ${previewLimit} previews.`;
    return;
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
  previewUrls.push(url);
  const figure = document.createElement('figure'); figure.className = 'art-preview';
  const img = document.createElement('img'); img.src = url; img.alt = `${label} for ${stem(game.path)}`; img.loading = 'lazy';
  const caption = document.createElement('figcaption');
  const title = document.createElement('strong'); title.textContent = stem(game.path);
  caption.append(title, document.createTextNode(`${system.name} · ${label}`));
  figure.append(img, caption); $('art-previews').append(figure);
  $('preview-count').textContent = `${previewCount} preview${previewCount === 1 ? '' : 's'}`;
}

async function refreshPreviews() {
  previewController?.abort();
  previewController = new AbortController();
  const { signal } = previewController;
  const width = Number($('width').value), height = Number($('height').value) || null;
  if (!Number.isInteger(width) || width < 50 || width > 2000 || (height && (!Number.isInteger(height) || height < 50 || height > 2000))) {
    $('preview-count').textContent = 'Set valid image dimensions to preview artwork.';
    return;
  }
  const options = {
    format: $('format').value, source: $('source').value, ai: $('ai').checked, aiUrl: $('ai-url').value.trim(), aiModel: $('ai-model').value.trim(), aiKey: $('ai-key').value,
    regions: $('regions').value, retries: 0, requestCount: 0, signal,
    raUser: $('ra-user').value.trim(), raKey: $('ra-key').value,
    types: gameTypes($('art-type').value), width, height
  };
  $('preview-count').textContent = 'Finding sample artwork…';
  try {
    const sample = 'A-mazing Tater (USA)';
    const system = { name: 'Game Boy sample', machine: 'Nintendo - Game Boy' };
    const art = await Promise.all(options.types.map(async (type) => ({
      type, bytes: await downloadArtwork(rawUrl(system.machine, artTypes[type], `${sample}.png`), options)
    })));
    if (signal.aborted) return;
    clearPreviews();
    if (options.format === 'esde' || options.format === 'knulli') {
      for (const item of art) showPreview(system, { path: `${sample}.gb` }, item.type, await resize(item.bytes, width, height));
    } else showPreview(system, { path: `${sample}.gb` }, previewLabel(options.types), await previewBytes(art, options));
  } catch (error) {
    if (error.name !== 'AbortError' && !signal.aborted) $('preview-count').textContent = `Preview unavailable: ${error.message}`;
  }
}

function previewLabel(types) {
  const names = { boxart: 'Box art', snap: 'Screenshot', title: 'Title screen' };
  return types.map((type) => names[type]).join(' + ');
}

async function previewBytes(art, options) {
  if (art.length === 1) return resize(art[0].bytes, options.width, options.height);
  if (options.format === 'esde' || options.format === 'knulli') return resize(art[0].bytes, options.width, options.height);
  const first = art.find((item) => item.type === options.types[0]);
  const second = art.find((item) => item.type === options.types[1]);
  return compose(first?.bytes, second?.bytes, options.width, options.height || options.width);
}

function schedulePreviews() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => refreshPreviews(), 350);
}

async function chooseDirectory() {
  try {
    if (!window.showDirectoryPicker) {
      const input = $('folder-input');
      if (!('webkitdirectory' in input)) throw new Error('This browser cannot choose folders. Try a current version of Chrome, Edge, or Safari.');
      input.click();
      return;
    }
    directoryHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
    files = new Map(); await scanDirectory(directoryHandle);
    $('library-label').textContent = directoryHandle.name;
    renderLibrary();
    updateDirectButtons();
  } catch (error) { if (error.name !== 'AbortError') throw error; }
}

function chooseFiles(event) {
  directoryHandle = null; selectedSystem = null; $('write').hidden = true;
  $('cleanup').hidden = true;
  scanFiles(event.target.files); renderLibrary();
}

function updateDirectButtons() {
  const allowed = directWriteAllowed();
  $('write').hidden = !allowed;
  $('cleanup').hidden = !allowed;
}

function updateExtractInstructions() {
  const muos = $('format').value === 'muos';
  $('extract-title-default').hidden = muos;
  $('extract-copy-default').hidden = muos;
  $('extract-title-muos').hidden = !muos;
  $('extract-copy-muos').hidden = !muos;
}

function setMessage(error) { $('scraper-message').textContent = error instanceof Error ? error.message : String(error); }

$('choose-folder').addEventListener('click', () => chooseDirectory().catch(setMessage));
$('folder-input').addEventListener('change', (event) => { try { chooseFiles(event); } catch (e) { setMessage(e); } });
$('source').addEventListener('change', () => { $('ra-fields').hidden = $('source').value !== 'retroachievements'; });
$('format').addEventListener('change', () => { document.querySelector('.esde-setting').hidden = $('format').value !== 'esde'; updateDirectButtons(); updateExtractInstructions(); });
for (const id of ['source', 'format', 'art-type', 'width', 'height', 'ra-user', 'ra-key', 'ai', 'ai-url', 'ai-model', 'ai-key', 'regions']) $(id).addEventListener('input', schedulePreviews);
for (const id of ['source', 'format', 'art-type', 'ai']) $(id).addEventListener('change', schedulePreviews);
$('start').addEventListener('click', () => run().catch(setMessage));
$('write').addEventListener('click', () => { writeDirectly = true; run().catch(setMessage).finally(() => { writeDirectly = false; }); });
$('cleanup').addEventListener('click', () => cleanup().catch(setMessage));
$('cancel').addEventListener('click', () => controller?.abort());
updateExtractInstructions();
schedulePreviews();
