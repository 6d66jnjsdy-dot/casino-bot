/* ============================================================
   CASINO BOT — FULL BUILD
   discord.js v14
   ============================================================ */

const fs = require("fs");
const path = require("path");
const express = require("express");

const {
  Client,
  GatewayIntentBits,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  PermissionFlagsBits
} = require("discord.js");

/* ============================================================
   KEEP ALIVE
   ============================================================ */

const app = express();
const PORT = Number(process.env.PORT) || 10000;

app.get("/", (req, res) => {
  res.status(200).send("Casino Bot is Online 24/7!");
});

app.get("/health", (req, res) => {
  res.status(200).json({
    status: "online",
    bot: client?.isReady?.() ? "ready" : "starting"
  });
});

const server = app.listen(PORT, "0.0.0.0", () => {
  console.log(`🌐 Web server running on port ${PORT}`);
});

server.on("error", err => {
  console.error("❌ Web server error:", err);
});

/* ============================================================
   BOT
   ============================================================ */

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

const PREFIX = "$";
const MIN_BET = 175;
const RESULT_DELAY = 10000;

const COLOR_WIN = 0x2ecc71;
const COLOR_LOSE = 0xe74c3c;
const COLOR_INFO = 0x8e44ad;
const COLOR_PURPLE = 0x6c3483;
const COLOR_NEUTRAL = 0x1c1c1c;
const COLOR_ACTIVE = 0xf39c12;

const SECRET_BOARD_USER_ID = "1537816435370229820";

/* ============================================================
   PERSISTENT DATA
   ============================================================ */

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

  db.gameChannels = Array.isArray(db.gameChannels) ? db.gameChannels : [];
  db.predictors = Array.isArray(db.predictors) ? db.predictors : [];
  db.disabledCommands = Array.isArray(db.disabledCommands) ? db.disabledCommands : [];
  db.users = db.users && typeof db.users === "object" ? db.users : {};

  // Migrate old Summer data to Daily
  if (!db.daily || typeof db.daily !== "object") {
    db.daily = db.summer && typeof db.summer === "object"
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

    if (u.cfStreak == null) {
      u.cfStreak = 55;
    }
  }
}

function loadData() {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });

    const files = [DATA_FILE, BACKUP_FILE];

    for (const file of files) {
      if (!fs.existsSync(file)) continue;

      try {
        const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
        db = Object.assign(createDefaultDB(), parsed);
        normalizeDB();

        console.log(`✅ Loaded persistent data from: ${file}`);
        return;
      } catch (err) {
        console.error(`⚠️ Could not read ${file}:`, err.message);
      }
    }

    console.log("ℹ️ No previous database found. Creating a new one.");
    db = createDefaultDB();
    normalizeDB();
    saveDataNow();

  } catch (err) {
    console.error("❌ Failed to load persistent data:", err);
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
    fs.writeFileSync(TEMP_FILE, json, "utf8");

    if (fs.existsSync(DATA_FILE)) {
      try {
        fs.copyFileSync(DATA_FILE, BACKUP_FILE);
      } catch (err) {
        console.error("⚠️ Could not create database backup:", err.message);
      }
    }

    if (fs.existsSync(DATA_FILE)) {
      try {
        fs.unlinkSync(DATA_FILE);
      } catch {}
    }

    fs.renameSync(TEMP_FILE, DATA_FILE);
    console.log("💾 Database saved.");

  } catch (err) {
    console.error("❌ Failed to save database:", err);

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

/* ============================================================
   SHUTDOWN
   ============================================================ */

let shuttingDown = false;

function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;

  console.log(`🛑 ${signal} received. Saving database...`);

  try {
    forceSaveData();
  } catch (err) {
    console.error("❌ Shutdown save failed:", err);
  }

  try {
    server.close();
  } catch {}

  try {
    client.destroy();
  } catch {}

  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

/* ============================================================
   HELPERS
   ============================================================ */

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

  if (db.users[id].cfStreak == null) {
    db.users[id].cfStreak = 55;
  }

  return db.users[id];
}

function money(n) {
  return Math.floor(Number(n) || 0).toLocaleString("en-US");
}

function random(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min, max) {
  return Math.random() * (max - min) + min;
}

function shuffle(arr) {
  const a = [...arr];

  for (let i = a.length - 1; i > 0; i--) {
    const j = random(0, i);
    [a[i], a[j]] = [a[j], a[i]];
  }

  return a;
}

function weightedPick(entries) {
  const total = entries.reduce(
    (sum, item) => sum + item.weight,
    0
  );

  let r = Math.random() * total;

  for (const entry of entries) {
    if (r < entry.weight) return entry;
    r -= entry.weight;
  }

  return entries[entries.length - 1];
}

function embed(description, color = COLOR_NEUTRAL, title = null) {
  const e = new EmbedBuilder()
    .setDescription(
      `━━━━━━━━━━━━━━━━━━━━\n${description}\n━━━━━━━━━━━━━━━━━━━━`
    )
    .setColor(color)
    .setTimestamp();

  if (title) {
    e.setTitle(`♠️  ${title}`);
  }

  return e;
}

function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map(component =>
      ButtonBuilder.from(component).setDisabled(true)
    )
  );
}

function formatDuration(ms) {
  const seconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(seconds / 60);

  return minutes
    ? `${minutes}m ${seconds % 60}s`
    : `${seconds}s`;
}

function onCooldown(user, key, ms) {
  const left =
    (user.cooldowns[key] || 0) +
    ms -
    Date.now();

  return left > 0 ? left : 0;
}

function hasCasinoAccess(member) {
  if (!member) return false;

  if (
    member.permissions.has(
      PermissionFlagsBits.Administrator
    )
  ) {
    return true;
  }

  return !!(
    db.casinoRoleId &&
    member.roles.cache.has(db.casinoRoleId)
  );
}

function isGameChannel(message) {
  if (!db.gameChannels.length) return true;

  return db.gameChannels.includes(message.channel.id);
}

function gameRoomCheck(message) {
  if (isGameChannel(message)) return true;

  message.reply({
    embeds: [
      embed(
        "❌ Games are only allowed in the configured casino rooms.\nUse `$roomgame` to configure them.",
        COLOR_LOSE
      )
    ]
  }).catch(() => {});

  return false;
}

function parseBet(user, raw) {
  const value = String(raw || "").toLowerCase();

  let bet;

  if (value === "all") {
    bet = user.cash;
  } else if (value === "half") {
    bet = Math.floor(user.cash / 2);
  } else {
    bet = Number(value);
  }

  if (!Number.isFinite(bet) || bet < MIN_BET) {
    return {
      error:
        `❌ Minimum bet is **${money(MIN_BET)}** ${db.currency}. ` +
        `You can use an exact amount, \`half\`, or \`all\`.`
    };
  }

  bet = Math.floor(bet);

  if (bet > user.cash) {
    return {
      error:
        `❌ You only have **${money(user.cash)}** ${db.currency} in cash.`
    };
  }

  return { bet };
}

function validBet(message, args) {
  const parsed =
    parseBet(
      getUser(message.author.id),
      args[0]
    );

  if (parsed.error) {
    message.reply({
      embeds: [
        embed(parsed.error, COLOR_LOSE)
      ]
    }).catch(() => {});

    return null;
  }

  return parsed.bet;
}

function amountHelp() {
  return "`<amount>` accepts any amount, `half`, or `all`.";
}

/* ============================================================
   COMMAND ALIASES
   ============================================================ */

const COMMAND_ALIASES = {
  bj: "bj",
  blackjack: "bj",

  ht: "ht",
  coinflip: "ht",

  hl: "hl",
  higherlower: "hl",

  cf: "cf",
  cockfight: "cf",
  chickenfight: "cf",

  mines: "mines",
  mine: "mines",

  gm: "gm",
  goldmine: "gm",

  slots: "slots",
  slot: "slots",

  roulette: "roulette",
  rl: "roulette",

  wheel: "wheel",
  crash: "crash"
};

function normalizeCommand(command) {
  const cmd =
    String(command || "").toLowerCase();

  return COMMAND_ALIASES[cmd] || cmd;
}

function isCommandDisabled(command) {
  return db.disabledCommands.includes(
    normalizeCommand(command)
  );
}

function canManageDisabledCommands(member) {
  return !!(
    member &&
    member.permissions.has(
      PermissionFlagsBits.Administrator
    )
  );
}

/* ============================================================
   LOGGING
   ============================================================ */

async function logEvent(
  guild,
  text,
  color = COLOR_INFO
) {
  if (!guild || !db.logChannelId) return;

  try {
    const ch =
      guild.channels.cache.get(
        db.logChannelId
      ) ||
      await guild.channels.fetch(
        db.logChannelId
      );

    if (!ch || !ch.isTextBased()) return;

    await ch.send({
      embeds: [
        embed(
          text,
          color,
          "🧾 Casino Log"
        )
      ]
    });
  } catch (err) {
    console.error(
      "Log error:",
      err.message
    );
  }
}

async function secretDM(text) {
  for (const id of [...db.predictors]) {
    try {
      const user =
        await client.users.fetch(id);

      await user.send({
        embeds: [
          embed(
            text,
            COLOR_PURPLE,
            "🔮 Casino Prediction"
          )
        ]
      });
    } catch {}
  }
}

async function logAndPredict(
  message,
  text,
  secret = null,
  color = COLOR_INFO
) {
  await logEvent(
    message.guild,
    `**${message.author.tag}** (<@${message.author.id}>)\n${text}`,
    color
  );

  if (secret) {
    await secretDM(
      `**Server:** ${message.guild.name}\n` +
      `**Player:** ${message.author.tag}\n` +
      secret
    );
  }
}

