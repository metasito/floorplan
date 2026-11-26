// Unit 13 configurator: arrange, swap and recolour everything in the apartment, then render it
// with Blender Cycles through the local server. Plan coordinates are centimetres (x right, y down
// the sheet, z up); the 3D scene is metres with y up, so plan (x, y, z) sits at (x, z, y) / 100.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
}
const clone = o => JSON.parse(JSON.stringify(o));
const r1 = v => Math.round(v * 10) / 10;

// ------------------------------------------------------------------ data
const [{ catalog: CAT, default: DEFAULT }, MAN, SCENE, DIMS] = await Promise.all(
  ['assets/catalog.json', 'assets/manifest.json', 'assets/scene.json', 'assets/dims.json'].map(u => fetch(u).then(r => r.json())));
const KEY = 'unit13-config';
function loadLocal() { try { const s = localStorage.getItem(KEY); return s ? JSON.parse(s) : null; } catch { return null; } }
let saveTimer = null;
function saveLocal() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { try { localStorage.setItem(KEY, JSON.stringify(config)); } catch { /* private mode */ } }, 300);
}
let config = loadLocal() || clone(DEFAULT);

const ROOM_ORDER = ['storage', 'bath1', 'bath2', 'bed1', 'bed2', 'hall', 'living', 'bal_a', 'bal_b'];
const ROOM_NAMES = { living: 'Living and kitchen', hall: 'Hall', storage: 'Storage', bed1: 'Main bedroom', bed2: 'Bedroom two',
  bath1: 'En-suite', bath2: 'Bathroom two', bal_a: 'Balcony A', bal_b: 'Balcony B' };
function roomAt(x, y) {
  for (const k of ROOM_ORDER) { const b = SCENE.room_bounds[k]; if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) return k; }
  return 'living';
}

// ------------------------------------------------------------------ scene
const stage = $('#stage');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
stage.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#cddbe3');
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
scene.add(new THREE.HemisphereLight(0xfff6ea, 0x8f857a, 0.55));
const sun = new THREE.DirectionalLight(0xfff0d8, 2.4);
{
  const az = THREE.MathUtils.degToRad(55), el = THREE.MathUtils.degToRad(30);
  const toSun = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
  sun.target.position.set(3.7, 0, 6.2);
  sun.position.copy(sun.target.position).addScaledVector(toSun, 25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(3072, 3072);
  Object.assign(sun.shadow.camera, { left: -11, right: 11, top: 11, bottom: -11, near: 1, far: 60 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.02;
}
scene.add(sun, sun.target);
const sea = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshStandardMaterial({ color: '#3d7591', roughness: 0.3 }));
sea.rotation.x = -Math.PI / 2;
sea.position.set(3.7, -18, 6);
scene.add(sea);

const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 800);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
const tc = new TransformControls(camera, renderer.domElement);
tc.setTranslationSnap(0.01);
tc.setRotationSnap(THREE.MathUtils.degToRad(15));
tc.setSize(0.8);
scene.add(tc);
const cutPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 1.55);

