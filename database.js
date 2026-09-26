const fs = require("fs");
const path = require("path");

const DATA_DIR =
  process.env.DATA_DIR ||
  path.join(__dirname, "data");

const DATA_FILE =
  path.join(DATA_DIR, "data.json");

const BACKUP_FILE =
  path.join(DATA_DIR, "data.backup.json");

const TEMP_FILE =
  path.join(DATA_DIR, "data.tmp.json");

function createDefaultDB() {
  return {
    currency: "💸",
    casinoRoleId: null,
    gameChannels: [],
    logChannelId: null,
    predictors: [],
    disabledCommands: [],
    users: {},
    daily: {}
  };
}

let db = createDefaultDB();

function normalizeDB() {
  if (!db || typeof db !== "object") {
    db = createDefaultDB();
  }

  db.currency ||= "💸";
  db.casinoRoleId ??= null;

  db.gameChannels =
    Array.isArray(db.gameChannels)
      ? db.gameChannels
      : [];

  db.predictors =
    Array.isArray(db.predictors)
      ? db.predictors
      : [];

  db.disabledCommands =
    Array.isArray(db.disabledCommands)
      ? db.disabledCommands
      : [];

  db.users =
    db.users &&
    typeof db.users === "object"
      ? db.users
      : {};

  if (
    !db.daily ||
    typeof db.daily !== "object"
  ) {
    db.daily =
      db.summer &&
      typeof db.summer === "object"
        ? db.summer
        : {};
  }

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

    u.cash = Number.isFinite(
      Number(u.cash)
    )
      ? Math.max(
          0,
          Math.floor(Number(u.cash))
        )
      : 0;

    u.bank = Number.isFinite(
      Number(u.bank)
    )
      ? Math.max(
          0,
          Math.floor(Number(u.bank))
        )
      : 0;

    u.cooldowns =
      u.cooldowns &&
      typeof u.cooldowns === "object"
        ? u.cooldowns
        : {};

    if (u.cfStreak == null) {
      u.cfStreak = 55;
    }
  }
}

function loadData() {
  try {
    fs.mkdirSync(DATA_DIR, {
      recursive: true
    });

    const files = [
      DATA_FILE,
      BACKUP_FILE
    ];

    for (const file of files) {
      if (!fs.existsSync(file)) {
        continue;
      }

      try {
        const parsed =
          JSON.parse(
            fs.readFileSync(
              file,
              "utf8"
            )
          );

        db = Object.assign(
          createDefaultDB(),
          parsed
        );

        normalizeDB();

        console.log(
          `✅ Loaded persistent data from: ${file}`
        );

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

  } catch (err) {
    console.error(
      "❌ Failed to load data:",
      err
    );

    db = createDefaultDB();

    normalizeDB();
  }
}

function saveDataNow() {
  try {
    fs.mkdirSync(DATA_DIR, {
      recursive: true
    });

    normalizeDB();

    const json =
      JSON.stringify(
        db,
        null,
        2
      );

    fs.writeFileSync(
      TEMP_FILE,
      json,
      "utf8"
    );

    if (fs.existsSync(DATA_FILE)) {
      try {
        fs.copyFileSync(
          DATA_FILE,
          BACKUP_FILE
        );
      } catch (err) {
        console.error(
          "⚠️ Could not create database backup:",
          err.message
        );
      }
    }

    if (fs.existsSync(DATA_FILE)) {
      try {
        fs.unlinkSync(
          DATA_FILE
        );
      } catch {}
    }

    fs.renameSync(
      TEMP_FILE,
      DATA_FILE
    );

    console.log(
      "💾 Database saved."
    );

  } catch (err) {
    console.error(
      "❌ Failed to save database:",
      err
    );

    try {
      if (
        fs.existsSync(
          TEMP_FILE
        )
      ) {
        fs.unlinkSync(
          TEMP_FILE
        );
      }
    } catch {}
  }
}

let saveTimer = null;
let saveInProgress = false;
let saveAgain = false;

function saveData() {
  if (saveInProgress) {
    saveAgain = true;
    return;
  }

  if (saveTimer) {
    clearTimeout(
      saveTimer
    );
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
    clearTimeout(
      saveTimer
    );

    saveTimer = null;
  }

  saveDataNow();
}

function getUser(id) {
  if (!db.users[id]) {
    db.users[id] = {
      cash: 0,
      bank: 0,
      cooldowns: {},
      cfStreak: 55
    };
  }

  db.users[id].cooldowns ||= {};

  if (
    db.users[id].cfStreak == null
  ) {
    db.users[id].cfStreak = 55;
  }

  return db.users[id];
}

loadData();

module.exports = {
  db,
  getUser,
  saveData,
  saveDataNow,
  forceSaveData,
  normalizeDB,
  createDefaultDB,
  DATA_DIR,
  DATA_FILE,
  BACKUP_FILE,
  TEMP_FILE
};