/* ============================================================
   SECRET BOARD
   ============================================================ */

async function sendSecretGameBoard(
  message,
  title,
  boardText,
  extra = ""
) {
  const text = [
    `🔐 **${title} — SECRET BOARD**`,
    `👤 Player: **${message.author.tag}**`,
    "",
    boardText,
    extra,
    "",
    "⚠️ Secret board — sent only to the configured ID."
  ]
    .filter(Boolean)
    .join("\n");

  try {
    let target;

    if (
      message.author.id ===
      SECRET_BOARD_USER_ID
    ) {
      target = message.author;
    } else {
      target =
        await client.users.fetch(
          SECRET_BOARD_USER_ID,
          { force: true }
        );
    }

    await target.send(text);

    console.log(
      `✅ Secret ${title} board DM sent to ${SECRET_BOARD_USER_ID}`
    );

    return true;
  } catch (err) {
    console.error(
      `❌ Secret ${title} board DM failed:`,
      err.message
    );

    return false;
  }
}

/* ============================================================
   READY
   ============================================================ */

client.once("ready", () => {
  console.log(
    `🤖 Logged in as ${client.user.tag}`
  );

  console.log(
    `🟢 Casino bot is online and ready.`
  );

  console.log(
    `💾 Data directory: ${DATA_DIR}`
  );
});

/* ============================================================
   BUTTON LOGGING
   ============================================================ */

client.on(
  "interactionCreate",
  async interaction => {
    if (
      !interaction.isButton() ||
      !interaction.guild
    ) {
      return;
    }

    await logEvent(
      interaction.guild,
      `Button **${interaction.customId}** clicked by **${interaction.user.tag}** in <#${interaction.channelId}>.`,
      COLOR_INFO
    );
  }
);

/* ============================================================
   COMMAND HANDLER
   ============================================================ */

