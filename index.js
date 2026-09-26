/* ============================ IMPORTS ============================ */

const fs = require("fs");
const path = require("path");

/* ============================ DATA ============================ */

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "data");
const DATA_FILE = path.join(DATA_DIR, "data.json");
const BACKUP_FILE = path.join(DATA_DIR, "data.backup.json");
const TEMP_FILE = path.join(DATA_DIR, "data.tmp.json");

function createDefaultDB() {
  return {
    currency: "💸",
    casinoRoleId: null,
    gameChannels: [],
    logChannelId: null,
    predictors: [],
    disabledCommands: [],
    users: {},
    summer: {}
  };
}

let db = createDefaultDB();

function normalizeDB() {
  db.currency ||= "💸";
  db.casinoRoleId ??= null;
  db.gameChannels = Array.isArray(db.gameChannels) ? db.gameChannels : [];
  db.predictors = Array.isArray(db.predictors) ? db.predictors : [];
  db.disabledCommands = Array.isArray(db.disabledCommands) ? db.disabledCommands : [];
  db.users = db.users && typeof db.users === "object" ? db.users : {};
  db.summer = db.summer && typeof db.summer === "object" ? db.summer : {};

  for (const id of Object.keys(db.users)) {
    const u = db.users[id];

    if (!u || typeof u !== "object") {
      db.users[id] = {
        cash: 0,
        bank: 0,
        cooldowns: {},
        cfStreak: 55
      };
      continue;
    }

    u.cash = Number.isFinite(Number(u.cash))
      ? Math.max(0, Math.floor(Number(u.cash)))
      : 0;

    u.bank = Number.isFinite(Number(u.bank))
      ? Math.max(0, Math.floor(Number(u.bank)))
      : 0;

    u.cooldowns =
      u.cooldowns && typeof u.cooldowns === "object"
        ? u.cooldowns
        : {};

    if (u.cfStreak == null) u.cfStreak = 55;
  }
}

function loadData() {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });

    const files = [DATA_FILE, BACKUP_FILE];

    for (const file of files) {
      if (!fs.existsSync(file)) continue;

      try {
        const parsed = JSON.parse(
          fs.readFileSync(file, "utf8")
        );

        db = Object.assign(createDefaultDB(), parsed);
        normalizeDB();

        console.log(`✅ Loaded persistent data from: ${file}`);
        return;
      } catch (err) {
        console.error(
          `⚠️ Could not read ${file}:`,
          err.message
        );
      }
    }

    console.log(
      "ℹ️ No previous database found. Creating a new one."
    );

    db = createDefaultDB();
    normalizeDB();
    saveDataNow();

  } catch (e) {
    console.error("❌ Failed to load persistent data:", e);

    db = createDefaultDB();
    normalizeDB();
  }
}

let saveTimer = null;
let saveInProgress = false;
let saveAgain = false;

function saveDataNow() {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });

    normalizeDB();

    const json = JSON.stringify(db, null, 2);

    // Write temporary file first.
    fs.writeFileSync(TEMP_FILE, json, "utf8");

    // Keep previous database as backup.
    if (fs.existsSync(DATA_FILE)) {
      try {
        fs.copyFileSync(DATA_FILE, BACKUP_FILE);
      } catch (e) {
        console.error(
          "⚠️ Could not create database backup:",
          e.message
        );
      }
    }

    // Replace database atomically.
    fs.renameSync(TEMP_FILE, DATA_FILE);

    console.log("💾 Database saved.");

  } catch (e) {
    console.error("❌ Failed to save database:", e);

    try {
      if (fs.existsSync(TEMP_FILE)) {
        fs.unlinkSync(TEMP_FILE);
      }
    } catch {}
  }
}

function saveData() {
  if (saveInProgress) {
    saveAgain = true;
    return;
  }

  if (saveTimer) {
    clearTimeout(saveTimer);
  }

  saveTimer = setTimeout(() => {
    saveTimer = null;
    saveInProgress = true;

    try {
      saveDataNow();
    } finally {
      saveInProgress = false;

      if (saveAgain) {
        saveAgain = false;
        saveData();
      }
    }
  }, 250);
}

function forceSaveData() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }

  saveDataNow();
}

loadData();

/* ============================ SHUTDOWN ============================ */

process.on("SIGINT", () => {
  console.log("🛑 SIGINT received. Saving database...");
  forceSaveData();
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("🛑 SIGTERM received. Saving database...");
  forceSaveData();
  process.exit(0);
});

process.on("beforeExit", () => {
  try {
    forceSaveData();
  } catch {}
});