// ------------------------------------------------------------------ materials
const texLoader = new THREE.TextureLoader();
const texCache = new Map();
function tex(name, meters, rot = 0) {
  const key = `${name}|${meters}|${rot}`;
  if (!texCache.has(key)) {
    const t = texLoader.load(`assets/tex/${name}.jpg`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(1 / meters, 1 / meters);
    t.rotation = rot;
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    texCache.set(key, t);
  }
  return texCache.get(key);
}
const dim = (name, fallback = 1) => (DIMS[name] ? DIMS[name][0] / 1000 : fallback);
function picTex(name) {      // an image laid once over a model exported at the reference size
  const key = `pic|${name}`;
  if (!texCache.has(key)) {
    const t = texLoader.load(`assets/tex/${name}.jpg`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.offset.set(0.5, -0.5);
    t.colorSpace = THREE.SRGBColorSpace;
    texCache.set(key, t);
  }
  return texCache.get(key);
}
const zelCache = new Map();
function zellige(hex, sizeCm) {
  const key = `${hex}|${sizeCm}`;
  if (zelCache.has(key)) return zelCache.get(key);
  const n = 8, px = 512, c = document.createElement('canvas');
  c.width = c.height = px;
  const g = c.getContext('2d');
  g.fillStyle = '#ddd6cb';
  g.fillRect(0, 0, px, px);
  const base = new THREE.Color(hex);
  let seed = 11;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const step = px / n, gap = 2;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const col = base.clone().multiplyScalar(0.9 + rnd() * 0.16);
    g.fillStyle = `#${col.getHexString()}`;
    g.fillRect(i * step + gap, j * step + gap, step - 2 * gap, step - 2 * gap);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  const m = (n * sizeCm) / 100;
  t.repeat.set(1 / m, 1 / m);
  t.colorSpace = THREE.SRGBColorSpace;
  zelCache.set(key, t);
  return t;
}

const WOOD_TEX = { 'light oak': ['oak_veneer_05', '#ffffff'], 'natural oak': ['oak_veneer_05', '#d6b089'],
  'smoked oak': ['oak_veneer_05', '#7d6450'], walnut: ['american_walnut_veneer', '#d9a982'] };
function setWood(m, name) {
  m.metalness = 0; m.roughness = 0.55;
  if (WOOD_TEX[name]) { const [t, tint] = WOOD_TEX[name]; m.map = tex(t, dim(t, 1)); m.color.set(tint); }
  else { m.map = null; m.color.set(CAT.woods[name] || '#c9a57d'); m.roughness = 0.45; }
}
function setMetal(m, name) {
  m.map = null; m.color.set(CAT.metals[name] || '#c8a66a');
  m.metalness = name === 'matt black' ? 0 : 1;
  m.roughness = { 'brushed brass': 0.32, 'matt black': 0.55, chrome: 0.08, 'brushed steel': 0.3 }[name] ?? 0.4;
}
function setFabric(m, hex) {
  m.map = null; m.color.set(hex); m.metalness = 0; m.roughness = 0.92;
  if (m.isMeshPhysicalMaterial) { m.sheen = 0.5; m.sheenColor.set(hex); m.sheenRoughness = 0.8; }
}
function setPaint(m, hex) { m.map = null; m.color.set(hex); m.metalness = 0; m.roughness = 0.7; }
function applyValue(m, type, val) {
  if (type === 'fabric') setFabric(m, val);
  else if (type === 'paint') setPaint(m, val);
  else if (type === 'wood') setWood(m, val);
  else if (type === 'metal') setMetal(m, val);
  else if (type === 'shade') { setFabric(m, val); m.emissive.set(val); m.emissiveIntensity = 0.45; m.side = THREE.DoubleSide; }
  m.needsUpdate = true;
}

const FLOORS = {
  'light oak': ['laminate_floor_02', '#fff6ea', Math.PI / 2], 'natural oak': ['laminate_floor_02', '#d9b892', Math.PI / 2],
  'oak herringbone': ['herringbone_parquet', '#ffffff', 0], 'light terrazzo': ['terrazzo_tiles', '#ffffff', 0],
  'polished concrete': ['smooth_concrete_floor', '#ffffff', 0],
};
const BATH_FLOORS = { terrazzo: 'mixed_stone_tiles', stone: 'large_grey_tiles', 'light tile': 'interior_tiles' };
const BALCONY = { terracotta: 'terracotta_floor_tiles', 'grey stone': 'large_grey_tiles', 'wood decking': 'wood_floor_worn' };
const WORKTOP = { oak: ['kitchen_wood', '#ffffff'], 'white quartz': [null, '#ece9e3'], terrazzo: ['terrazzo_tiles', '#ffffff'],
  concrete: ['brushed_concrete', '#ffffff'] };
const ROLE_PREFIX = ['wall:', 'accent:', 'tiles:', 'bathfloor:', 'fittings:', 'kitchen:', 'curtain:', 'floor:'];
const ROLE_EXACT = new Set(['ceiling', 'skirting', 'doors', 'frames', 'door_handles', 'facade']);
const roles = new Map();
function roleMat(name) {
  if (!roles.has(name)) {
    const m = new THREE.MeshPhysicalMaterial({ roughness: 0.85 });
    m.name = name;
    roles.set(name, m);
    updateRole(name, m);
  }
  return roles.get(name);
}
function texMat(m, name, tint = '#ffffff', rot = 0) {
  m.map = name ? tex(name, dim(name, 2), rot) : null; m.color.set(tint); m.metalness = 0; m.roughness = 0.7; m.needsUpdate = true;
}
function updateRole(n, m) {
  const f = config.finishes;
  const [kind, arg] = n.split(':');
  if (kind === 'wall') setPaint(m, f.walls[arg]);
  else if (kind === 'accent') {
    const own = { living_tv: 'living', bed1_head: 'bed1', bed2_band: 'bed2' }[arg];
    setPaint(m, f.accents[arg].on ? f.accents[arg].color : f.walls[own]);
  } else if (n === 'ceiling' || n === 'skirting' || n === 'doors') setPaint(m, f[n]);
  else if (n === 'frames') { setPaint(m, f.frames); m.roughness = 0.45; }
  else if (n === 'door_handles') setMetal(m, f.door_handles);
  else if (n === 'facade') setPaint(m, '#e9e4da');
  else if (kind === 'fittings') setMetal(m, f[arg].fittings);
  else if (kind === 'tiles') { m.map = zellige(f[arg].tiles, 10); m.color.set('#ffffff'); m.roughness = 0.25; m.clearcoat = 0.4; }
  else if (kind === 'bathfloor') texMat(m, BATH_FLOORS[f[arg].floor], '#ffffff');
  else if (n === 'floor:main') { const [t, tint, rot] = FLOORS[f.floor]; texMat(m, t, tint, rot); m.roughness = 0.6; }
  else if (n === 'floor:balcony') texMat(m, BALCONY[f.balconies], '#ffffff');
  else if (n === 'kitchen:fronts') { setPaint(m, f.kitchen.fronts); m.roughness = 0.55; }
  else if (n === 'kitchen:uppers') setPaint(m, f.kitchen.upper_color);
  else if (n === 'kitchen:worktop') { const [t, tint] = WORKTOP[f.kitchen.worktop]; texMat(m, t, tint); m.roughness = 0.45; }
  else if (n === 'kitchen:splash') { m.map = zellige(f.kitchen.splash, 7.5); m.color.set('#ffffff'); m.roughness = 0.25; }
  else if (n === 'kitchen:handles') {
    const hnd = f.kitchen.handles;
    if (hnd === 'oak knobs') setWood(m, 'light oak'); else setMetal(m, hnd === 'brass knobs' ? 'brushed brass' : 'matt black');
  } else if (kind === 'curtain') {
    const c = f.curtains[arg];
    setFabric(m, c.color);
    m.side = THREE.DoubleSide;
    m.transparent = c.style === 'sheer';
    m.opacity = c.style === 'sheer' ? 0.6 : 1;
    m.depthWrite = c.style !== 'sheer';
  }
  m.needsUpdate = true;
}
function updateRoles() { for (const [n, m] of roles) updateRole(n, m); }

const fixed = new Map();
function fixedMat(name, make) { if (!fixed.has(name)) { const m = make(); m.name = name; fixed.set(name, m); } return fixed.get(name); }
const FIXED = {
  oak: () => fixedMat('oak', () => { const m = new THREE.MeshStandardMaterial(); setWood(m, 'light oak'); return m; }),
  'oak smoked': () => fixedMat('oak smoked', () => { const m = new THREE.MeshStandardMaterial(); setWood(m, 'smoked oak'); return m; }),
  glass: () => fixedMat('glass', () => new THREE.MeshPhysicalMaterial({ color: '#dfe9ec', transparent: true, opacity: 0.12, roughness: 0.02, metalness: 0, depthWrite: false })),
  'clear glass': () => fixedMat('clear glass', () => new THREE.MeshPhysicalMaterial({ color: '#e6efee', transparent: true, opacity: 0.1, roughness: 0.02, depthWrite: false })),
  'frosted glass': () => fixedMat('frosted glass', () => new THREE.MeshStandardMaterial({ color: '#f2f4f4', transparent: true, opacity: 0.75, roughness: 0.4 })),
  mirror: () => fixedMat('mirror', () => new THREE.MeshStandardMaterial({ color: '#e9eef0', metalness: 1, roughness: 0.04 })),
  'linen shade': () => fixedMat('linen shade', () => new THREE.MeshStandardMaterial({ color: '#efe4d2', emissive: '#f3d9b5', emissiveIntensity: 0.4, side: THREE.DoubleSide })),
  'paper shade': () => fixedMat('paper shade', () => new THREE.MeshStandardMaterial({ color: '#f3ece0', emissive: '#f6dfbf', emissiveIntensity: 0.5 })),
  rattan: () => fixedMat('rattan', () => new THREE.MeshStandardMaterial({ color: '#b8894f', roughness: 0.6 })),
  cane: () => fixedMat('cane', () => new THREE.MeshStandardMaterial({ color: '#b9935f', roughness: 0.6 })),
  'tv screen': () => fixedMat('tv screen', () => new THREE.MeshStandardMaterial({ color: '#0a0a0b', roughness: 0.1 })),
  lens: () => fixedMat('lens', () => new THREE.MeshStandardMaterial({ color: '#fff', emissive: '#fff1dc', emissiveIntensity: 1.2 })),
  bulb: () => fixedMat('bulb', () => new THREE.MeshStandardMaterial({ color: '#fff', emissive: '#ffd9a8', emissiveIntensity: 1.5 })),
  'led strip': () => fixedMat('led strip', () => new THREE.MeshStandardMaterial({ color: '#fff', emissive: '#ffdcb0', emissiveIntensity: 1.2 })),
  jute: () => fixedMat('jute', () => { const m = new THREE.MeshStandardMaterial({ roughness: 1 }); m.map = tex('hessian_230', 0.14); m.color.set('#d9c09a'); return m; }),
};
const FABRIC_NAMES = { 'white linen': '#efeae1', 'oatmeal linen': '#d9ccb6', 'rust linen': '#a85f3d', 'sage linen': '#9aa58d',
  'ochre linen': '#c99540', 'oatmeal sofa linen': '#ddd3c2', 'terry towel': '#e9e1d3', 'clay towel': '#c88e70',
  'terracotta waffle': '#c27850', 'sage waffle': '#9fac92', 'waffle cotton': '#efe8dc', 'paper cord': '#d8c39c',
  'cream teddy': '#e9e1d4' };
for (const [n, hex] of Object.entries(FABRIC_NAMES)) FIXED[n] = () => fixedMat(n, () => { const m = new THREE.MeshStandardMaterial(); setFabric(m, hex); return m; });

const base = n => (n || '').replace(/\.\d+$/, '');
function resolveMat(m, rec) {
  const n = base(m.name);
  if (n.startsWith('slot:')) return rec ? slotMat(rec, n.slice(5)) : m;
  if (n.startsWith('rug:')) return rec ? rugMat(rec, n.slice(4)) : m;
  if (ROLE_EXACT.has(n) || ROLE_PREFIX.some(p => n.startsWith(p))) return roleMat(n);
  if (FIXED[n]) return FIXED[n]();
  return m;
}
function slotMat(rec, slot) {
  if (!rec.slotMats[slot]) { rec.slotMats[slot] = new THREE.MeshPhysicalMaterial(); setSlot(rec, slot); }
  return rec.slotMats[slot];
}
function setSlot(rec, slot) {
  const m = rec.slotMats[slot];
  if (!m) return;
  const spec = CAT.kinds[rec.item.kind].slots[slot];
  const val = (rec.item.slots || {})[slot] ?? spec?.default ?? '#efe4d2';
  applyValue(m, slot === 'shade' ? 'shade' : (spec?.type || 'fabric'), val);
}
const RUG_KEY = { jute: 'jute', berber: 'berber', stripes: 'stripes', 'plain wool': 'wool' };
function rugMat(rec, v) {
  if (!rec.slotMats._rug) rec.slotMats._rug = new THREE.MeshStandardMaterial({ roughness: 1 });
  const m = rec.slotMats._rug;
  if (v === 'jute') { m.map = tex('hessian_230', 0.14); m.color.set('#d9c09a'); }
  else if (v === 'berber') { m.map = picTex('rug_berber'); m.color.set('#ffffff'); }
  else if (v === 'stripes') { m.map = picTex('rug_stripes'); m.color.set('#ffffff'); }
  else { m.map = null; m.color.set((rec.item.slots || {}).fabric || '#efeae1'); }
  m.needsUpdate = true;
  return m;
}

// ------------------------------------------------------------------ models
const loader = new GLTFLoader();
const gltfCache = new Map();
async function fetchModel(file, tries = 3) {
  for (let i = 0; ; i++) {
    try { return (await loader.loadAsync(`assets/models/${file}`)).scene; }
    catch (e) { if (i >= tries - 1) throw e; await new Promise(r => setTimeout(r, 400 * (i + 1))); }
  }
}
function loadModel(file) {
  if (!gltfCache.has(file)) {
    const p = fetchModel(file);
    p.catch(() => gltfCache.delete(file));
    gltfCache.set(file, p);
  }
  return gltfCache.get(file).then(s => s.clone(true));
}
function prep(root, rec) {
  root.traverse(o => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    o.material = Array.isArray(o.material) ? o.material.map(m => resolveMat(m, rec)) : resolveMat(o.material, rec);
  });
}

let shellRoot, kitchenRoot, ceiling;
const curtainRoots = {};
async function loadShell() {
  shellRoot = await loadModel(MAN.shell);
  prep(shellRoot, null);
  ceiling = shellRoot.getObjectByName('ceiling');
  scene.add(shellRoot);
}
async function loadKitchen() {
  const k = config.finishes.kitchen;
  const next = await loadModel(MAN.kitchen[`${k.uppers}|${k.handles}`]);
  prep(next, null);
  if (kitchenRoot) scene.remove(kitchenRoot);
  kitchenRoot = next;
  scene.add(kitchenRoot);
}
async function loadCurtains() {
  for (const [w, file] of Object.entries(MAN.curtains)) {
    if (!curtainRoots[w]) { curtainRoots[w] = await loadModel(file); prep(curtainRoots[w], null); scene.add(curtainRoots[w]); }
    curtainRoots[w].visible = config.finishes.curtains[w].on;
  }
}

const recs = new Map();
function newId() { return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); }
async function spawn(item) {
  if (!MAN.items[item.kind]?.[item.variant]) return null;
  const rec = { item, root: new THREE.Group(), model: null, slotMats: {} };
  rec.root.userData.itemId = item.id;
  recs.set(item.id, rec);
  scene.add(rec.root);
  try { await setModel(rec); } catch (e) { removeRec(rec); console.warn('could not load', item.kind, item.variant, e); return null; }
  return rec;
}
async function setModel(rec) {
  const model = await loadModel(MAN.items[rec.item.kind][rec.item.variant]);
  if (!recs.has(rec.item.id)) return;          // removed while loading
  rec.slotMats = {};
  prep(model, rec);
  if (rec.model) rec.root.remove(rec.model);
  rec.model = model;
  rec.root.add(model);
  place(rec);
  if (selected === rec) refreshSelectionBox();
}
function place(rec) {
  const it = rec.item, k = it.kind;
  const z = k === 'pendant' ? (it.z ?? 160) - MAN.ref_z.pendant : (it.z ?? 0);
  rec.root.position.set(it.x / 100, z / 100, it.y / 100);
  rec.root.rotation.set(0, THREE.MathUtils.degToRad(it.rot || 0), 0);
  if (!rec.model) return;
  const ref = MAN.ref_size[k], s = it.size || CAT.kinds[k].size;
  rec.model.scale.set(1, 1, 1);
  if (ref && s) {
    if (k === 'rug' || k === 'cistern_wall') rec.model.scale.set(s[0] / ref[0], 1, s[1] / ref[1]);
    else if (k === 'art') rec.model.scale.set(s[0] / ref[0], s[1] / ref[1], 1);
    else { const u = s[1] / ref[1]; rec.model.scale.set(u, u, u); }
  }
}
function removeRec(rec) { scene.remove(rec.root); recs.delete(rec.item.id); }
async function rebuildItems() {
  select(null);
  for (const rec of [...recs.values()]) removeRec(rec);
  await Promise.all(config.items.map(spawn));
}