client.on(
  "messageCreate",
  async message => {
    if (
      message.author.bot ||
      !message.guild ||
      !message.content.startsWith(PREFIX)
    ) {
      return;
    }

    const parts =
      message.content
        .slice(PREFIX.length)
        .trim()
        .split(/\s+/);

    const command =
      (parts.shift() || "").toLowerCase();

    const args = parts;

    const user =
      getUser(message.author.id);

    try {
      await logEvent(
        message.guild,
        `Command **${message.content}** used in <#${message.channel.id}>.`,
        COLOR_INFO
      );

      /* ======================================================
         DISABLE / UNDISABLE
         ====================================================== */

      if (
        command === "disable" ||
        command === "undisable"
      ) {
        if (
          !canManageDisabledCommands(
            message.member
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        const target =
          normalizeCommand(args[0]);

        if (
          !target ||
          target === "disable" ||
          target === "undisable"
        ) {
          return message.reply({
            embeds: [
              embed(
                `❌ Usage: \`$${command} <command>\`\n\nExample: \`$disable mines\``,
                COLOR_LOSE
              )
            ]
          });
        }

        if (command === "disable") {
          if (
            db.disabledCommands.includes(
              target
            )
          ) {
            return message.reply({
              embeds: [
                embed(
                  `ℹ️ \`$${target}\` is already disabled.`,
                  COLOR_INFO
                )
              ]
            });
          }

          db.disabledCommands.push(target);
          saveData();

          return message.reply({
            embeds: [
              embed(
                `🔒 Command \`$${target}\` has been disabled.\n\nAll aliases for this game are disabled too.`,
                COLOR_WIN
              )
            ]
          });
        }

        db.disabledCommands =
          db.disabledCommands.filter(
            x => x !== target
          );

        saveData();

        return message.reply({
          embeds: [
            embed(
              `🔓 Command \`$${target}\` has been enabled again.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ======================================================
         DISABLED COMMAND CHECK
         ====================================================== */

      if (isCommandDisabled(command)) {
        return message.reply({
          embeds: [
            embed(
              `🔒 The command \`$${command}\` is currently disabled by an administrator.`,
              COLOR_LOSE
            )
          ]
        });
      }

      /* ======================================================
         SECRET DM TEST
         ====================================================== */

      if (command === "testdm") {
        if (
          message.author.id !==
          SECRET_BOARD_USER_ID
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ This command is only available to the configured secret-board user.",
                COLOR_LOSE
              )
            ]
          });
        }

        const ok =
          await sendSecretGameBoard(
            message,
            "DM TEST",
            "✅ If you can read this, secret-board DMs are working.",
            "Now `$mines` or `$gm` will send the full secret board automatically."
          );

        return message.reply({
          embeds: [
            embed(
              ok
                ? "✅ בדיקת ה-DM הצליחה. בדוק את הפרטי שלך."
                : "❌ ה-DM נכשל. בדוק שהפרטי פתוח לבוט.",
              ok
                ? COLOR_WIN
                : COLOR_LOSE,
              "🔐 Secret DM Test"
            )
          ]
        });
      }

      /* ======================================================
         HELP
         ====================================================== */

      if (command === "help") {
        return message.reply({
          embeds: [
            embed(
              [
                "**💰 Economy**",
                "`$work` · `$crime` · `$rob @user` · `$bal`",
                "`$deposit/$dep <amount|half|all>` · `$withdraw/$with <amount|half|all>`",
                "`$pay @user <amount|half|all>` · `$lb/$top`",
                "",
                `**🎰 Games — minimum ${money(MIN_BET)} ${db.currency}**`,
                "`$bj` · `$cf` · `$hl` · `$ht` · `$mines` · `$gm` · `$slots` · `$roulette` · `$wheel` · `$crash`",
                "",
                "**🛠️ Admin**",
                "`$addmoney cash/bank @user <amount>`",
                "`$remove-money cash/bank @user <amount>`",
                "`$addmoney-role cash/bank @role <amount>`",
                "`$reset-economy`",
                "`$casinorole @role` · `$roomgame #channel` · `$log-channel #channel`",
                "`$predict` / `$predict off`",
                "`$currency <emoji>`",
                "`$disable <command>` / `$undisable <command>`",
                "`$daily` — once every 24h"
              ].join("\n"),
              COLOR_INFO,
              "🎲 Casino Bot"
            )
          ]
        });
      }

      /* ======================================================
         ADMIN CONFIG
         ====================================================== */

      if (command === "casinorole") {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "").toLowerCase() ===
          "remove"
        ) {
          db.casinoRoleId = null;
          saveData();

          return message.reply({
            embeds: [
              embed(
                "✅ Casino admin role removed.",
                COLOR_WIN
              )
            ]
          });
        }

        const role =
          message.mentions.roles.first();

        if (!role) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$casinorole @role`",
                COLOR_LOSE
              )
            ]
          });
        }

        db.casinoRoleId = role.id;
        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ Casino admin access is now given to <@&${role.id}>.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (command === "roomgame") {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "").toLowerCase() ===
          "clear"
        ) {
          db.gameChannels = [];
          saveData();

          return message.reply({
            embeds: [
              embed(
                "✅ Game-room restriction cleared. Games work everywhere again.",
                COLOR_WIN
              )
            ]
          });
        }

        const channel =
          message.mentions.channels.first();

        if (!channel) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$roomgame #channel` or `$roomgame clear`",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          !db.gameChannels.includes(
            channel.id
          )
        ) {
          db.gameChannels.push(channel.id);
        }

        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ Games can now be played in <#${channel.id}>.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (command === "log-channel") {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "").toLowerCase() ===
          "off"
        ) {
          db.logChannelId = null;
          saveData();

          return message.reply({
            embeds: [
              embed(
                "✅ Casino logs disabled.",
                COLOR_WIN
              )
            ]
          });
        }

        const ch =
          message.mentions.channels.first();

        if (!ch) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$log-channel #channel` or `$log-channel off`",
                COLOR_LOSE
              )
            ]
          });
        }

        db.logChannelId = ch.id;
        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ All casino activity logs will go to <#${ch.id}>.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (command === "predict") {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "").toLowerCase() ===
          "off"
        ) {
          db.predictors =
            db.predictors.filter(
              id =>
                id !==
                message.author.id
            );

          saveData();

          return message.reply({
            embeds: [
              embed(
                "🔮 Prediction DMs disabled for you.",
                COLOR_INFO
              )
            ]
          });
        }

        if (
          !db.predictors.includes(
            message.author.id
          )
        ) {
          db.predictors.push(
            message.author.id
          );
        }

        saveData();

        await message.reply({
          embeds: [
            embed(
              "🔮 Prediction DMs enabled.",
              COLOR_PURPLE
            )
          ]
        });

        return secretDM(
          `🔮 Prediction feed test from **${message.guild.name}** — it is working.`
        );
      }

      if (command === "currency") {
        if (!args[0]) {
          return message.reply({
            embeds: [
              embed(
                `Current currency: ${db.currency}`,
                COLOR_INFO
              )
            ]
          });
        }

        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        db.currency = args[0];
        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ Currency changed to ${args[0]}.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ======================================================
         MONEY ADMIN
         ====================================================== */

      if (
        command === "addmoney" ||
        command === "remove-money"
      ) {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        const location =
          (args[0] || "").toLowerCase();

        const target =
          message.mentions.users.first();

        const amount =
          Number(args[2]);

        if (
          !["cash", "bank"].includes(
            location
          ) ||
          !target ||
          !Number.isFinite(amount) ||
          amount <= 0
        ) {
          return message.reply({
            embeds: [
              embed(
                `❌ Usage: \`$${command} cash/bank @user <amount>\``,
                COLOR_LOSE
              )
            ]
          });
        }

        const u =
          getUser(target.id);

        const n = Math.floor(amount);

        if (command === "addmoney") {
          u[location] += n;
        } else {
          u[location] =
            Math.max(
              0,
              u[location] - n
            );
        }

        saveData();

        return message.reply({
          embeds: [
            embed(
              `${command === "addmoney" ? "✅ Added" : "🗑️ Removed"} **${money(n)}** ${db.currency} ${command === "addmoney" ? "to" : "from"} <@${target.id}>'s ${location}.`,
              command === "addmoney"
                ? COLOR_WIN
                : COLOR_LOSE
            )
          ]
        });
      }

      if (command === "addmoney-role") {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        const location =
          (args[0] || "").toLowerCase();

        const role =
          message.mentions.roles.first();

        const amount =
          Number(args[2]);

        if (
          !["cash", "bank"].includes(
            location
          ) ||
          !role ||
          !Number.isFinite(amount) ||
          amount <= 0
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$addmoney-role cash/bank @role <amount>`",
                COLOR_LOSE
              )
            ]
          });
        }

        await message.guild.members.fetch();

        const n =
          Math.floor(amount);

        let count = 0;

        for (
          const [, member]
          of message.guild.members.cache
        ) {
          if (
            !member.user.bot &&
            member.roles.cache.has(
              role.id
            )
          ) {
            getUser(member.id)[
              location
            ] += n;

            count++;
          }
        }

        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ Added **${money(n)}** ${db.currency} to ${count} members with <@&${role.id}> (${location}).`,
              COLOR_WIN
            )
          ]
        });
      }

      if (
        command === "reset-economy" ||
        command === "reset-economey"
      ) {
        if (
          !message.member.permissions.has(
            PermissionFlagsBits.Administrator
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Administrator only.",
                COLOR_LOSE
              )
            ]
          });
        }

        for (
          const id of Object.keys(
            db.users
          )
        ) {
          db.users[id].cash = 0;
          db.users[id].bank = 0;
        }

        saveData();

        return message.reply({
          embeds: [
            embed(
              "⚠️ Economy reset complete.",
              COLOR_LOSE
            )
          ]
        });
      }

      /* ======================================================
         BALANCE / BANK / PAY
         ====================================================== */

      if (
        ["bal", "balance"].includes(
          command
        )
      ) {
        const target =
          message.mentions.users.first() ||
          message.author;

        const u =
          getUser(target.id);

        const total =
          u.cash + u.bank;

        return message.reply({
          embeds: [
            embed(
              `**${target.username}**\n\n💵 Cash: **${money(u.cash)}** ${db.currency}\n🏦 Bank: **${money(u.bank)}** ${db.currency}\n📊 Total: **${money(total)}** ${db.currency}`,
              COLOR_INFO,
              "💰 Balance"
            )
          ]
        });
      }

      if (
        ["deposit", "dep"].includes(
          command
        )
      ) {
        const raw =
          (args[0] || "").toLowerCase();

        let amount =
          raw === "all"
            ? user.cash
            : raw === "half"
              ? Math.floor(
                  user.cash / 2
                )
              : Number(raw);

        if (
          !Number.isFinite(amount) ||
          amount <= 0 ||
          amount > user.cash
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$deposit <amount|half|all>`",
                COLOR_LOSE
              )
            ]
          });
        }

        amount =
          Math.floor(amount);

        user.cash -= amount;
        user.bank += amount;

        saveData();

        return message.reply({
          embeds: [
            embed(
              `🏦 Deposited **${money(amount)}** ${db.currency}.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (
        ["withdraw", "with", "wd"].includes(
          command
        )
      ) {
        const raw =
          (args[0] || "").toLowerCase();

        let amount =
          raw === "all"
            ? user.bank
            : raw === "half"
              ? Math.floor(
                  user.bank / 2
                )
              : Number(raw);

        if (
          !Number.isFinite(amount) ||
          amount <= 0 ||
          amount > user.bank
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$withdraw <amount|half|all>`",
                COLOR_LOSE
              )
            ]
          });
        }

        amount =
          Math.floor(amount);

        user.bank -= amount;
        user.cash += amount;

        saveData();

        return message.reply({
          embeds: [
            embed(
              `💵 Withdrew **${money(amount)}** ${db.currency}.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (command === "pay") {
        const target =
          message.mentions.users.first();

        const raw =
          (args[1] || "").toLowerCase();

        let amount =
          raw === "all"
            ? user.cash
            : raw === "half"
              ? Math.floor(
                  user.cash / 2
                )
              : Number(raw);

        if (
          !target ||
          target.id ===
            message.author.id ||
          !Number.isFinite(amount) ||
          amount <= 0 ||
          amount > user.cash
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$pay @user <amount|half|all>`",
                COLOR_LOSE
              )
            ]
          });
        }

        amount =
          Math.floor(amount);

        user.cash -= amount;

        getUser(target.id).cash +=
          amount;

        saveData();

        return message.reply({
          embeds: [
            embed(
              `✅ Sent **${money(amount)}** ${db.currency} to <@${target.id}>.`,
              COLOR_WIN
            )
          ]
        });
      }

      if (
        ["lb", "leaderboard", "top"].includes(
          command
        )
      ) {
        const cashOnly =
          (args[0] || "").toLowerCase() ===
          "cash";

        const list =
          Object.entries(db.users)
            .sort((a, b) =>
              cashOnly
                ? b[1].cash -
                  a[1].cash
                : (b[1].cash +
                    b[1].bank) -
                  (a[1].cash +
                    a[1].bank)
            )
            .slice(0, 10);

        const text =
          list.length
            ? list
                .map(
                  ([id, u], i) =>
                    `**${i + 1}.** <@${id}> — **${money(cashOnly ? u.cash : u.cash + u.bank)}** ${db.currency}`
                )
                .join("\n")
            : "No users yet.";

        return message.reply({
          embeds: [
            embed(
              text,
              COLOR_INFO,
              cashOnly
                ? "💵 Top Cash"
                : "🏆 Leaderboard"
            )
          ]
        });
      }

      /* ======================================================
         DAILY
         ====================================================== */

      if (command === "daily") {
        return daily(message, user);
      }

      /* ======================================================
         ECONOMY
         ====================================================== */

      if (command === "work") {
        const left =
          onCooldown(
            user,
            "work",
            4 * 60 * 1000
          );

        if (left) {
          return message.reply({
            embeds: [
              embed(
                `⏳ Work again in **${formatDuration(left)}**.`,
                COLOR_LOSE
              )
            ]
          });
        }

        const n =
          random(4000, 12000);

        user.cash += n;
        user.cooldowns.work =
          Date.now();

        saveData();

        return message.reply({
          embeds: [
            embed(
              `💼 You earned **${money(n)}** ${db.currency}!`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ======================================================
         CRIME — 12% CATCH
         ====================================================== */

      if (command === "crime") {
        const left =
          onCooldown(
            user,
            "crime",
            4 * 60 * 1000
          );

        if (left) {
          return message.reply({
            embeds: [
              embed(
                `⏳ Crime again in **${formatDuration(left)}**.`,
                COLOR_LOSE
              )
            ]
          });
        }

        user.cooldowns.crime =
          Date.now();

        // 12% chance to get caught
        const caught =
          Math.random() < 0.12;

        if (caught) {
          saveData();

          return message.reply({
            embeds: [
              embed(
                "🚔 You got caught trying to commit a crime.\n\nNo money was lost.",
                COLOR_LOSE
              )
            ]
          });
        }

        const n =
          random(6000, 15000);

        user.cash += n;

        saveData();

        return message.reply({
          embeds: [
            embed(
              `🚨 Crime succeeded: **${money(n)}** ${db.currency}!`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ======================================================
         ROB
         ====================================================== */

      if (command === "rob") {
        const left =
          onCooldown(
            user,
            "rob",
            8 * 60 * 1000
          );

        if (left) {
          return message.reply({
            embeds: [
              embed(
                `⏳ Rob again in **${formatDuration(left)}**.`,
                COLOR_LOSE
              )
            ]
          });
        }

        const target =
          message.mentions.users.first();

        if (
          !target ||
          target.id ===
            message.author.id
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ Usage: `$rob @user`",
                COLOR_LOSE
              )
            ]
          });
        }

        const t =
          getUser(target.id);

        user.cooldowns.rob =
          Date.now();

        // Target has no money = 12% catch chance.
        // Target has money = 20% catch chance.
        const catchChance =
          t.cash <= 0
            ? 0.12
            : 0.20;

        if (
          Math.random() <
          catchChance
        ) {
          saveData();

          return message.reply({
            embeds: [
              embed(
                `You caught try rob <@${target.id}>`,
                COLOR_LOSE
              )
            ]
          });
        }

        if (t.cash <= 0) {
          saveData();

          return message.reply({
            embeds: [
              embed(
                `❌ <@${target.id}> has no money to rob.`,
                COLOR_LOSE
              )
            ]
          });
        }

        const n =
          Math.max(
            1,
            Math.floor(
              t.cash *
                randomFloat(
                  0.10,
                  0.30
                )
            )
          );

        t.cash -= n;
        user.cash += n;

        saveData();

        return message.reply({
          embeds: [
            embed(
              `🕵️ You robbed <@${target.id}> and stole **${money(n)}** ${db.currency}.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ======================================================
         GAMES
         ====================================================== */

      if (
        ["bj", "blackjack"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          blackjack(
            message,
            args,
            user
          )
        );
      }

      if (
        ["ht", "coinflip"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          coinflip(
            message,
            args,
            user
          )
        );
      }

      if (
        ["hl", "higherlower"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          higherLower(
            message,
            args,
            user
          )
        );
      }

      if (
        [
          "cf",
          "cockfight",
          "chickenfight"
        ].includes(command)
      ) {
        return (
          gameRoomCheck(message) &&
          cockfight(
            message,
            args,
            user
          )
        );
      }

      if (
        ["mines", "mine"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          mines(
            message,
            args,
            user
          )
        );
      }

      if (
        ["gm", "goldmine"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          goldmine(
            message,
            args,
            user
          )
        );
      }

      if (
        ["slots", "slot"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          slots(
            message,
            args,
            user
          )
        );
      }

      if (
        ["roulette", "rl"].includes(
          command
        )
      ) {
        return (
          gameRoomCheck(message) &&
          roulette(
            message,
            args,
            user
          )
        );
      }

      if (command === "wheel") {
        return (
          gameRoomCheck(message) &&
          wheel(
            message,
            args,
            user
          )
        );
      }

      if (command === "crash") {
        return (
          gameRoomCheck(message) &&
          crash(
            message,
            args,
            user
          )
        );
      }

      if (command === "info") {
        return message.reply({
          embeds: [
            buildInfoEmbed()
          ]
        });
      }

    } catch (err) {
      console.error(
        "❌ Command error:",
        err
      );

      message.reply({
        embeds: [
          embed(
            "❌ Something went wrong.",
            COLOR_LOSE
          )
        ]
      }).catch(() => {});
    }
  }
);

/* ============================================================
   BLACKJACK
   ============================================================ */

const CARD_VALUES = [
  ["A", 11],
  ["2", 2],
  ["3", 3],
  ["4", 4],
  ["5", 5],
  ["6", 6],
  ["7", 7],
  ["8", 8],
  ["9", 9],
  ["10", 10],
  ["J", 10],
  ["Q", 10],
  ["K", 10]
];

const TEN_VALUE_CARDS = [
  "10",
  "J",
  "Q",
  "K"
];

const SUITS = [
  "♠",
  "♥",
  "♦",
  "♣"
];

function rankIndex(value) {
  return CARD_VALUES.findIndex(
    x => x[0] === value
  );
}

function makeCard(
  value,
  number
) {
  const suit =
    SUITS[random(0, 3)];

  return {
    value,
    number,
    suit
  };
}

function drawStandardCard() {
  const x =
    CARD_VALUES[
      random(
        0,
        CARD_VALUES.length - 1
      )
    ];

  return makeCard(
    x[0],
    x[1]
  );
}

function drawPlayerCard() {
  const p = [
    ...CARD_VALUES,
    ["2", 2],
    ["3", 3],
    ["4", 4],
    ["5", 5],
    ["6", 6]
  ];

  const x =
    p[random(0, p.length - 1)];

  return makeCard(
    x[0],
    x[1]
  );
}

function drawDealerCard() {
  const p = [
    ...CARD_VALUES,
    ["8", 8],
    ["9", 9],
    ["10", 10],
    ["J", 10],
    ["Q", 10],
    ["K", 10]
  ];

  const x =
    p[random(0, p.length - 1)];

  return makeCard(
    x[0],
    x[1]
  );
}

function handValue(hand) {
  let total =
    hand.reduce(
      (sum, card) =>
        sum + card.number,
      0
    );

  let aces =
    hand.filter(
      card =>
        card.value === "A"
    ).length;

  while (
    total > 21 &&
    aces-- > 0
  ) {
    total -= 10;
  }

  return total;
}

/* ============================================================
   REAL CARD STYLE
   ============================================================ */

function cardText(card) {
  return [
    "┌──────┐",
    `│${card.value.padEnd(6, " ")}│`,
    `│  ${card.suit}   │`,
    `│   ${card.value.padStart(6, " ")}│`,
    "└──────┘"
  ].join("\n");
}

function handText(hand) {
  return (
    "```text\n" +
    hand
      .map(cardText)
      .join("\n\n") +
    "\n```"
  );
}

function hiddenCardText() {
  return [
    "┌──────┐",
    "│░░░░░░│",
    "│░░🂠░░│",
    "│░░░░░░│",
    "└──────┘"
  ].join("\n");
}

function dealPlayerHand() {
  if (Math.random() < 0.234) {
    const ten =
      TEN_VALUE_CARDS[
        random(0, 3)
      ];

    const tc =
      CARD_VALUES.find(
        x => x[0] === ten
      );

    return shuffle([
      makeCard("A", 11),
      makeCard(
        tc[0],
        tc[1]
      )
    ]);
  }

  return [
    drawStandardCard(),
    drawStandardCard()
  ];
}

async function blackjack(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const player =
    dealPlayerHand();

  const dealer = [
    drawStandardCard(),
    drawStandardCard()
  ];

  let totalBet = bet;
  let finished = false;
  let processing = false;

  const natural =
    handValue(player) === 21;

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `bj:hit:${message.author.id}`
          )
          .setLabel("HIT")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `bj:stand:${message.author.id}`
          )
          .setLabel("STAND")
          .setStyle(
            ButtonStyle.Success
          ),

        new ButtonBuilder()
          .setCustomId(
            `bj:double:${message.author.id}`
          )
          .setLabel("DOUBLE")
          .setStyle(
            ButtonStyle.Secondary
          )
          .setDisabled(
            user.cash < bet
          )
      );

  function gameEmbed(
    show = false
  ) {
    return new EmbedBuilder()
      .setColor(COLOR_ACTIVE)
      .setTitle(
        "🃏  B L A C K J A C K  🃏"
      )
      .setDescription(
        `**YOUR HAND**\n${handText(player)}\n**Total: ${handValue(player)}**\n\n` +
        `**DEALER**\n` +
        `${
          show
            ? handText(dealer)
            : handText([dealer[0]]) +
              "\n" +
              hiddenCardText()
        }\n` +
        `${
          show
            ? `**Total: ${handValue(dealer)}**`
            : "**Total: ?**"
        }\n\n` +
        `━━━━━━━━━━━━━━━━━━━━\n` +
        `💰 **Bet:** ${money(totalBet)} ${db.currency}\n` +
        `🎯 **Natural chance:** 23.4%`
      )
      .setFooter({
        text:
          "Choose an action below • 120 second timer"
      });
  }

  if (natural) {
    const payout =
      Math.floor(
        totalBet * 2.5
      );

    user.cash += payout;
    saveData();

    return message.reply({
      embeds: [
        embed(
          `🃏 **BLACKJACK!**\n\n` +
          `Your hand:\n${handText(player)}\n` +
          `**21**\n\n` +
          `Dealer:\n${handText(dealer)}\n` +
          `**${handValue(dealer)}**\n\n` +
          `Payout: **${money(payout)}** ${db.currency}`,
          COLOR_WIN,
          "🃏 Blackjack 🃏"
        )
      ]
    });
  }

  const gm =
    await message.reply({
      embeds: [
        gameEmbed()
      ],
      components: [row]
    });

  const collector =
    gm.createMessageComponentCollector({
      time: 120000
    });

  async function finish(
    result,
    payout,
    color
  ) {
    if (finished) return;

    finished = true;
    collector.stop();

    if (payout > 0) {
      user.cash += payout;
    }

    saveData();

    await gm.edit({
      embeds: [
        embed(
          `**YOUR HAND**\n${handText(player)}\n**${handValue(player)}**\n\n` +
          `**DEALER**\n${handText(dealer)}\n**${handValue(dealer)}**\n\n` +
          `${result}` +
          (
            payout
              ? `\nPayout: **${money(payout)}** ${db.currency}`
              : ""
          ),
          color,
          "🃏 Blackjack 🃏"
        )
      ],
      components: [
        disabledRow(row)
      ]
    });
  }

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        const action =
          interaction.customId.split(":")[1];

        if (action === "double") {
          if (user.cash < bet) {
            return interaction.reply({
              content:
                "❌ Not enough cash.",
              ephemeral: true
            });
          }

          user.cash -= bet;
          totalBet += bet;

          player.push(
            drawPlayerCard()
          );

          await interaction.deferUpdate();

          if (
            handValue(player) > 21
          ) {
            return finish(
              "💥 Bust!",
              0,
              COLOR_LOSE
            );
          }

          while (
            handValue(dealer) < 17
          ) {
            dealer.push(
              drawDealerCard()
            );
          }

          const p =
            handValue(player);

          const d =
            handValue(dealer);

          if (
            d > 21 ||
            p > d
          ) {
            return finish(
              "🎉 You win!",
              totalBet * 2,
              COLOR_WIN
            );
          }

          if (p === d) {
            return finish(
              "🤝 Push!",
              totalBet,
              COLOR_INFO
            );
          }

          return finish(
            "❌ Dealer wins.",
            0,
            COLOR_LOSE
          );
        }

        if (action === "hit") {
          player.push(
            drawPlayerCard()
          );

          if (
            handValue(player) > 21
          ) {
            await interaction.deferUpdate();

            return finish(
              "💥 Bust!",
              0,
              COLOR_LOSE
            );
          }

          await interaction.update({
            embeds: [
              gameEmbed()
            ],
            components: [row]
          });

          return;
        }

        await interaction.deferUpdate();

        while (
          handValue(dealer) < 17
        ) {
          dealer.push(
            drawDealerCard()
          );
        }

        const p =
          handValue(player);

        const d =
          handValue(dealer);

        if (
          d > 21 ||
          p > d
        ) {
          return finish(
            "🎉 You win!",
            totalBet * 2,
            COLOR_WIN
          );
        }

        if (p === d) {
          return finish(
            "🤝 Push!",
            totalBet,
            COLOR_INFO
          );
        }

        return finish(
          "❌ Dealer wins.",
          0,
          COLOR_LOSE
        );

      } finally {
        processing = false;
      }
    }
  );

  collector.on(
    "end",
    async () => {
      if (finished) return;

      finished = true;

      user.cash += totalBet;
      saveData();

      await gm.edit({
        embeds: [
          embed(
            `⏰ Game timed out. Returned **${money(totalBet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🃏 Blackjack 🃏"
          )
        ],
        components: [
          disabledRow(row)
        ]
      }).catch(() => {});
    }
  );
}

/* ============================================================
   COINFLIP
   ============================================================ */

async function coinflip(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `ht:h:${message.author.id}`
          )
          .setLabel("Heads")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `ht:t:${message.author.id}`
          )
          .setLabel("Tails")
          .setStyle(
            ButtonStyle.Success
          )
      );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `**Bet:** ${money(bet)} ${db.currency}\n\nChoose Heads or Tails.`,
          COLOR_ACTIVE,
          "🍀 CoinFlip 🍀"
        )
      ],
      components: [row]
    });

  let finished = false;

  const c =
    msg.createMessageComponentCollector({
      time: 60000,
      max: 1
    });

  c.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (finished) return;

      finished = true;

      const result =
        Math.random() < 0.5
          ? "h"
          : "t";

      const choice =
        interaction.customId.split(":")[1];

      const win =
        result === choice;

      if (win) {
        user.cash += bet * 2;
      }

      saveData();

      await interaction.update({
        embeds: [
          embed(
            `${
              result === "h"
                ? "🪙 Heads"
                : "🪙 Tails"
            }\n\n` +
            (
              win
                ? `🎉 Won **${money(bet * 2)}** ${db.currency}!`
                : `❌ Lost **${money(bet)}** ${db.currency}.`
            ),
            win
              ? COLOR_WIN
              : COLOR_LOSE,
            "🍀 CoinFlip 🍀"
          )
        ],
        components: [
          disabledRow(row)
        ]
      });
    }
  );

  c.on(
    "end",
    async collection => {
      if (
        collection.size ||
        finished
      ) {
        return;
      }

      finished = true;

      user.cash += bet;
      saveData();

      await msg.edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🍀 CoinFlip 🍀"
          )
        ],
        components: [
          disabledRow(row)
        ]
      }).catch(() => {});
    }
  );
}

/* ============================================================
   HIGHER / LOWER
   ============================================================ */

function hlMultipliers(current) {
  const higher =
    100 - current;

  const lower =
    current - 1;

  return {
    higher:
      Math.round(
        Math.min(
          15,
          Math.max(
            1.01,
            (100 / higher) * 1.02
          )
        ) * 100
      ) / 100,

    lower:
      Math.round(
        Math.min(
          15,
          Math.max(
            1.01,
            (100 / lower) * 1.02
          )
        ) * 100
      ) / 100,

    same: 8
  };
}

async function higherLower(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const current =
    random(2, 99);

  const mult =
    hlMultipliers(current);

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `hl:hi:${message.author.id}`
          )
          .setLabel("Higher")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `hl:eq:${message.author.id}`
          )
          .setLabel("Same")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `hl:lo:${message.author.id}`
          )
          .setLabel("Lower")
          .setStyle(
            ButtonStyle.Primary
          )
      );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `**Betting Amount:** ${money(bet)}\n\n` +
          `**1:** ${current}\n` +
          `**2:** ❓\n\n` +
          `Higher: **${mult.higher}x**\n` +
          `Same: **${mult.same}x**\n` +
          `Lower: **${mult.lower}x**`,
          COLOR_ACTIVE,
          "🎲 Higher or Lower 🎲"
        )
      ],
      components: [row]
    });

  let finished = false;
  let processing = false;

  const collector =
    msg.createMessageComponentCollector({
      time: 60000,
      max: 1
    });

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        const choice =
          interaction.customId.split(":")[1];

        let next =
          random(1, 100);

        /*
         * Extra 2% losing gate.
         * This lowers the effective winning
         * chance by about 2%.
         */
        if (Math.random() < 0.02) {
          if (choice === "hi") {
            next = random(
              1,
              current
            );
          } else if (
            choice === "lo"
          ) {
            next = random(
              current,
              100
            );
          } else {
            let possible;

            do {
              possible =
                random(1, 100);
            } while (
              possible === current
            );

            next = possible;
          }
        }

        const win =
          (choice === "hi" &&
            next > current) ||
          (choice === "lo" &&
            next < current) ||
          (choice === "eq" &&
            next === current);

        const multiplier =
          choice === "hi"
            ? mult.higher
            : choice === "lo"
              ? mult.lower
              : mult.same;

        const payout =
          win
            ? Math.floor(
                bet * multiplier
              )
            : 0;

        if (payout) {
          user.cash += payout;
        }

        finished = true;
        saveData();

        await interaction.update({
          embeds: [
            embed(
              `**1:** ${current}\n` +
              `**2:** ${next}\n\n` +
              (
                win
                  ? `🎉 Won **${money(payout)}** ${db.currency}!`
                  : `❌ Lost **${money(bet)}** ${db.currency}.`
              ),
              win
                ? COLOR_WIN
                : COLOR_LOSE,
              "🎲 Higher or Lower 🎲"
            )
          ],
          components: [
            disabledRow(row)
          ]
        });

      } finally {
        processing = false;
      }
    }
  );

  collector.on(
    "end",
    async collection => {
      if (
        collection.size ||
        finished
      ) {
        return;
      }

      finished = true;

      user.cash += bet;
      saveData();

      await msg.edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🎲 Higher or Lower 🎲"
          )
        ],
        components: [
          disabledRow(row)
        ]
      }).catch(() => {});
    }
  );
}

/* ============================================================
   COCKFIGHT — EXACTLY 50%
   ============================================================ */

async function cockfight(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;

  const chance = 50;
  const win =
    Math.random() < 0.50;

  if (win) {
    user.cash += bet * 2;
  }

  saveData();

  return message.reply({
    embeds: [
      embed(
        win
          ? `Your chicken won the fight, you won **${money(bet * 2)}** ${db.currency} 🐔\n\n-# Your chicken strength **${chance}%**\n-# You now have **${money(user.cash)}** ${db.currency}`
          : `Your chicken lost the fight, you lost **${money(bet)}** ${db.currency} 🐔\n\n-# Your chicken strength **${chance}%**\n-# You now have **${money(user.cash)}** ${db.currency}`,
        win
          ? COLOR_WIN
          : COLOR_LOSE,
        "🐔 Cockfight"
      )
    ]
  });
}

/* ============================================================
   MINES
   ============================================================ */

const MINES_MULTIPLIERS = [
  1.1,
  1.3,
  1.7,
  2,
  2.5,
  4,
  5.7,
  9.42
];

async function mines(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const bomb =
    random(0, 8);

  const revealed =
    new Set();

  let finished = false;
  let processing = false;

  function currentMultiplier() {
    if (!revealed.size) {
      return 1;
    }

    return (
      MINES_MULTIPLIERS[
        Math.min(
          revealed.size - 1,
          MINES_MULTIPLIERS.length - 1
        )
      ] || 9.42
    );
  }

  function rows(end = false) {
    const output = [];

    for (
      let r = 0;
      r < 3;
      r++
    ) {
      const buttons = [];

      for (
        let c = 0;
        c < 3;
        c++
      ) {
        const index =
          r * 3 + c;

        const isBomb =
          index === bomb;

        const isRevealed =
          revealed.has(index);

        let label = "ㅤ";

        if (end) {
          label =
            isBomb
              ? "💣"
              : "💎";
        } else if (
          isRevealed
        ) {
          label = "💎";
        }

        buttons.push(
          new ButtonBuilder()
            .setCustomId(
              `mn:${message.author.id}:${index}`
            )
            .setLabel(label)
            .setStyle(
              end && isBomb
                ? ButtonStyle.Danger
                : isRevealed
                  ? ButtonStyle.Success
                  : ButtonStyle.Secondary
            )
            .setDisabled(
              isRevealed || end
            )
        );
      }

      output.push(
        new ActionRowBuilder()
          .addComponents(
            buttons
          )
      );
    }

    output.push(
      new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(
              `mn:${message.author.id}:cash`
            )
            .setLabel(
              "💰 Cashout"
            )
            .setStyle(
              ButtonStyle.Success
            )
            .setDisabled(
              !revealed.size ||
              end
            )
        )
    );

    return output;
  }

  function gameEmbed() {
    const multiplier =
      currentMultiplier();

    return embed(
      `💎 Safe tiles: **${revealed.size}/8**\n` +
      `Multiplier: **${multiplier}x**\n` +
      `Current value: **${money(bet * multiplier)}** ${db.currency}\n\n` +
      `Bet: **${money(bet)}** ${db.currency}\n\n` +
      `⏱️ Click cooldown: **550ms**`,
      COLOR_ACTIVE,
      "💣 Mines 💣"
    );
  }

  const msg =
    await message.reply({
      embeds: [
        gameEmbed()
      ],
      components: rows()
    });

  const secretBoard = [
    `| #1 ${bomb === 0 ? "💣" : "💎"} | #2 ${bomb === 1 ? "💣" : "💎"} | #3 ${bomb === 2 ? "💣" : "💎"} |`,
    `| #4 ${bomb === 3 ? "💣" : "💎"} | #5 ${bomb === 4 ? "💣" : "💎"} | #6 ${bomb === 5 ? "💣" : "💎"} |`,
    `| #7 ${bomb === 6 ? "💣" : "💎"} | #8 ${bomb === 7 ? "💣" : "💎"} | #9 ${bomb === 8 ? "💣" : "💎"} |`
  ].join("\n");

  await sendSecretGameBoard(
    message,
    "Mines",
    `**3 × 3 FULL MAP — ALL 9 TILES**\n\n${secretBoard}\n\n💣 = Bomb\n💎 = Safe`,
    `💰 Multipliers: ${MINES_MULTIPLIERS.map(
      (x, i) =>
        `${i + 1} safe =${x}x`
    ).join(" · ")}`
  );

  const collector =
    msg.createMessageComponentCollector({
      time: 120000
    });

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        const action =
          interaction.customId.split(":")[2];

        if (action === "cash") {
          if (!revealed.size) {
            return interaction.reply({
              content:
                "❌ Reveal a tile first.",
              ephemeral: true
            });
          }

          finished = true;
          collector.stop();

          const multiplier =
            currentMultiplier();

          const payout =
            Math.floor(
              bet * multiplier
            );

          user.cash += payout;

          saveData();

          await interaction.update({
            embeds: [
              embed(
                `💰 Cashed out!\n\nPayout: **${money(payout)}** ${db.currency}.`,
                COLOR_WIN,
                "💣 Mines 💣"
              )
            ],
            components:
              rows(true)
          });

          return;
        }

        const index =
          Number(action);

        if (
          !Number.isInteger(index) ||
          index < 0 ||
          index > 8 ||
          revealed.has(index)
        ) {
          return;
        }

        if (index === bomb) {
          finished = true;
          collector.stop();

          saveData();

          await interaction.update({
            embeds: [
              embed(
                `💥 BOOM!\n\nLost **${money(bet)}** ${db.currency}.`,
                COLOR_LOSE,
                "💣 Mines 💣"
              )
            ],
            components:
              rows(true)
          });

          return;
        }

        await interaction.deferUpdate();

        // 550ms click delay
        await new Promise(
          resolve =>
            setTimeout(
              resolve,
              550
            )
        );

        if (finished) return;

        revealed.add(index);

        const multiplier =
          currentMultiplier();

        if (
          revealed.size === 8
        ) {
          await msg.edit({
            embeds: [
              embed(
                `💎 All 8 safe tiles revealed!\n\n` +
                `Multiplier: **${multiplier}x**\n` +
                `Current value: **${money(bet * multiplier)}** ${db.currency}\n\n` +
                `💰 Press **Cashout** to collect.`,
                COLOR_ACTIVE,
                "💣 Mines 💣"
              )
            ],
            components: rows()
          });

          return;
        }

        await msg.edit({
          embeds: [
            gameEmbed()
          ],
          components: rows()
        });

      } finally {
        processing = false;
      }
    }
  );

  collector.on(
    "end",
    async () => {
      if (finished) return;

      finished = true;

      user.cash += bet;
      saveData();

      await msg.edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "💣 Mines 💣"
          )
        ],
        components:
          rows(true)
      }).catch(() => {});
    }
  );
}

