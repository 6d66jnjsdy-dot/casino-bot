const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const ECONOMY_PATH = path.join(DATA_DIR, 'economy.json');
const CONFIG_PATH = path.join(DATA_DIR, 'config.json');

const STARTING_CASH = Number(process.env.STARTING_CASH || 15000);

function ensureFile(filePath, fallback) {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, JSON.stringify(fallback, null, 2));
  }
}

// ---------- Economy (players' money) ----------
// This file is only ever ADDED to / updated in place. Restarting or
// redeploying the bot never wipes it, so player balances persist across
// bot restarts/updates.
function loadEconomy() {
  ensureFile(ECONOMY_PATH, { users: {} });
  return JSON.parse(fs.readFileSync(ECONOMY_PATH, 'utf8'));
}

function saveEconomy(data) {
  fs.writeFileSync(ECONOMY_PATH, JSON.stringify(data, null, 2));
}

function getUser(data, userId) {
  if (!data.users[userId]) {
    data.users[userId] = {
      cash: STARTING_CASH,
      bank: 0,
      cfStreak: 0, // chicken-fight current win streak
      moneyOut: STARTING_CASH // lifetime "money out" stat, like $bal shows
    };
  }
  // backfill fields for older saves
  const u = data.users[userId];
  if (u.cfStreak === undefined) u.cfStreak = 0;
  if (u.bank === undefined) u.bank = 0;
  if (u.moneyOut === undefined) u.moneyOut = u.cash + u.bank;
  return u;
}

// ---------- Config (server settings) ----------
function loadConfig() {
  ensureFile(CONFIG_PATH, { casinoRoleId: null, gameRooms: [] });
  const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  if (!cfg.gameRooms) cfg.gameRooms = [];
  if (cfg.casinoRoleId === undefined) cfg.casinoRoleId = null;
  return cfg;
}

function saveConfig(cfg) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
}

module.exports = {
  loadEconomy,
  saveEconomy,
  getUser,
  loadConfig,
  saveConfig,
  STARTING_CASH
};