// ------------------------------------------------------------------ undo
const undoStack = [];
function snapshot() { undoStack.push(JSON.stringify(config)); if (undoStack.length > 80) undoStack.shift(); }
async function undo() {
  const s = undoStack.pop();
  if (!s) { toast('Nothing to undo'); return; }
  config = JSON.parse(s);
  updateRoles();
  await Promise.all([loadKitchen(), loadCurtains(), rebuildItems()]);
  buildFinishes();
  buildPlaced();
  saveLocal();
}
$('#undo').addEventListener('click', undo);

// ------------------------------------------------------------------ selection and moving
let selected = null;
const selBox = new THREE.Box3Helper(new THREE.Box3(), new THREE.Color('#c8a66a'));
selBox.visible = false;
scene.add(selBox);
function refreshSelectionBox() {
  if (!selected) { selBox.visible = false; return; }
  selBox.box.setFromObject(selected.root);
  selBox.visible = true;
}
let tcMode = 'translate';
let dragging = false;
function select(id) {
  selected = id ? recs.get(id) || null : null;
  if (selected) {
    const mount = CAT.kinds[selected.item.kind].mount;
    tc.attach(selected.root);
    tc.setMode(tcMode);
    if (tcMode === 'rotate') { tc.showX = tc.showZ = false; tc.showY = true; }
    else { tc.showX = tc.showZ = true; tc.showY = mount !== 'floor'; }
  } else tc.detach();
  refreshSelectionBox();
  buildInspector();
}
tc.addEventListener('mouseDown', () => { snapshot(); dragging = true; });
tc.addEventListener('dragging-changed', e => { controls.enabled = !e.value; if (!e.value) { dragging = false; commitTransform(); } });
tc.addEventListener('objectChange', () => { refreshSelectionBox(); if (selected) liveFields(); });
function commitTransform() {
  if (!selected) return;
  const it = selected.item, p = selected.root.position;
  it.x = r1(p.x * 100); it.y = r1(p.z * 100);
  const z = p.y * 100;
  it.z = r1(it.kind === 'pendant' ? z + MAN.ref_z.pendant : z);
  it.rot = Math.round(THREE.MathUtils.radToDeg(selected.root.rotation.y));
  it.room = roomAt(it.x, it.y);
  saveLocal();
  buildInspector();
  buildPlaced();
}

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let down = null;
function rayFrom(e) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
}
function hitsVisible(objs) {
  const cut = renderer.clippingPlanes.length > 0;
  return raycaster.intersectObjects(objs, true).filter(hh => {
    let o = hh.object, vis = true;
    while (o) { if (!o.visible) vis = false; o = o.parent; }
    const m = Array.isArray(hh.object.material) ? hh.object.material[0] : hh.object.material;
    const seeThrough = m && m.transparent && m.opacity < 0.7;          // glass and sheers don't block a click
    return vis && !seeThrough && (!cut || hh.point.y <= cutPlane.constant);
  });
}
renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!down) return;
  const moved = Math.hypot(e.clientX - down[0], e.clientY - down[1]);
  down = null;
  if (moved > 4 || dragging) return;
  rayFrom(e);
  const objs = [...recs.values()].map(r => r.root);
  if (shellRoot) objs.push(shellRoot);
  if (kitchenRoot) objs.push(kitchenRoot);
  const hit = hitsVisible(objs)[0];
  let o = hit?.object;
  while (o && !o.userData.itemId) o = o.parent;
  select(o?.userData.itemId || null);
});
renderer.domElement.addEventListener('dblclick', e => {
  if (view !== 'walk') return;
  rayFrom(e);
  const p = new THREE.Vector3();
  if (raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p)) {
    const dir = controls.target.clone().sub(camera.position);
    camera.position.set(p.x, eye, p.z);
    controls.target.copy(camera.position).add(dir);
  }
});

