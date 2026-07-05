// Showdown の champions mod から metamon 用の図鑑 JSON を書き出す。
//
// 使い方:
//   node tools/export_champions_dex.js <showdown_root> <out_dir>
//
// 出力: <out_dir>/gen9pokedex.json, <out_dir>/gen9moves.json
// (metamon/backend/showdown_dex/static/{pokemon,moves}/ の gen9 ファイルを置き換える)

const path = require("path");
const fs = require("fs");

const [showdownRoot, outDir] = process.argv.slice(2);
if (!showdownRoot || !outDir) {
  console.error("usage: node export_champions_dex.js <showdown_root> <out_dir>");
  process.exit(1);
}

const { Dex } = require(path.join(showdownRoot, "dist/sim/dex"));
const dex = Dex.mod("champions");

// poke-env / metamon の gen9pokedex.json と同じフィールド構成に揃える
function speciesEntry(s) {
  const entry = {
    abilities: s.abilities,
    baseStats: s.baseStats,
    color: s.color,
    eggGroups: s.eggGroups,
    heightm: s.heightm,
    name: s.name,
    num: s.num,
    types: s.types,
    weightkg: s.weightkg,
  };
  if (s.prevo) entry.prevo = s.prevo;
  if (s.evoLevel) entry.evoLevel = s.evoLevel;
  if (s.evos && s.evos.length) entry.evos = s.evos;
  if (s.baseSpecies !== s.name) entry.baseSpecies = s.baseSpecies;
  if (s.forme) entry.forme = s.forme;
  if (s.requiredItem) entry.requiredItem = s.requiredItem;
  if (s.otherFormes) entry.otherFormes = s.otherFormes;
  if (s.changesFrom) entry.changesFrom = s.changesFrom;
  return entry;
}

function moveEntry(m) {
  const entry = {
    accuracy: m.accuracy,
    basePower: m.basePower,
    category: m.category,
    flags: m.flags,
    name: m.name,
    num: m.num,
    pp: m.pp,
    priority: m.priority,
    secondary: m.secondary ?? null,
    target: m.target,
    type: m.type,
  };
  if (m.contestType) entry.contestType = m.contestType;
  if (m.recoil) entry.recoil = m.recoil;
  if (m.drain) entry.drain = m.drain;
  if (m.boosts) entry.boosts = m.boosts;
  if (m.status) entry.status = m.status;
  if (m.weather) entry.weather = m.weather;
  if (m.terrain) entry.terrain = m.terrain;
  if (m.sideCondition) entry.sideCondition = m.sideCondition;
  if (m.volatileStatus) entry.volatileStatus = m.volatileStatus;
  if (m.multihit) entry.multihit = m.multihit;
  if (m.heal) entry.heal = m.heal;
  return entry;
}

const pokedex = {};
for (const s of dex.species.all()) {
  if (!s.exists || s.num <= 0) continue; // CAP等は除外
  pokedex[s.id] = speciesEntry(s);
}

const moves = {};
for (const m of dex.moves.all()) {
  if (!m.exists || m.isZ || m.isMax) continue;
  moves[m.id] = moveEntry(m);
}

fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "gen9pokedex.json"), JSON.stringify(pokedex));
fs.writeFileSync(path.join(outDir, "gen9moves.json"), JSON.stringify(moves));
console.log(`species: ${Object.keys(pokedex).length}, moves: ${Object.keys(moves).length}`);
console.log(`staraptormega: ${pokedex.staraptormega ? "OK" : "MISSING"}`);
console.log(`electroshot 威力: ${moves.electroshot ? moves.electroshot.basePower : "MISSING"}`);