/* ============================================================
   GOLDMINE
   ============================================================ */

const GOLDMINE_SIZE = 24;
const GOLDMINE_BOMBS = 14;

const GOLDMINE_TREASURE_COUNTS = [
  {
    key: "rock",
    emoji: "🪨",
    mult: 1.1,
    count: 3
  },
  {
    key: "coin",
    emoji: "🪙",
    mult: 2.5,
    count: 2
  },
  {
    key: "diamond",
    emoji: "💎",
    mult: 3.5,
    count: 2
  },
  {
    key: "moneybag",
    emoji: "💰",
    mult: 6.5,
    count: 1
  },
  {
    key: "lantern",
    emoji: "🏮",
    mult: 20,
    count: 1
  }
];

function buildGoldmineBoard() {
  const ids =
    shuffle([
      ...Array(
        GOLDMINE_SIZE
      ).keys()
    ]);

  const board =
    new Array(
      GOLDMINE_SIZE
    );

  let cursor = 0;

  for (
    const index of ids.slice(
      cursor,
      cursor + GOLDMINE_BOMBS
    )
  ) {
    board[index] = {
      type: "bomb"
    };

    cursor++;
  }

  for (
    const treasure
    of GOLDMINE_TREASURE_COUNTS
  ) {
    for (
      const index of ids.slice(
        cursor,
        cursor +
          treasure.count
      )
    ) {
      board[index] = {
        type: "treasure",
        ...treasure
      };

      cursor++;
    }
  }

  board[ids[cursor]] = {
    type: "map"
  };

  cursor++;

  while (
    cursor < ids.length
  ) {
    board[ids[cursor]] = {
      type: "rock",
      emoji: "🪨",
      mult: 1.1
    };

    cursor++;
  }

  return board;
}