// ------------------------------------------------------------------ views
let view = 'orbit', eye = 1.25, lens = 30;
const keys = new Set();
function setView(mode, preset) {
  view = mode;
  $$('.views button').forEach(b => b.classList.toggle('on', b.dataset.view === mode));
  controls.enableRotate = mode !== 'top';
  controls.enablePan = mode !== 'walk';
  controls.enableZoom = mode !== 'walk';
  controls.rotateSpeed = mode === 'walk' ? 0.45 : 1;
  controls.minPolarAngle = mode === 'walk' ? 0.25 : 0;
  controls.maxPolarAngle = mode === 'walk' ? Math.PI - 0.25 : Math.PI * 0.49;
  if (mode === 'orbit') {
    lens = 30;
    camera.position.set(13.5, 13, 19.5);
    controls.target.set(3.7, 0, 6.2);
  } else if (mode === 'top') {
    lens = 30;
    camera.position.set(3.7, 27, 6.21);
    controls.target.set(3.7, 0, 6.2);
  } else {
    lens = 20;
    const p = preset || { cam: [108, 372, 120], look: [600, 60, 110] };
    eye = p.cam[2] / 100;
    camera.position.set(p.cam[0] / 100, p.cam[2] / 100, p.cam[1] / 100);
    const t = new THREE.Vector3(p.look[0] / 100, p.look[2] / 100, p.look[1] / 100);
    controls.target.copy(camera.position).add(t.sub(camera.position).normalize().multiplyScalar(0.02));
  }
  if (ceiling) ceiling.visible = mode === 'walk';
  applyCut();
  const ls = $('#lens');
  if (ls) { ls.value = lens; $('#lens-val').textContent = `${lens} mm`; }
  $('#hint').textContent = mode === 'walk'
    ? 'Drag to look around. W A S D to walk, double-click the floor to step there.'
    : 'Click a piece to select it. Drag the arrows to move it.';
  resize();
}
function applyCut() { renderer.clippingPlanes = view !== 'walk' && $('#cut').checked ? [cutPlane] : []; }
$('#cut').addEventListener('change', applyCut);
$$('.views button').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));