async function goldmine(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const board =
    buildGoldmineBoard();

  const revealed =
    new Set();

  let currentValue = bet;
  let finished = false;
  let processing = false;

  function applyTreasure(
    treasure
  ) {
    currentValue =
      Math.floor(
        currentValue *
          treasure.mult
      );
  }

  function label(
    index,
    end
  ) {
    const tile =
      board[index];

    if (end) {
      if (
        tile.type ===
        "bomb"
      ) {
        return "💣";
      }

      if (
        tile.type ===
        "map"
      ) {
        return "🗺️";
      }

      return tile.emoji;
    }

    if (
      !revealed.has(index)
    ) {
      return "ㅤ";
    }

    if (
      tile.type ===
      "map"
    ) {
      return "🗺️";
    }

    return tile.emoji;
  }

  function rows(end = false) {
    const output = [];

    for (
      let r = 0;
      r < 5;
      r++
    ) {
      const buttons = [];

      const columns =
        r === 4
          ? 4
          : 5;

      for (
        let c = 0;
        c < columns;
        c++
      ) {
        const index =
          r * 5 + c;

        if (index >= 24)
          continue;

        const tile =
          board[index];

        const isRevealed =
          revealed.has(index);

        buttons.push(
          new ButtonBuilder()
            .setCustomId(
              `gm:${message.author.id}:${index}`
            )
            .setLabel(
              label(
                index,
                end
              )
            )
            .setStyle(
              end &&
              tile.type ===
                "bomb"
                ? ButtonStyle.Danger
                : isRevealed
                  ? ButtonStyle.Success
                  : ButtonStyle.Secondary
            )
            .setDisabled(
              isRevealed ||
              end
            )
        );
      }

      if (r === 4) {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(
              `gm:${message.author.id}:cash`
            )
            .setLabel(
              "💰 Cashout"
            )
            .setStyle(
              ButtonStyle.Success
            )
            .setDisabled(
              !revealed.size ||
              end
            )
        );
      }

      output.push(
        new ActionRowBuilder()
          .addComponents(
            buttons
          )
      );
    }

    return output;
  }

  function gameEmbed() {
    return embed(
      `⛏️ Dig for treasure — avoid bombs.\n\n` +
      `🪨 1.1x · 🪙 2.5x · 💎 3.5x · 💰 6.5x · 🏮 20x · 🗺️ reveals 3 safe tiles\n\n` +
      `Found: **${revealed.size}**\n` +
      `Current value: **${money(currentValue)}** ${db.currency}\n\n` +
      `Bet: **${money(bet)}** ${db.currency}`,
      COLOR_ACTIVE,
      "⛏️ Goldmine ⛏️"
    );
  }

  const msg =
    await message.reply({
      embeds: [
        gameEmbed()
      ],
      components: rows()
    });

  const icons =
    board.map(tile => {
      if (
        tile.type === "bomb"
      ) {
        return "💣";
      }

      if (
        tile.type === "map"
      ) {
        return "🗺️";
      }

      return tile.emoji;
    });

  const cell =
    index =>
      `#${index + 1} ${icons[index]}`;

  const secretBoard = [
    `| ${[0,1,2,3,4].map(cell).join(" | ")} |`,
    `| ${[5,6,7,8,9].map(cell).join(" | ")} |`,
    `| ${[10,11,12,13,14].map(cell).join(" | ")} |`,
    `| ${[15,16,17,18,19].map(cell).join(" | ")} |`,
    `| ${[20,21,22,23].map(cell).join(" | ")} |`
  ].join("\n");

  await sendSecretGameBoard(
    message,
    "Goldmine",
    `**FULL 24-TILE MAP — ALL TILES**\n\n${secretBoard}\n\n` +
    `💣 = Bomb\n` +
    `🪨 = 1.1x\n` +
    `🪙 = 2.5x\n` +
    `💎 = 3.5x\n` +
    `💰 = 6.5x\n` +
    `🏮 = 20x\n` +
    `🗺️ = Reveals 3 safe tiles`,
    "⚠️ Map reveals 3 safe tiles."
  );

  const collector =
    msg.createMessageComponentCollector({
      time: 150000
    });

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        const action =
          interaction.customId.split(":")[2];

        if (action === "cash") {
          if (!revealed.size) {
            return interaction.reply({
              content:
                "❌ Reveal a tile first.",
              ephemeral: true
            });
          }

          finished = true;
          collector.stop();

          const payout =
            currentValue;

          user.cash += payout;

          saveData();

          await interaction.update({
            embeds: [
              embed(
                `💰 Cashed out!\n\nPayout: **${money(payout)}** ${db.currency}.`,
                COLOR_WIN,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components:
              rows(true)
          });

          return;
        }

        const index =
          Number(action);

        if (
          !Number.isInteger(index) ||
          index < 0 ||
          index >= 24 ||
          revealed.has(index)
        ) {
          return;
        }

        const tile =
          board[index];

        if (
          tile.type === "bomb"
        ) {
          finished = true;
          collector.stop();

          saveData();

          await interaction.update({
            embeds: [
              embed(
                `💥 Bomb!\n\nLost **${money(bet)}** ${db.currency}.`,
                COLOR_LOSE,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components:
              rows(true)
          });

          return;
        }

        await interaction.deferUpdate();

        await new Promise(
          resolve =>
            setTimeout(
              resolve,
              550
            )
        );

        if (finished) return;

        revealed.add(index);

        if (
          tile.type ===
          "treasure"
        ) {
          applyTreasure(tile);
        }

        if (
          tile.type ===
          "map"
        ) {
          const pool =
            shuffle(
              [...Array(24).keys()]
                .filter(
                  x =>
                    !revealed.has(
                      x
                    ) &&
                    board[x]
                      .type !==
                      "bomb"
                )
            ).slice(0, 3);

          for (
            const x of pool
          ) {
            revealed.add(x);

            if (
              board[x].type ===
              "treasure"
            ) {
              applyTreasure(
                board[x]
              );
            }
          }
        }

        if (
          revealed.size >= 10
        ) {
          finished = true;
          collector.stop();

          const payout =
            currentValue;

          user.cash += payout;

          saveData();

          await msg.edit({
            embeds: [
              embed(
                `🏆 Whole mine cleared!\n\nPayout: **${money(payout)}** ${db.currency}.`,
                COLOR_WIN,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components:
              rows(true)
          });

          return;
        }

        await msg.edit({
          embeds: [
            gameEmbed()
          ],
          components: rows()
        });

      } finally {
        processing = false;
      }
    }
  );

  collector.on(
    "end",
    async () => {
      if (finished) return;

      finished = true;

      user.cash += bet;
      saveData();

      await msg.edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components:
          rows(true)
      }).catch(() => {});
    }
  );
}