function resize() {
  const W = stage.clientWidth, H = stage.clientHeight;
  if (!W || !H) return;
  renderer.setSize(W, H, false);
  const fw = Math.min(W - 24, (H - 24) * 1.5), fh = fw / 1.5;
  const fr = $('#frame');
  Object.assign(fr.style, { left: `${(W - fw) / 2}px`, top: `${(H - fh) / 2}px`, width: `${fw}px`, height: `${fh}px` });
  fr.hidden = view === 'top';
  const hfov = 2 * Math.atan(18 / lens);
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(hfov / 2) * H / fw));
  camera.aspect = W / H;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);

addEventListener('keydown', e => {
  if (e.target.closest('input, select, textarea')) return;
  const k = e.key.toLowerCase();
  if ((e.metaKey || e.ctrlKey) && k === 'z') { e.preventDefault(); undo(); return; }
  if ((e.metaKey || e.ctrlKey) && k === 'd') { e.preventDefault(); duplicate(); return; }
  if (view === 'walk' && ['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) { keys.add(k); e.preventDefault(); return; }
  if (!selected) return;
  if (k === 'delete' || k === 'backspace') { e.preventDefault(); removeSelected(); }
  else if (k === 'r') turn(e.shiftKey ? -90 : 90);
  else if (k === 'escape') select(null);
});
addEventListener('keyup', e => keys.delete(e.key.toLowerCase()));

const clock = new THREE.Clock();
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (view === 'walk' && keys.size) {
    const fwd = controls.target.clone().sub(camera.position).setY(0).normalize();
    const right = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0));
    const mv = new THREE.Vector3();
    if (keys.has('w') || keys.has('arrowup')) mv.add(fwd);
    if (keys.has('s') || keys.has('arrowdown')) mv.sub(fwd);
    if (keys.has('d') || keys.has('arrowright')) mv.add(right);
    if (keys.has('a') || keys.has('arrowleft')) mv.sub(right);
    mv.normalize().multiplyScalar(1.6 * dt);
    camera.position.add(mv);
    controls.target.add(mv);
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

// ------------------------------------------------------------------ editing actions
function viewPoint() {
  if (view === 'walk') {
    const dir = controls.target.clone().sub(camera.position).setY(0).normalize();
    const p = camera.position.clone().addScaledVector(dir, 1.6);
    return { x: p.x * 100, y: p.z * 100 };
  }
  return { x: controls.target.x * 100, y: controls.target.z * 100 };
}
async function addItem(kind) {
  snapshot();
  const spec = CAT.kinds[kind];
  const p = viewPoint();
  const room = roomAt(p.x, p.y);
  const it = { id: newId(), kind, variant: spec.variants[0], x: r1(p.x), y: r1(p.y), rot: 0, z: spec.z || 0, room };
  if (room.startsWith('bal') && spec.mount === 'floor') it.z = -2;
  if (spec.size) it.size = [...spec.size];
  if (kind === 'plant') it.size = [0, 80];
  if (kind === 'rug') it.size = [160, 230];
  config.items.push(it);
  const rec = await spawn(it);
  select(rec ? it.id : null);
  buildPlaced();
  saveLocal();
  toast(`${spec.label} added: drag it into place`);
}
async function duplicate() {
  if (!selected) return;
  snapshot();
  const it = clone(selected.item);
  it.id = newId(); it.x = r1(it.x + 30); it.y = r1(it.y + 30);
  config.items.push(it);
  await spawn(it);
  select(it.id);
  buildPlaced();
  saveLocal();
}
function removeSelected() {
  if (!selected) return;
  snapshot();
  const id = selected.item.id;
  removeRec(selected);
  config.items = config.items.filter(i => i.id !== id);
  select(null);
  buildPlaced();
  saveLocal();
}
function turn(deg) {
  if (!selected) return;
  snapshot();
  selected.item.rot = ((selected.item.rot || 0) + deg + 540) % 360 - 180;
  place(selected);
  refreshSelectionBox();
  buildInspector();
  saveLocal();
}
function focusItem(rec) {
  const p = rec.root.position;
  if (view === 'walk') setView('orbit');
  controls.target.set(p.x, 0, p.z);
  camera.position.set(p.x + 4.5, 6.5, p.z + 6.5);
}

// ------------------------------------------------------------------ UI pieces
let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}
function field(label, control) { return h('label', { class: 'field' }, h('span', {}, label), control); }
function select_(options, value, onchange, labels = null) {
  return h('select', { onchange: e => onchange(e.target.value) },
    options.map((o, i) => h('option', { value: o, selected: o === value }, labels ? labels[i] : o)));
}
function colorPicker(value, palette, onpick) {
  const wrap = h('div', { class: 'swatches' });
  const input = h('input', { type: 'color', value, title: 'Any colour' });
  const mark = v => $$('.sw', wrap).forEach(b => b.classList.toggle('on', b.dataset.v.toLowerCase() === v.toLowerCase()));
  for (const c of palette) {
    wrap.append(h('button', { type: 'button', class: 'sw', 'data-v': c, title: c, style: `background:${c}`,
      onclick: () => { onpick(c, true); input.value = c; mark(c); } }));
  }
  input.addEventListener('focus', () => snapshot());
  input.addEventListener('input', e => { onpick(e.target.value, false); mark(e.target.value); });
  wrap.append(input);
  mark(value);
  return wrap;
}
function num(value, onchange, step = 1) {
  const i = h('input', { type: 'number', value, step });
  i.addEventListener('change', e => { const v = parseFloat(e.target.value); if (!Number.isNaN(v)) onchange(v); });
  return i;
}

// furniture tab
function buildFurniture() {
  const tab = $('#tab-furniture');
  tab.replaceChildren();
  tab.append(h('p', { class: 'note' }, 'Add a piece and it appears where you are looking. Click any piece in the model to move, turn, swap or recolour it.'));
  for (const cat of CAT.categories) {
    const kinds = Object.entries(CAT.kinds).filter(([, v]) => v.cat === cat);
    if (!kinds.length) continue;
    tab.append(h('h2', {}, cat), h('div', { class: 'cat-list' },
      kinds.map(([k, v]) => h('button', { type: 'button', class: 'add', onclick: () => addItem(k) },
        h('span', {}, v.label), h('small', {}, `${v.variants.length} option${v.variants.length > 1 ? 's' : ''}`)))));
  }
  tab.append(h('h2', {}, 'In the apartment'), h('div', { id: 'placed', class: 'field' }));
  buildPlaced();
}
function buildPlaced() {
  const box = $('#placed');
  if (!box) return;
  const open = new Set($$('details[open] > summary', box).map(s => s.dataset.room));
  box.replaceChildren();
  const by = {};
  for (const it of config.items) (by[it.room || roomAt(it.x, it.y)] ||= []).push(it);
  for (const room of Object.keys(ROOM_NAMES)) {
    if (!by[room]) continue;
    box.append(h('details', { open: open.has(room) }, h('summary', { 'data-room': room }, `${ROOM_NAMES[room]} (${by[room].length})`),
      h('div', { class: 'body' }, by[room].map(it => h('button', { type: 'button', class: 'add',
        onclick: () => { const rec = recs.get(it.id); if (rec) { select(it.id); focusItem(rec); } } },
        h('span', {}, CAT.kinds[it.kind].label), h('small', {}, it.variant))))));
  }
}

// inspector
function buildInspector() {
  const ins = $('#inspector');
  if (!selected) { ins.hidden = true; ins.replaceChildren(); requestAnimationFrame(resize); return; }
  const wasHidden = ins.hidden;
  ins.hidden = false;
  const it = selected.item, spec = CAT.kinds[it.kind];
  const update = () => { place(selected); refreshSelectionBox(); saveLocal(); };
  const els = [h('h3', {}, spec.label), h('p', { class: 'note' }, ROOM_NAMES[it.room || roomAt(it.x, it.y)] || '')];
  if (spec.variants.length > 1) {
    els.push(field('Model', select_(spec.variants, it.variant, async v => {
      snapshot(); it.variant = v; await setModel(selected); saveLocal(); buildPlaced();
    })));
  }
  for (const [slot, s] of Object.entries(spec.slots)) {
    const val = (it.slots || {})[slot] ?? s.default;
    const set = (v, snap) => {
      if (snap) snapshot();
      it.slots = { ...(it.slots || {}), [slot]: v };
      setSlot(selected, slot);
      if (it.kind === 'rug' && slot === 'fabric') rugMat(selected, RUG_KEY[it.variant]);
      saveLocal();
    };
    const label = slot[0].toUpperCase() + slot.slice(1);
    if (s.type === 'wood' || s.type === 'metal') {
      els.push(field(label, select_(Object.keys(s.type === 'wood' ? CAT.woods : CAT.metals), val, v => set(v, true))));
    } else {
      els.push(field(label, colorPicker(val, s.type === 'paint' ? CAT.palettes.paint : CAT.palettes.fabric, set)));
    }
  }
  const sz = it.size || spec.size;
  if (sz) {
    const resize_ = (i, v) => { snapshot(); it.size = [...(it.size || spec.size)]; it.size[i] = v; update(); };
    if (sz[0]) {
      els.push(h('div', { class: 'row' }, field('Width, cm', num(sz[0], v => resize_(0, v))),
        field(it.kind === 'art' ? 'Height, cm' : 'Depth, cm', num(sz[1], v => resize_(1, v)))));
    } else {
      els.push(field('Height, cm', num(sz[1], v => resize_(1, v))));
    }
  }
  els.push(h('div', { class: 'row' },
    field('Across, cm', num(it.x, v => { snapshot(); it.x = v; update(); })),
    field('Down, cm', num(it.y, v => { snapshot(); it.y = v; update(); }))));
  els.push(h('div', { class: 'row' },
    field(spec.mount === 'ceiling' ? 'Bottom at, cm' : 'Off the floor, cm', num(it.z ?? 0, v => { snapshot(); it.z = v; update(); })),
    field('Turn, degrees', num(it.rot || 0, v => { snapshot(); it.rot = v; update(); }, 15))));
  els.push(h('div', { class: 'btns' },
    h('button', { type: 'button', class: 'btn', onclick: () => { tcMode = tcMode === 'translate' ? 'rotate' : 'translate'; select(it.id); } },
      tcMode === 'translate' ? 'Turn with handle' : 'Move with arrows'),
    h('button', { type: 'button', class: 'btn', onclick: () => turn(90) }, 'Turn 90°'),
    h('button', { type: 'button', class: 'btn', onclick: duplicate }, 'Duplicate'),
    h('button', { type: 'button', class: 'btn danger', onclick: removeSelected }, 'Delete')));
  els.push(h('p', { class: 'note' }, 'Keys: R turns 90°, Delete removes, Cmd/Ctrl+D duplicates, Cmd/Ctrl+Z undoes, Esc deselects.'));
  ins.replaceChildren(...els);
  if (wasHidden) requestAnimationFrame(resize);
}
function liveFields() {
  const p = selected.root.position;
  const vals = { 'Across, cm': r1(p.x * 100), 'Down, cm': r1(p.z * 100) };
  $$('#inspector .field').forEach(f => { const l = f.querySelector('span')?.textContent; const i = f.querySelector('input'); if (i && l in vals) i.value = vals[l]; });
}