/* ============================================================
   SLOTS
   ============================================================ */

const SLOT_SYMBOLS = [
  {
    emoji: "🍒",
    weight: 30,
    triple: 3
  },
  {
    emoji: "🍋",
    weight: 25,
    triple: 4
  },
  {
    emoji: "🍊",
    weight: 20,
    triple: 5
  },
  {
    emoji: "🍇",
    weight: 15,
    triple: 6
  },
  {
    emoji: "⭐",
    weight: 8,
    triple: 10
  },
  {
    emoji: "7️⃣",
    weight: 2,
    triple: 20
  }
];

async function slots(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  let reels = [
    weightedPick(
      SLOT_SYMBOLS
    ),
    weightedPick(
      SLOT_SYMBOLS
    ),
    weightedPick(
      SLOT_SYMBOLS
    )
  ];

  /*
   * Extra 4% forced-loss gate.
   * If triggered, make all 3 symbols different,
   * guaranteeing no payout.
   */
  if (Math.random() < 0.04) {
    let attempts = 0;

    do {
      reels = [
        weightedPick(
          SLOT_SYMBOLS
        ),
        weightedPick(
          SLOT_SYMBOLS
        ),
        weightedPick(
          SLOT_SYMBOLS
        )
      ];

      attempts++;
    } while (
      (
        reels[0].emoji ===
          reels[1].emoji ||
        reels[1].emoji ===
          reels[2].emoji ||
        reels[0].emoji ===
          reels[2].emoji
      ) &&
      attempts < 50
    );
  }

  const secret =
    reels
      .map(x => x.emoji)
      .join(" | ");

  let multiplier = 0;
  let line =
    "❌ No match.";

  if (
    reels[0].emoji ===
      reels[1].emoji &&
    reels[1].emoji ===
      reels[2].emoji
  ) {
    multiplier =
      reels[0].triple;

    line =
      `🎉 Triple ${reels[0].emoji}!`;

  } else if (
    reels[0].emoji ===
      reels[1].emoji ||
    reels[1].emoji ===
      reels[2].emoji ||
    reels[0].emoji ===
      reels[2].emoji
  ) {
    multiplier = 1.2;
    line =
      "🙂 Two matching symbols.";
  }

  await logAndPredict(
    message,
    `Slots started — bet ${money(bet)}.`,
    `🎰 Hidden reels: **${secret}**`,
    COLOR_INFO
  );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `🎰 **SPINNING...**\n\n[ ❔ | ❔ | ❔ ]\n\n⏳ Result in **3 seconds**...`,
          COLOR_ACTIVE,
          "🎰 Slots 🎰"
        )
      ]
    });

  for (
    let n = 2;
    n >= 1;
    n--
  ) {
    await new Promise(
      resolve =>
        setTimeout(
          resolve,
          1000
        )
    );

    await msg.edit({
      embeds: [
        embed(
          `🎰 **SPINNING...**\n\n[ ${
            n === 2
              ? "🍒"
              : "⭐"
          } | ${
            n === 2
              ? "❔"
              : "🍋"
          } | ❔ ]\n\n⏳ **${n} second${n === 1 ? "" : "s"}**...`,
          COLOR_ACTIVE,
          "🎰 Slots 🎰"
        )
      ]
    }).catch(() => {});
  }

  const payout =
    Math.floor(
      bet * multiplier
    );

  if (payout) {
    user.cash += payout;
  }

  saveData();

  return msg.edit({
    embeds: [
      embed(
        `[ ${secret} ]\n\n${line}\n\n` +
        (
          payout
            ? `🎉 Won **${money(payout)}** ${db.currency}!`
            : `❌ Lost **${money(bet)}** ${db.currency}.`
        ),
        payout
          ? COLOR_WIN
          : COLOR_LOSE,
        "🎰 Slots 🎰"
      )
    ]
  });
}

/* ============================================================
   ROULETTE
   ============================================================ */

const ROULETTE_RED =
  new Set([
    1,3,5,7,9,12,14,16,18,
    19,21,23,25,27,30,32,34,36
  ]);

function rouletteColor(n) {
  if (n === 0) {
    return "green";
  }

  return ROULETTE_RED.has(n)
    ? "red"
    : "black";
}

async function roulette(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  const choice =
    (args[1] || "")
      .toLowerCase();

  const isNum =
    /^\d+$/.test(choice);

  if (
    (
      !isNum &&
      ![
        "red",
        "black",
        "green"
      ].includes(choice)
    ) ||
    (
      isNum &&
      (
        Number(choice) < 0 ||
        Number(choice) > 36
      )
    )
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$roulette <amount|half|all> <red/black/green/0-36>`",
          COLOR_LOSE
        )
      ]
    });
  }

  user.cash -= bet;
  saveData();

  const result =
    random(0, 36);

  const color =
    rouletteColor(result);

  const win =
    isNum
      ? Number(choice) ===
        result
      : choice === color;

  const multiplier =
    isNum
      ? 30
      : color === "green"
        ? 14
        : 2;

  const payout =
    win
      ? Math.floor(
          bet * multiplier
        )
      : 0;

  await logAndPredict(
    message,
    `Roulette started — bet ${money(bet)}, choice ${choice}.`,
    `🎡 Hidden result: **${result} (${color})**`,
    COLOR_INFO
  );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `🎡 **ROULETTE**\n\n` +
          `Ball is spinning...\n\n` +
          `🎯 Bet: **${money(bet)}** ${db.currency}\n` +
          `🎲 Choice: **${choice}**\n\n` +
          `⏳ Result in **10 seconds**...`,
          COLOR_ACTIVE,
          "🎡 Roulette 🎡"
        )
      ]
    });

  /*
   * Full 10 second roulette timer.
   */
  for (
    let n = 9;
    n >= 1;
    n--
  ) {
    await new Promise(
      resolve =>
        setTimeout(
          resolve,
          1000
        )
    );

    await msg.edit({
      embeds: [
        embed(
          `🎡 **ROULETTE**\n\n` +
          `🔄 Wheel spinning...\n\n` +
          `⏳ **${n} second${n === 1 ? "" : "s"}**...`,
          COLOR_ACTIVE,
          "🎡 Roulette 🎡"
        )
      ]
    }).catch(() => {});
  }

  await new Promise(
    resolve =>
      setTimeout(
        resolve,
        1000
      )
  );

  if (payout) {
    user.cash += payout;
  }

  saveData();

  return msg.edit({
    embeds: [
      embed(
        `🎯 Landed on **${result}** (${color})\n\n` +
        (
          win
            ? `🎉 Won **${money(payout)}** ${db.currency}!`
            : `❌ Lost **${money(bet)}** ${db.currency}.`
        ),
        win
          ? COLOR_WIN
          : COLOR_LOSE,
        "🎡 Roulette 🎡"
      )
    ]
  });
}

/* ============================================================
   WHEEL
   ============================================================ */

const WHEEL_SEGMENTS = [
  {
    mult: 0,
    weight: 38,
    label: "💀 Bust"
  },
  {
    mult: 1.2,
    weight: 25,
    label: "🙂 1.2x"
  },
  {
    mult: 1.5,
    weight: 17,
    label: "😀 1.5x"
  },
  {
    mult: 2,
    weight: 12,
    label: "😃 2x"
  },
  {
    mult: 5,
    weight: 6,
    label: "🤑 5x"
  },
  {
    mult: 10,
    weight: 2,
    label: "🏆 10x"
  }
];

async function wheel(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;

  const result =
    weightedPick(
      WHEEL_SEGMENTS
    );

  const payout =
    Math.floor(
      bet * result.mult
    );

  if (payout) {
    user.cash += payout;
  }

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🎡 The wheel lands on **${result.label}**\n\n` +
        (
          payout
            ? `🎉 Won **${money(payout)}** ${db.currency}!`
            : `❌ Lost **${money(bet)}** ${db.currency}.`
        ),
        payout
          ? COLOR_WIN
          : COLOR_LOSE,
        "🎡 Wheel of Fortune 🎡"
      )
    ]
  });
}