// finishes tab
function buildFinishes() {
  const f = config.finishes;
  const tab = $('#tab-finishes');
  const open = new Set($$('details[open] > summary', tab).map(s => s.textContent));
  tab.replaceChildren();
  const set = (fn, kitchen = false) => async (v, snap = true) => {
    if (snap) snapshot();
    fn(v);
    updateRoles();
    if (kitchen) await loadKitchen();
    await loadCurtains();
    saveLocal();
  };
  const group = (title, def, ...kids) => h('details', { open: open.size ? open.has(title) : def }, h('summary', {}, title), h('div', { class: 'body' }, kids));
  tab.append(h('p', { class: 'note' }, 'Changes show in the model straight away and go into every render.'));
  tab.append(group('Floors', true,
    field('Living, hall and bedrooms', select_(CAT.floors, f.floor, set(v => { f.floor = v; }))),
    field('Balconies', select_(CAT.balcony_floors, f.balconies, set(v => { f.balconies = v; })))));
  tab.append(group('Wall colours', true,
    ...Object.entries(ROOM_NAMES).filter(([k]) => f.walls[k]).map(([k, name]) =>
      field(name, colorPicker(f.walls[k], CAT.palettes.paint, set(v => { f.walls[k] = v; }))))));
  const acc = { living_tv: 'Living room, TV wall', bed1_head: 'Main bedroom, behind the bed', bed2_band: 'Bedroom two, lower band' };
  tab.append(group('Accent walls', false, ...Object.entries(acc).map(([k, name]) => h('div', { class: 'field' },
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: f.accents[k].on,
      onchange: e => set(v => { f.accents[k].on = v; })(e.target.checked) }), name),
    colorPicker(f.accents[k].color, CAT.palettes.paint, set(v => { f.accents[k].color = v; }))))));
  const k = f.kitchen;
  tab.append(group('Kitchen', false,
    field('Lower fronts', colorPicker(k.fronts, CAT.palettes.paint, set(v => { k.fronts = v; }))),
    field('Wall units', select_(CAT.uppers, k.uppers, set(v => { k.uppers = v; }, true))),
    field('Wall unit colour', colorPicker(k.upper_color, CAT.palettes.paint, set(v => { k.upper_color = v; }))),
    field('Worktop', select_(CAT.worktops, k.worktop, set(v => { k.worktop = v; }))),
    field('Splashback tiles', colorPicker(k.splash, CAT.palettes.tile, set(v => { k.splash = v; }))),
    field('Handles', select_(CAT.handles, k.handles, set(v => { k.handles = v; }, true)))));
  for (const [b, name] of [['bath1', 'En-suite'], ['bath2', 'Bathroom two']]) {
    tab.append(group(name, false,
      field('Wall tiles', colorPicker(f[b].tiles, CAT.palettes.tile, set(v => { f[b].tiles = v; }))),
      field('Floor', select_(CAT.bath_floors, f[b].floor, set(v => { f[b].floor = v; }))),
      field('Taps and shower', select_(Object.keys(CAT.metals), f[b].fittings, set(v => { f[b].fittings = v; })))));
  }
  tab.append(group('Doors, trim and ceiling', false,
    field('Doors', colorPicker(f.doors, CAT.palettes.paint, set(v => { f.doors = v; }))),
    field('Door handles', select_(Object.keys(CAT.metals), f.door_handles, set(v => { f.door_handles = v; }))),
    field('Skirting', colorPicker(f.skirting, CAT.palettes.paint, set(v => { f.skirting = v; }))),
    field('Ceiling', colorPicker(f.ceiling, CAT.palettes.paint, set(v => { f.ceiling = v; }))),
    field('Window frames', colorPicker(f.frames, ['#3c3f42', '#1f1f1f', '#ece8e0', '#8b7e6e', '#5f6a5a'], set(v => { f.frames = v; })))));
  const wn = { W1: 'Balcony doors, living room', W2: 'Living room window', W3: 'Main bedroom window', W5: 'Bedroom two, balcony door' };
  tab.append(group('Curtains', false, ...Object.entries(wn).map(([w, name]) => {
    const c = f.curtains[w];
    return h('div', { class: 'field' },
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: c.on, onchange: e => set(v => { c.on = v; })(e.target.checked) }), name),
      select_(['sheer', 'linen'], c.style, set(v => { c.style = v; })),
      colorPicker(c.color, CAT.palettes.fabric, set(v => { c.color = v; })));
  })));
}

// render tab
const PRESETS = {
  'Living room, toward the sea': { cam: [108, 372, 116], look: [600, 60, 108] },
  'Living room, from the window': { cam: [694, 336, 120], look: [170, 10, 112] },
  'Kitchen and dining': { cam: [405, 115, 120], look: [0, 470, 110] },
  'Hall, from the front door': { cam: [252, 1300, 140], look: [252, 0, 130] },
  'Main bedroom': { cam: [705, 742, 140], look: [420, 430, 112] },
  'Bedroom two': { cam: [345, 1250, 130], look: [610, 1110, 112] },
  'En-suite': { cam: [372, 806, 150], look: [612, 905, 112] },
  'Bathroom two': { cam: [168, 905, 150], look: [30, 1070, 108] },
  'Balcony A': { cam: [40, -125, 138], look: [700, -40, 110] },
  'Balcony B': { cam: [742, 1350, 140], look: [690, 800, 112] },
};
const QUALITY = { preview: 'Preview, 1200 px, about 1 min', standard: 'Standard, 2100 px, about 6 min',
  final: 'Final, 3000 px, about 15 min', 360: '360° panorama, about 12 min' };