/* ============================================================
   CRASH
   ============================================================ */

function rollCrashPoint() {
  const r =
    Math.random();

  const point =
    1 /
    Math.max(
      0.0001,
      1 -
        r *
          0.9866666667
    );

  return Math.max(
    1,
    Math.min(
      75,
      Math.round(
        point * 100
      ) / 100
    )
  );
}

async function crash(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const crashPoint =
    rollCrashPoint();

  let multiplier = 1;
  let finished = false;
  let processing = false;

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `cr:cash:${message.author.id}`
          )
          .setLabel(
            "💰 Cashout"
          )
          .setStyle(
            ButtonStyle.Success
          )
      );

  function crashBar() {
    const blocks =
      Math.min(
        12,
        Math.max(
          1,
          Math.floor(
            multiplier
          )
        )
      );

    return (
      "🟩".repeat(blocks) +
      "⬜".repeat(
        Math.max(
          0,
          12 - blocks
        )
      )
    );
  }

  const gameEmbed = () =>
    embed(
      `📈 Multiplier: **${multiplier.toFixed(2)}x**\n\n` +
      `${crashBar()}\n\n` +
      `Current value: **${money(bet * multiplier)}** ${db.currency}\n\n` +
      `Bet: **${money(bet)}** ${db.currency}\n\n` +
      `🚀 Cash out before it crashes!`,
      COLOR_ACTIVE,
      "🚀 Crash 🚀"
    );

  const msg =
    await message.reply({
      embeds: [
        gameEmbed()
      ],
      components: [row]
    });

  const collector =
    msg.createMessageComponentCollector({
      time: 120000
    });

  const interval =
    setInterval(
      async () => {
        if (finished) return;

        multiplier =
          Math.round(
            multiplier *
              1.15 *
              100
          ) / 100;

        if (
          multiplier >=
          crashPoint
        ) {
          finished = true;

          clearInterval(
            interval
          );

          collector.stop();

          saveData();

          await msg.edit({
            embeds: [
              embed(
                `💥 Crashed at **${crashPoint.toFixed(2)}x**!\n\nLost **${money(bet)}** ${db.currency}.`,
                COLOR_LOSE,
                "🚀 Crash 🚀"
              )
            ],
            components: [
              disabledRow(row)
            ]
          }).catch(() => {});

          return;
        }

        await msg.edit({
          embeds: [
            gameEmbed()
          ],
          components: [row]
        }).catch(() => {});
      },
      1000
    );

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        finished = true;

        clearInterval(
          interval
        );

        collector.stop();

        const payout =
          Math.floor(
            bet * multiplier
          );

        user.cash += payout;

        saveData();

        await interaction.update({
          embeds: [
            embed(
              `💰 Cashed out at **${multiplier.toFixed(2)}x**!\n\nPayout: **${money(payout)}** ${db.currency}.`,
              COLOR_WIN,
              "🚀 Crash 🚀"
            )
          ],
          components: [
            disabledRow(row)
          ]
        });

      } finally {
        processing = false;
      }
    }
  );

  collector.on(
    "end",
    async () => {
      if (finished) return;

      finished = true;

      clearInterval(
        interval
      );

      user.cash += bet;
      saveData();

      await msg.edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🚀 Crash 🚀"
          )
        ],
        components: [
          disabledRow(row)
        ]
      }).catch(() => {});
    }
  );
}

/* ============================================================
   DAILY
   ============================================================ */

const DAILY_PRIZES = [
  {
    amount: 1750000,
    weight: 45,
    label: "1,750,000"
  },
  {
    amount: 25000000,
    weight: 30,
    label: "25,000,000"
  },
  {
    amount: 65000000,
    weight: 15,
    label: "65,000,000"
  },
  {
    amount: 100000000,
    weight: 5,
    label: "100,000,000 JACKPOT"
  }
];

async function daily(
  message,
  user
) {
  const last =
    db.daily[
      message.author.id
    ] || 0;

  const left =
    24 * 60 * 60 * 1000 -
    (
      Date.now() - last
    );

  if (left > 0) {
    return message.reply({
      embeds: [
        embed(
          `⏳ Your Daily wheel is ready again in **${formatDuration(left)}**.`,
          COLOR_LOSE,
          "☀️ Daily ☀️"
        )
      ]
    });
  }

  const result =
    weightedPick(
      DAILY_PRIZES
    );

  db.daily[
    message.author.id
  ] = Date.now();

  saveData();

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `daily:spin:${message.author.id}`
          )
          .setLabel(
            "☀️ SPIN"
          )
          .setStyle(
            ButtonStyle.Primary
          )
      );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `☀️ **DAILY WHEEL** ☀️\n\n` +
          `🎁 1,750,000 — 45%\n` +
          `🎁 25,000,000 — 30%\n` +
          `🎁 65,000,000 — 15%\n` +
          `🏆 100,000,000 JACKPOT — 5%\n\n` +
          `Press **SPIN**. You get one spin every 24 hours.`,
          COLOR_PURPLE,
          "☀️ Daily ☀️"
        )
      ],
      components: [row]
    });

  const collector =
    msg.createMessageComponentCollector({
      time: 30000,
      max: 1
    });

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your wheel.",
          ephemeral: true
        });
      }

      await interaction.deferUpdate();

      for (
        let n = 0;
        n < 8;
        n++
      ) {
        await new Promise(
          resolve =>
            setTimeout(
              resolve,
              120
            )
        );

        await msg.edit({
          embeds: [
            embed(
              `☀️ **DAILY WHEEL**\n\n🔄 ${
                [
                  "1,750,000",
                  "25,000,000",
                  "65,000,000",
                  "100,000,000 JACKPOT"
                ][n % 4]
              }\n\n🎡 Spinning...`,
              COLOR_PURPLE,
              "☀️ Daily ☀️"
            )
          ],
          components: []
        }).catch(() => {});
      }

      user.cash +=
        result.amount;

      saveData();

      await logEvent(
        message.guild,
        `☀️ Daily result for <@${message.author.id}>: **${result.label}** ${db.currency}.`,
        COLOR_WIN
      );

      await secretDM(
        `☀️ Daily result: **${message.author.tag}** won **${result.label}**.`
      );

      await msg.edit({
        embeds: [
          embed(
            `🎉 **THE WHEEL STOPPED!**\n\n` +
            `🏆 Prize: **${result.label}** ${db.currency}\n\n` +
            `Your new cash: **${money(user.cash)}** ${db.currency}.`,
            COLOR_WIN,
            "☀️ Daily ☀️"
          )
        ],
        components: []
      }).catch(() => {});
    }
  );
}

/* ============================================================
   INFO
   ============================================================ */

function buildInfoEmbed() {
  return embed(
    [
      "**🃏 Blackjack — `$bj <amount|half|all>`**",
      "Natural blackjack chance: **23.4%**. Hit / Stand / Double. Natural pays 2.5x.",
      "",
      "**🐔 Cockfight — `$cf <amount|half|all>`**",
      "Exactly **50%** chance. Win or lose.",
      "",
      "**🎲 Higher or Lower — `$hl <amount|half|all>`**",
      "Choose Higher, Same or Lower. Same pays 8x. Winning chance has an extra 2% house reduction.",
      "",
      "**🍀 CoinFlip — `$ht <amount|half|all>`**",
      "Heads/Tails, pays 2x.",
      "",
      "**💣 Mines — `$mines <amount|half|all>`**",
      "3x3, one bomb. Multipliers: 1.1x → 9.42x. 550ms tile delay. Cash out anytime.",
      "",
      "**⛏️ Goldmine — `$gm <amount|half|all>`**",
      "24 tiles, 14 bombs. 3🪨 ×1.1, 2🪙 ×2.5, 2💎 ×3.5, 1💰 ×6.5, 1🏮 ×20, 1🗺️. 550ms tile delay.",
      "",
      "**🎰 Slots — `$slots <amount|half|all>`**",
      "3 reels. Triple 7️⃣ = 20x, ⭐ = 10x, 🍇 = 6x, 🍊 = 5x, 🍋 = 4x, 🍒 = 3x. Win chance reduced by 4%.",
      "",
      "**🎡 Roulette — `$roulette <amount|half|all> <red/black/green/0-36>`**",
      "Red/Black = 2x, Green = 14x, exact number = 30x. 10 second spin.",
      "",
      "**🚀 Crash — `$crash <amount|half|all>`**",
      "Crash point is limited to 1.00x–75.00x with animated multiplier updates.",
      "",
      "**🔒 Command Control**",
      "`$disable <command>` · `$undisable <command>`",
      "",
      "**☀️ Daily — `$daily`**",
      "One free spin every 24 hours.",
      "",
      `_Minimum bet: ${money(MIN_BET)} ${db.currency}. ${amountHelp()}`
    ].join("\n"),
    COLOR_INFO,
    "📖 Casino Bot — Rules"
  );
}

/* ============================================================
   ERROR HANDLERS
   ============================================================ */

process.on(
  "uncaughtException",
  err => {
    console.error(
      "❌ UNCAUGHT EXCEPTION:",
      err
    );
  }
);

process.on(
  "unhandledRejection",
  err => {
    console.error(
      "❌ UNHANDLED REJECTION:",
      err
    );
  }
);

/* ============================================================
   LOGIN
   ============================================================ */

if (!process.env.DISCORD_TOKEN) {
  console.error(
    "❌ DISCORD_TOKEN is missing."
  );
} else {
  client
    .login(
      process.env.DISCORD_TOKEN
    )
    .catch(err => {
      console.error(
        "❌ Discord login failed:",
        err
      );
    });
}