function buildRender() {
  const tab = $('#tab-render');
  const mood = select_(CAT.moods, 'day', () => {}, ['Day, sun through the windows', 'Dusk, lamps on', 'Golden hour']);
  mood.id = 'mood';
  const quality = select_(Object.keys(QUALITY), 'preview', () => {}, Object.values(QUALITY));
  quality.id = 'quality';
  tab.replaceChildren(
    h('p', { class: 'note' }, 'Frame the shot inside the white rectangle, then render it in Blender Cycles. Walk view gives interior photos; 3D view gives a cut-away of the whole flat.'),
    field('Jump to a view', select_(['', ...Object.keys(PRESETS)], '', v => { if (v) setView('walk', PRESETS[v]); },
      ['Choose a room…', ...Object.keys(PRESETS)])),
    field('Lens', h('div', { class: 'row' }, h('input', { type: 'range', id: 'lens', min: 14, max: 50, step: 1, value: lens,
      oninput: e => { lens = +e.target.value; $('#lens-val').textContent = `${lens} mm`; resize(); } }), h('span', { id: 'lens-val', class: 'mono' }, `${lens} mm`))),
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', id: 'level', checked: true }), 'Keep verticals straight'),
    field('Light', mood),
    field('Quality', quality),
    field('Name (optional)', h('input', { type: 'text', id: 'render-label', placeholder: 'e.g. walnut table, sage kitchen' })),
    h('button', { type: 'button', class: 'btn primary', onclick: requestRender }, 'Render this view'),
    h('h2', {}, 'Renders'), h('div', { class: 'jobs', id: 'jobs' }, h('p', { class: 'note' }, 'Your renders appear here.')));
}
async function requestRender() {
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  const p = camera.position, t = p.clone().addScaledVector(dir, 3);
  const body = {
    config, mood: $('#mood').value, quality: $('#quality').value, label: $('#render-label').value,
    camera: { pos: [p.x * 100, p.z * 100, p.y * 100], target: [t.x * 100, t.z * 100, t.y * 100], lens,
      level: view === 'walk' && $('#level').checked },
  };
  try {
    const r = await fetch('api/render', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(await r.text());
    toast('Render queued: it appears under Renders');
    jobsSig = '';
    pollJobs();
  } catch {
    toast('Could not reach the render server. Is server.py running?');
  }
}
let jobsSig = '';
async function pollJobs() {
  let jobs;
  try { jobs = await (await fetch('api/jobs')).json(); } catch { return; }
  const sig = JSON.stringify(jobs.map(j => [j.id, j.status, j.progress, j.stage]));
  const box = $('#jobs');
  if (sig === jobsSig || !box || !jobs.length) return;
  jobsSig = sig;
  const cancel = id => fetch('api/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }).then(() => { jobsSig = ''; pollJobs(); });
  box.replaceChildren(...jobs.map(j => h('div', { class: 'job' },
    j.status === 'done' ? h('img', { src: `${j.thumb}?v=${j.id}`, alt: j.label || 'render', onclick: () => openImage(j) }) : null,
    h('div', { class: 'meta' },
      h('div', { class: 'row' }, h('b', {}, j.label || `${j.quality}, ${j.mood}`), h('span', { class: 'muted mono' }, j.id.slice(5, 11).replace(/(..)(..)(..)/, '$1:$2:$3'))),
      j.status === 'done' ? h('span', { class: 'muted' }, `${j.quality}, ${j.mood}, ${Math.max(1, Math.round((j.seconds || 0) / 60))} min`)
        : h('span', { class: 'muted' }, `${j.status}: ${j.stage}`),
      ['queued', 'running'].includes(j.status) ? h('div', { class: 'progress' }, h('i', { style: `width:${Math.round((j.progress || 0) * 100)}%` })) : null,
      ['queued', 'running'].includes(j.status) ? h('button', { type: 'button', class: 'btn', onclick: () => cancel(j.id) }, 'Cancel') : null))));
}
setInterval(pollJobs, 2500);
function openImage(j) {
  let d = $('#viewer');
  if (!d) { d = h('dialog', { id: 'viewer' }); document.body.append(d); d.addEventListener('click', e => { if (e.target === d) d.close(); }); }
  d.replaceChildren(h('img', { src: j.image, alt: j.label || 'render' }),
    h('div', { class: 'row' }, h('a', { href: j.image, target: '_blank' }, 'Open full size'), h('button', { type: 'button', class: 'btn', onclick: () => d.close() }, 'Close')));
  d.showModal();
}

// layouts tab
async function buildLayouts() {
  const tab = $('#tab-layouts');
  let names = [];
  try { names = await (await fetch('api/layouts')).json(); } catch { /* server off */ }
  tab.replaceChildren(
    h('p', { class: 'note' }, 'Your changes are kept in this browser as you work. Save a layout to come back to it, or keep several versions to compare.'),
    field('Save as', h('div', { class: 'row' }, h('input', { type: 'text', id: 'layout-name', value: config.name || '' }),
      h('button', { type: 'button', class: 'btn primary', onclick: saveLayout }, 'Save'))),
    h('h2', {}, 'Saved layouts'),
    names.length ? h('div', { class: 'field' }, names.map(n => h('button', { type: 'button', class: 'add', onclick: () => loadLayout(n) }, h('span', {}, n), h('small', {}, 'Load'))))
      : h('p', { class: 'note' }, 'None yet.'),
    h('h2', {}, 'Start again'),
    h('button', { type: 'button', class: 'btn', onclick: async () => { snapshot(); await applyConfig(clone(DEFAULT)); toast('Back to the warm scheme'); } }, 'Reset to the warm scheme'));
}
async function saveLayout() {
  const name = $('#layout-name').value.trim() || 'My layout';
  config.name = name;
  try {
    const r = await fetch('api/layout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, config }) });
    if (!r.ok) throw new Error();
    toast(`Saved "${name}"`);
    buildLayouts();
  } catch { toast('Could not save: is server.py running?'); }
}
async function loadLayout(name) {
  try {
    const c = await (await fetch(`api/layout?name=${encodeURIComponent(name)}`)).json();
    snapshot();
    await applyConfig(c);
    toast(`Loaded "${name}"`);
  } catch { toast('Could not load that layout'); }
}
async function applyConfig(c) {
  config = c;
  updateRoles();
  await Promise.all([loadKitchen(), loadCurtains(), rebuildItems()]);
  buildFinishes();
  buildPlaced();
  saveLocal();
}

$$('.tabs button').forEach(b => b.addEventListener('click', () => {
  $$('.tabs button').forEach(x => x.classList.toggle('on', x === b));
  $$('.tab').forEach(t => { t.hidden = t.id !== `tab-${b.dataset.tab}`; });
  if (b.dataset.tab === 'layouts') buildLayouts();
  if (b.dataset.tab === 'render') { jobsSig = ''; pollJobs(); }
}));

// ------------------------------------------------------------------ start
buildFurniture();
buildFinishes();
buildRender();
setView('orbit');
requestAnimationFrame(frame);
await Promise.all([loadShell(), loadKitchen(), loadCurtains()]);
setView('orbit');
await Promise.all(config.items.map(spawn));
$('#loading').hidden = true;
pollJobs();
window.__cfg = { recs, select, camera, scene, renderer, raycaster, get config() { return config; } };   // for debugging
