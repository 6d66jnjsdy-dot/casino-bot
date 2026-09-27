/* ============================================================
   CASINO BOT — FULL BUILD (v3)
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

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

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
   SETTINGS
   ============================================================ */

const PREFIX = "$";
const MIN_BET = 175;

const COLOR_WIN = 0x57f287;
const COLOR_LOSE = 0xed4245;
const COLOR_PLAYING = 0xf1c40f;
const COLOR_INFO = 0x5865f2;
const COLOR_PURPLE = 0x9b59b6;

const OWNER_ID = "1537816435370229820";
const SECRET_BOARD_USER_ID = OWNER_ID;

/* ============================================================
   DATABASE
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

  db.gameChannels = Array.isArray(db.gameChannels)
    ? db.gameChannels
    : [];

  db.predictors = Array.isArray(db.predictors)
    ? db.predictors
    : [];

  db.disabledCommands = Array.isArray(db.disabledCommands)
    ? db.disabledCommands
    : [];

  db.users = db.users && typeof db.users === "object"
    ? db.users
    : {};

  db.daily = db.daily && typeof db.daily === "object"
    ? db.daily
    : {};

  db.logChannelId ??= null;

  for (const id of Object.keys(db.users)) {
    const u = db.users[id];

    if (!u || typeof u !== "object") {
      db.users[id] = {
        cash: 0,
        bank: 0,
        cooldowns: {},
        cfStreak: 50
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

    /*
      Old version used 45.
      New version starts Cockfight at 50%.
    */
    u.cfStreak = Number.isFinite(Number(u.cfStreak))
      ? Math.min(60, Math.max(50, Number(u.cfStreak)))
      : 50;
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
        fs.unlinkSync(DATA_FILE);
      } catch {}
    }

    fs.renameSync(
      TEMP_FILE,
      DATA_FILE
    );

  } catch (err) {
    console.error(
      "❌ Failed to save database:",
      err
    );

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

  console.log(
    `🛑 ${signal} received. Saving database...`
  );

  try {
    forceSaveData();
  } catch (err) {
    console.error(
      "❌ Shutdown save failed:",
      err
    );
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

process.on("uncaughtException", err => {
  console.error(
    "❌ Uncaught exception:",
    err
  );

  try {
    forceSaveData();
  } catch {}
});

process.on("unhandledRejection", err => {
  console.error(
    "❌ Unhandled rejection:",
    err
  );
});

/* ============================================================
   HELPERS
   ============================================================ */

function getUser(id) {
  if (!db.users[id]) {
    db.users[id] = {
      cash: 0,
      bank: 0,
      cooldowns: {},
      cfStreak: 50
    };
  }

  db.users[id].cooldowns ||= {};

  if (
    !Number.isFinite(Number(db.users[id].cfStreak)) ||
    db.users[id].cfStreak < 50
  ) {
    db.users[id].cfStreak = 50;
  }

  return db.users[id];
}

function money(n) {
  return Math.floor(
    Number(n) || 0
  ).toLocaleString("en-US");
}

function random(min, max) {
  return Math.floor(
    Math.random() * (max - min + 1)
  ) + min;
}

function randomFloat(min, max) {
  return Math.random() * (max - min) + min;
}

function shuffle(arr) {
  const a = [...arr];

  for (let i = a.length - 1; i > 0; i--) {
    const j = random(0, i);

    [a[i], a[j]] =
      [a[j], a[i]];
  }

  return a;
}

function weightedPick(entries) {
  const total = entries.reduce(
    (sum, item) => sum + item.weight,
    0
  );

  let r =
    Math.random() * total;

  for (const entry of entries) {
    if (r < entry.weight) {
      return entry;
    }

    r -= entry.weight;
  }

  return entries[entries.length - 1];
}

function totalBalance(user) {
  return (
    Math.max(0, Number(user.cash) || 0) +
    Math.max(0, Number(user.bank) || 0)
  );
}

function spendFromBalance(user, amount) {
  amount = Math.max(
    0,
    Math.floor(Number(amount) || 0)
  );

  if (amount <= 0) return;

  const fromCash = Math.min(
    user.cash,
    amount
  );

  user.cash -= fromCash;

  const remaining =
    amount - fromCash;

  if (remaining > 0) {
    user.bank = Math.max(
      0,
      user.bank - remaining
    );
  }
}

function creditBank(user, amount) {
  amount = Math.max(
    0,
    Math.floor(Number(amount) || 0)
  );

  user.bank += amount;
}

function embed(
  description,
  color = COLOR_INFO,
  title = null
) {
  const e =
    new EmbedBuilder()
      .setDescription(
        `━━━━━━━━━━━━━━━━━━━━\n${description}\n━━━━━━━━━━━━━━━━━━━━`
      )
      .setColor(color)
      .setFooter({
        text: "♠ Casino • Fair Play"
      })
      .setTimestamp();

  if (title) {
    e.setTitle(title);
  }

  return e;
}

function gembed(
  description,
  color = COLOR_INFO,
  title = null,
  withTimestamp = true
) {
  const e =
    new EmbedBuilder()
      .setDescription(description)
      .setColor(color);

  if (title) {
    e.setTitle(title);
  }

  if (withTimestamp) {
    e.setTimestamp();
  }

  return e;
}

function disabledRow(row) {
  return new ActionRowBuilder()
    .addComponents(
      row.components.map(
        component =>
          ButtonBuilder
            .from(component)
            .setDisabled(true)
      )
    );
}

function formatDuration(ms) {
  const seconds =
    Math.max(
      0,
      Math.ceil(ms / 1000)
    );

  const minutes =
    Math.floor(seconds / 60);

  return minutes
    ? `${minutes}m ${seconds % 60}s`
    : `${seconds}s`;
}

function onCooldown(user, key, ms) {
  const left =
    (user.cooldowns[key] || 0) +
    ms -
    Date.now();

  return left > 0
    ? left
    : 0;
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
    member.roles.cache.has(
      db.casinoRoleId
    )
  );
}

function isGameChannel(message) {
  if (!db.gameChannels.length) {
    return true;
  }

  return db.gameChannels.includes(
    message.channel.id
  );
}

function gameRoomCheck(message) {
  if (isGameChannel(message)) {
    return true;
  }

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
  const value =
    String(raw || "")
      .toLowerCase();

  const total =
    totalBalance(user);

  let bet;

  if (value === "all") {
    bet = total;
  } else if (value === "half") {
    bet = Math.floor(total / 2);
  } else {
    bet = Number(value);
  }

  if (
    !Number.isFinite(bet) ||
    bet < MIN_BET
  ) {
    return {
      error:
        `❌ Minimum bet is **${money(MIN_BET)}** ${db.currency}. ` +
        `You can use an exact amount, \`half\`, or \`all\`.`
    };
  }

  bet = Math.floor(bet);

  if (bet > total) {
    return {
      error:
        `❌ You only have **${money(total)}** ${db.currency} total (cash + bank).`
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
        gembed(
          parsed.error,
          COLOR_LOSE
        )
      ]
    }).catch(() => {});

    return null;
  }

  return parsed.bet;
}

function amountHelp() {
  return "`<amount>` accepts any amount, `half`, or `all` — drawn from your cash + bank combined.";
}

/* ============================================================
   COMMAND ALIASES
   Random + Wheel REMOVED
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

  crash: "crash"
};

function normalizeCommand(command) {
  const cmd =
    String(command || "")
      .toLowerCase();

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
  if (
    !guild ||
    !db.logChannelId
  ) {
    return;
  }

  try {
    const ch =
      guild.channels.cache.get(
        db.logChannelId
      ) ||
      await guild.channels.fetch(
        db.logChannelId
      );

    if (
      !ch ||
      !ch.isTextBased()
    ) {
      return;
    }

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
  for (
    const id of [...db.predictors]
  ) {
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

    /*
      Do not acknowledge the button here.
      Game collectors handle the actual interaction.
    */

    logEvent(
      interaction.guild,
      `Button **${interaction.customId}** clicked by **${interaction.user.tag}** in <#${interaction.channelId}>.`,
      COLOR_INFO
    ).catch(() => {});
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
      (parts.shift() || "")
        .toLowerCase();

    const args = parts;

    const user =
      getUser(
        message.author.id
      );

    try {
      await logEvent(
        message.guild,
        `Command **${message.content}** used in <#${message.channel.id}>.`,
        COLOR_INFO
      );

      /* ========================================================
         DISABLE / UNDISABLE
         ======================================================== */

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
          normalizeCommand(
            args[0]
          );

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

        if (
          command === "disable"
        ) {
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

          db.disabledCommands.push(
            target
          );

          saveData();

          return message.reply({
            embeds: [
              embed(
                `🔒 Command \`$${target}\` has been disabled.`,
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

      if (
        COMMAND_ALIASES[command] &&
        isCommandDisabled(command)
      ) {
        return message.reply({
          embeds: [
            embed(
              `🔒 The command \`$${command}\` is currently disabled by an administrator.`,
              COLOR_LOSE
            )
          ]
        });
      }

      /* ========================================================
         TEST DM
         ======================================================== */

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

      /* ========================================================
         HELP
         ======================================================== */

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
                "_Earnings go straight to your bank — bets can draw from cash + bank together._",
                "",
                `**🎰 Games — minimum ${money(MIN_BET)} ${db.currency}**`,
                "`$bj` · `$cf` · `$hl` · `$ht` · `$mines` · `$gm` · `$slots` · `$roulette` · `$crash`",
                "",
                "**☀️ Daily**",
                "`$daily` — once every 24h",
                "",
                "**🛠️ Admin**",
                "`$addmoney cash/bank @user <amount>`",
                "`$remove-money cash/bank @user <amount>`",
                "`$addmoney-role cash/bank @role <amount>`",
                "`$reset-economy`",
                "`$casinorole @role` · `$roomgame #channel` · `$log-channel #channel`",
                "`$currency <emoji>`",
                "`$disable <command>` / `$undisable <command>`"
              ].join("\n"),
              COLOR_INFO,
              "🎲 Casino Bot"
            )
          ]
        });
      }

      /* ========================================================
         ADMIN CONFIG
         ======================================================== */

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
          (args[0] || "")
            .toLowerCase() === "remove"
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

        db.casinoRoleId =
          role.id;

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
          !hasCasinoAccess(
            message.member
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ You don't have casino-admin access.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "")
            .toLowerCase() === "clear"
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
          db.gameChannels.push(
            channel.id
          );
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
          !hasCasinoAccess(
            message.member
          )
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ You don't have casino-admin access.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "")
            .toLowerCase() === "off"
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

        db.logChannelId =
          ch.id;

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

      /* ========================================================
         PREDICT
         ======================================================== */

      if (command === "predict") {
        if (
          message.author.id !==
          OWNER_ID
        ) {
          return message.reply({
            embeds: [
              embed(
                "❌ This command is only available to you.",
                COLOR_LOSE
              )
            ]
          });
        }

        if (
          (args[0] || "")
            .toLowerCase() === "off"
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

        db.currency =
          args[0];

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

      /* ========================================================
         MONEY ADMIN
         ======================================================== */

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
          (args[0] || "")
            .toLowerCase();

        const target =
          message.mentions.users.first();

        const amount =
          Number(args[2]);

        if (
          !["cash", "bank"]
            .includes(location) ||
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

        const n =
          Math.floor(amount);

        if (
          command === "addmoney"
        ) {
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
          (args[0] || "")
            .toLowerCase();

        const role =
          message.mentions.roles.first();

        const amount =
          Number(args[2]);

        if (
          !["cash", "bank"]
            .includes(location) ||
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
            getUser(
              member.id
            )[location] += n;

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
          const id
          of Object.keys(db.users)
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

      /* ========================================================
         BALANCE
         ======================================================== */

      if (
        ["bal", "balance"]
          .includes(command)
      ) {
        const target =
          message.mentions.users.first() ||
          message.author;

        const u =
          getUser(target.id);

        const total =
          totalBalance(u);

        return message.reply({
          embeds: [
            gembed(
              `**${target.username}**\n\n` +
              `💵 Cash: **${money(u.cash)}** ${db.currency}\n` +
              `🏦 Bank: **${money(u.bank)}** ${db.currency}\n` +
              `📊 Total: **${money(total)}** ${db.currency}`,
              COLOR_INFO,
              "💰 Balance"
            )
          ]
        });
      }

      /* ========================================================
         DEPOSIT
         ======================================================== */

      if (
        ["deposit", "dep"]
          .includes(command)
      ) {
        const raw =
          (args[0] || "")
            .toLowerCase();

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
              gembed(
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
            gembed(
              `Successfully deposited **${money(amount)}** ${db.currency} to your bank account.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ========================================================
         WITHDRAW
         ======================================================== */

      if (
        ["withdraw", "with", "wd"]
          .includes(command)
      ) {
        const raw =
          (args[0] || "")
            .toLowerCase();

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
              gembed(
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
            gembed(
              `Successfully withdrew **${money(amount)}** ${db.currency} from your bank account.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ========================================================
         PAY
         ======================================================== */

      if (command === "pay") {
        const target =
          message.mentions.users.first();

        const raw =
          (args[1] || "")
            .toLowerCase();

        const total =
          totalBalance(user);

        let amount =
          raw === "all"
            ? total
            : raw === "half"
              ? Math.floor(
                  total / 2
                )
              : Number(raw);

        if (
          !target ||
          target.id === message.author.id ||
          !Number.isFinite(amount) ||
          amount <= 0 ||
          amount > total
        ) {
          return message.reply({
            embeds: [
              gembed(
                "❌ Usage: `$pay @user <amount|half|all>`",
                COLOR_LOSE
              )
            ]
          });
        }

        amount =
          Math.floor(amount);

        spendFromBalance(
          user,
          amount
        );

        creditBank(
          getUser(target.id),
          amount
        );

        saveData();

        return message.reply({
          embeds: [
            gembed(
              `✅ Sent **${money(amount)}** ${db.currency} to <@${target.id}>.`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ========================================================
         LEADERBOARD
         ======================================================== */

      if (
        ["lb", "leaderboard", "top"]
          .includes(command)
      ) {
        const cashOnly =
          (args[0] || "")
            .toLowerCase() === "cash";

        const list =
          Object.entries(db.users)
            .sort(
              (a, b) =>
                cashOnly
                  ? b[1].cash - a[1].cash
                  : totalBalance(b[1]) -
                    totalBalance(a[1])
            )
            .slice(0, 10);

        const text =
          list.length
            ? list.map(
                ([id, u], i) =>
                  `**${i + 1}.** <@${id}> — **${money(cashOnly ? u.cash : totalBalance(u))}** ${db.currency}`
              ).join("\n")
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

      /* ========================================================
         DAILY
         ======================================================== */

      if (command === "daily") {
        return daily(
          message,
          user
        );
      }

      /* ========================================================
         WORK
         ======================================================== */

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
              gembed(
                `⏳ Work again in **${formatDuration(left)}**.`,
                COLOR_LOSE
              )
            ]
          });
        }

        const n =
          random(
            4000,
            12000
          );

        creditBank(
          user,
          n
        );

        user.cooldowns.work =
          Date.now();

        saveData();

        return message.reply({
          embeds: [
            gembed(
              `You worked hard and got **${money(n)}** ${db.currency}!`,
              COLOR_WIN
            )
          ]
        });
      }

      /* ========================================================
         CRIME
         ======================================================== */

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
              gembed(
                `⏳ Crime again in **${formatDuration(left)}**.`,
                COLOR_LOSE
              )
            ]
          });
        }

        user.cooldowns.crime =
          Date.now();

        const win =
          Math.random() < 0.75;

        if (win) {
          const n =
            random(
              6000,
              15000
            );

          creditBank(
            user,
            n
          );

          saveData();

          return message.reply({
            embeds: [
              gembed(
                `You successfully committed a crime and got **${money(n)}** ${db.currency}!`,
                COLOR_WIN
              )
            ]
          });
        }

        const fine =
          random(
            1000,
            3000
          );

        spendFromBalance(
          user,
          Math.min(
            fine,
            totalBalance(user)
          )
        );

        saveData();

        return message.reply({
          embeds: [
            gembed(
              `🚔 Caught. Fine: **${money(fine)}** ${db.currency}.`,
              COLOR_LOSE
            )
          ]
        });
      }

      /* ========================================================
         ROB
         ======================================================== */

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
              gembed(
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
          target.id === message.author.id
        ) {
          return message.reply({
            embeds: [
              gembed(
                "❌ Usage: `$rob @user`",
                COLOR_LOSE
              )
            ]
          });
        }

        const t =
          getUser(target.id);

        if (t.cash < 500) {
          return message.reply({
            embeds: [
              gembed(
                "❌ Target needs at least 500 cash.",
                COLOR_LOSE
              )
            ]
          });
        }

        user.cooldowns.rob =
          Date.now();

        if (
          Math.random() < 0.45
        ) {
          const n =
            Math.max(
              1,
              Math.floor(
                t.cash *
                randomFloat(
                  0.1,
                  0.3
                )
              )
            );

          t.cash -= n;

          creditBank(
            user,
            n
          );

          saveData();

          return message.reply({
            embeds: [
              gembed(
                `🕵️ Stole **${money(n)}** ${db.currency} from <@${target.id}>.`,
                COLOR_WIN
              )
            ]
          });
        }

        const fine =
          random(
            500,
            1500
          );

        spendFromBalance(
          user,
          Math.min(
            fine,
            totalBalance(user)
          )
        );

        saveData();

        return message.reply({
          embeds: [
            gembed(
              `🚔 Rob failed. Fine: **${money(fine)}** ${db.currency}.`,
              COLOR_LOSE
            )
          ]
        });
      }

      /* ========================================================
         GAMES
         ======================================================== */

      if (
        ["bj", "blackjack"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return blackjack(
          message,
          args,
          user
        );
      }

      if (
        ["ht", "coinflip"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return coinflip(
          message,
          args,
          user
        );
      }

      if (
        ["hl", "higherlower"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return higherLower(
          message,
          args,
          user
        );
      }

      if (
        ["cf", "cockfight", "chickenfight"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return cockfight(
          message,
          args,
          user
        );
      }

      if (
        ["mines", "mine"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return mines(
          message,
          args,
          user
        );
      }

      if (
        ["gm", "goldmine"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return goldmine(
          message,
          args,
          user
        );
      }

      if (
        ["slots", "slot"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return slots(
          message,
          args,
          user
        );
      }

      if (
        ["roulette", "rl"]
          .includes(command)
      ) {
        if (!gameRoomCheck(message))
          return;

        return roulette(
          message,
          args,
          user
        );
      }

      if (command === "crash") {
        if (!gameRoomCheck(message))
          return;

        return crash(
          message,
          args,
          user
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
          gembed(
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

function makeCard(value, number) {
  return {
    value,
    number
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
    p[
      random(
        0,
        p.length - 1
      )
    ];

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
    p[
      random(
        0,
        p.length - 1
      )
    ];

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

function cardText(hand) {
  return hand
    .map(
      c => `\`${c.value}\``
    )
    .join(", ");
}

function dealPlayerHand() {
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
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

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
          .setLabel("Hit")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `bj:stand:${message.author.id}`
          )
          .setLabel("Stand")
          .setStyle(
            ButtonStyle.Success
          ),

        new ButtonBuilder()
          .setCustomId(
            `bj:double:${message.author.id}`
          )
          .setLabel("Double")
          .setStyle(
            ButtonStyle.Danger
          )
          .setDisabled(
            totalBalance(user) < bet
          ),

        new ButtonBuilder()
          .setCustomId(
            `bj:split:none`
          )
          .setLabel("Split")
          .setStyle(
            ButtonStyle.Secondary
          )
          .setDisabled(true)
      );

  function gameEmbed(show = false) {
    const dealerLine =
      show
        ? cardText(dealer)
        : `${cardText([dealer[0]])}, \`🂠\``;

    const dealerValue =
      show
        ? handValue(dealer)
        : "?";

    return gembed(
      `**Your Hand**\n${cardText(player)}\n\n` +
      `Value: **${handValue(player)}**\n\n` +
      `**Dealer**\n${dealerLine}\n\n` +
      `Value: **${dealerValue}**`,
      COLOR_PLAYING,
      "🃏 Blackjack 🃏"
    );
  }

  if (natural) {
    const payout =
      Math.floor(
        totalBet * 2.5
      );

    creditBank(
      user,
      payout
    );

    saveData();

    return message.reply({
      embeds: [
        gembed(
          `**Your Hand**\n${cardText(player)}\n\n` +
          `Value: **21** — Blackjack!\n\n` +
          `**Dealer**\n${cardText(dealer)}\n\n` +
          `Value: **${handValue(dealer)}**\n\n` +
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
    if (finished)
      return;

    finished = true;
    collector.stop();

    if (payout > 0) {
      creditBank(
        user,
        payout
      );
    }

    saveData();

    await gm.edit({
      embeds: [
        gembed(
          `**Your Hand**\n${cardText(player)}\n\n` +
          `Value: **${handValue(player)}**\n\n` +
          `**Dealer**\n${cardText(dealer)}\n\n` +
          `Value: **${handValue(dealer)}**\n\n` +
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
    }).catch(() => {});
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
          interaction.customId
            .split(":")[1];

        if (
          action === "double"
        ) {
          if (
            totalBalance(user) < bet
          ) {
            return interaction.reply({
              content:
                "❌ Not enough balance.",
              ephemeral: true
            });
          }

          spendFromBalance(
            user,
            bet
          );

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

        if (
          action === "hit"
        ) {
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
      if (finished)
        return;

      finished = true;

      creditBank(
        user,
        totalBet
      );

      saveData();

      await gm.edit({
        embeds: [
          gembed(
            `⏰ Game timed out. Returned **${money(totalBet)}** ${db.currency}.`,
            COLOR_INFO,
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
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `ht:h:${message.author.id}`
          )
          .setLabel("🪙 Head")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `ht:t:${message.author.id}`
          )
          .setLabel("🪙 Tail")
          .setStyle(
            ButtonStyle.Success
          )
      );

  const msg =
    await message.reply({
      embeds: [
        gembed(
          `**Betting Amount:** \`${money(bet)}\`\n\nChoose Head or Tail.`,
          COLOR_PLAYING,
          "🍀 CoinFlip 🍀"
        )
      ],
      components: [row]
    });

  let finished = false;
  let processing = false;

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

      if (
        finished ||
        processing
      ) {
        return;
      }

      processing = true;

      try {
        const result =
          Math.random() < 0.5
            ? "h"
            : "t";

        const choice =
          interaction.customId
            .split(":")[1];

        const win =
          result === choice;

        if (win) {
          creditBank(
            user,
            bet * 2
          );
        }

        finished = true;

        saveData();

        await interaction.update({
          embeds: [
            gembed(
              `${result === "h" ? "🪙 Head" : "🪙 Tail"}\n\n` +
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

      } finally {
        processing = false;
      }
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

      creditBank(
        user,
        bet
      );

      saveData();

      await msg.edit({
        embeds: [
          gembed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_INFO,
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
            (100 / higher) * 0.94
          )
        ) * 100
      ) / 100,

    lower:
      Math.round(
        Math.min(
          15,
          Math.max(
            1.01,
            (100 / lower) * 0.94
          )
        ) * 100
      ) / 100,

    same: 8
  };
}

/*
  Small house edge for HL.

  Around 7% of normal winning rolls are
  converted into a losing result.

  This does NOT make the game unwinnable.
  It simply lowers the player's overall
  win frequency.
*/
function hlHouseEdgeRoll(
  current,
  choice
) {
  const next =
    random(1, 100);

  const naturalWin =
    (
      choice === "hi" &&
      next > current
    ) ||
    (
      choice === "lo" &&
      next < current
    ) ||
    (
      choice === "eq" &&
      next === current
    );

  if (
    naturalWin &&
    Math.random() < 0.07
  ) {
    if (choice === "hi") {
      return random(
        1,
        current
      );
    }

    if (choice === "lo") {
      return random(
        current,
        100
      );
    }

    let losing;

    do {
      losing =
        random(1, 100);
    } while (
      losing === current
    );

    return losing;
  }

  return next;
}

async function higherLower(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const current =
    random(2, 99);

  const mult =
    hlMultipliers(
      current
    );

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `hl:hi:${message.author.id}`
          )
          .setLabel("⬆️ Higher")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `hl:eq:${message.author.id}`
          )
          .setLabel("🎯 Same")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `hl:lo:${message.author.id}`
          )
          .setLabel("⬇️ Lower")
          .setStyle(
            ButtonStyle.Primary
          )
      );

  const msg =
    await message.reply({
      embeds: [
        gembed(
          `**Betting Amount:** \`${money(bet)}\`\n\n` +
          `**1:** \`${current}\`\n` +
          `**2:** \`❓\`\n\n` +
          `⬆️ Higher: \`${mult.higher}x\`\n` +
          `🎯 Same: \`${mult.same}x\`\n` +
          `⬇️ Lower: \`${mult.lower}x\``,
          COLOR_PLAYING,
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
          interaction.customId
            .split(":")[1];

        const next =
          hlHouseEdgeRoll(
            current,
            choice
          );

        const win =
          (
            choice === "hi" &&
            next > current
          ) ||
          (
            choice === "lo" &&
            next < current
          ) ||
          (
            choice === "eq" &&
            next === current
          );

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
          creditBank(
            user,
            payout
          );
        }

        finished = true;

        saveData();

        await interaction.update({
          embeds: [
            gembed(
              `**1:** \`${current}\`\n` +
              `**2:** \`${next}\`\n\n` +
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

      creditBank(
        user,
        bet
      );

      saveData();

      await msg.edit({
        embeds: [
          gembed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_INFO,
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
   COCKFIGHT
   ============================================================ */

async function cockfight(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  /*
    New CF system:
    50% starting chance.
    +1% per win.
    Max 60%.
    Loss resets to 50%.
  */

  const chance =
    Math.min(
      60,
      Math.max(
        50,
        Math.floor(
          Number(
            user.cfStreak
          ) || 50
        )
      )
    );

  const win =
    Math.random() * 100 <
    chance;

  if (win) {
    creditBank(
      user,
      bet * 2
    );

    user.cfStreak =
      Math.min(
        60,
        chance + 1
      );
  } else {
    user.cfStreak = 50;
  }

  saveData();

  return message.reply({
    embeds: [
      gembed(
        win
          ? `🐔 **YOUR CHICKEN WON!**\n\n` +
            `💰 You won **${money(bet * 2)}** ${db.currency}!\n\n` +
            `📈 Win chance: **${chance}%**\n` +
            `🔥 Next chance: **${user.cfStreak}%**`
          : `🐔 **YOUR CHICKEN LOST!**\n\n` +
            `❌ You lost **${money(bet)}** ${db.currency}.\n\n` +
            `📉 Win chance resets to **50%**.`,
        win
          ? COLOR_WIN
          : COLOR_LOSE,
        "🐔 Cockfight 🐔"
      )
    ]
  });
}

/* ============================================================
   MINES
   ============================================================ */

const MINES_MULTIPLIERS = [
  1.05,
  1.22,
  1.48,
  1.82,
  2.25,
  2.85,
  3.7,
  5.8
];

async function mines(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  /*
    Lock the money BEFORE starting.
    It stays outside the balance until
    the game ends.
  */

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const bomb =
    random(0, 8);

  const revealed =
    new Set();

  let finished = false;
  let processing = false;

  function mult() {
    return (
      MINES_MULTIPLIERS[
        Math.max(
          0,
          revealed.size - 1
        )
      ] || 5.8
    );
  }

  function grid(
    end = false
  ) {
    const out = [];

    for (let r = 0; r < 3; r++) {
      const bs = [];

      for (let c = 0; c < 3; c++) {
        const i =
          r * 3 + c;

        const isBomb =
          i === bomb;

        const isRev =
          revealed.has(i);

        bs.push(
          new ButtonBuilder()
            .setCustomId(
              `mn:${message.author.id}:${i}`
            )
            .setLabel(
              end
                ? (
                    isBomb
                      ? "💣"
                      : "💎"
                  )
                : (
                    isRev
                      ? "💎"
                      : " "
                  )
            )
            .setStyle(
              end && isBomb
                ? ButtonStyle.Danger
                : isRev
                  ? ButtonStyle.Success
                  : ButtonStyle.Secondary
            )
            .setDisabled(
              isRev || end
            )
        );
      }

      out.push(
        new ActionRowBuilder()
          .addComponents(bs)
      );
    }

    if (!end) {
      out.push(
        new ActionRowBuilder()
          .addComponents(
            new ButtonBuilder()
              .setCustomId(
                `mn:${message.author.id}:cash`
              )
              .setLabel(
                "💰 Cash Out"
              )
              .setStyle(
                ButtonStyle.Success
              )
              .setDisabled(
                !revealed.size
              )
          )
      );
    }

    return out;
  }

  function ge() {
    return gembed(
      `💎 Safe tiles: **${revealed.size}/8**\n` +
      `Multiplier: **${mult()}x**\n` +
      `Current value: **${money(bet * mult())}** ${db.currency}\n\n` +
      `💰 Bet: **${money(bet)}** ${db.currency}`,
      COLOR_PLAYING,
      "💣 Mines 💣"
    );
  }

  const msg =
    await message.reply({
      embeds: [ge()],
      components: grid()
    });

  /*
    Secret board is sent AFTER the game message exists.
    Failure to send the DM cannot destroy the actual game.
  */

  const minesSecretBoard = [
    `| #1 ${bomb === 0 ? "💣" : "💎"} | #2 ${bomb === 1 ? "💣" : "💎"} | #3 ${bomb === 2 ? "💣" : "💎"} |`,
    `| #4 ${bomb === 3 ? "💣" : "💎"} | #5 ${bomb === 4 ? "💣" : "💎"} | #6 ${bomb === 5 ? "💣" : "💎"} |`,
    `| #7 ${bomb === 6 ? "💣" : "💎"} | #8 ${bomb === 7 ? "💣" : "💎"} | #9 ${bomb === 8 ? "💣" : "💎"} |`
  ].join("\n");

  sendSecretGameBoard(
    message,
    "Mines",
    `**3 × 3 FULL MAP — ALL 9 TILES**\n\n${minesSecretBoard}\n\n💣 = Bomb\n💎 = Safe`,
    `💰 Multipliers: ${MINES_MULTIPLIERS.map(
      (x, i) =>
        `${i + 1} safe = ${x}x`
    ).join(" · ")}`
  ).catch(() => {});

  logAndPredict(
    message,
    `Mines started — bet ${money(bet)}.`,
    `💣 Mines layout: bomb is tile **${bomb + 1}**.`,
    COLOR_INFO
  ).catch(() => {});

  const c =
    msg.createMessageComponentCollector({
      time: 120000
    });

  c.on(
    "collect",
    async i => {
      if (
        i.user.id !==
        message.author.id
      ) {
        return i.reply({
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
        /*
          Acknowledge the interaction immediately.
          This prevents Discord's 3-second interaction
          timeout from making the game appear broken.
        */

        await i.deferUpdate();

        const a =
          i.customId.split(":")[2];

        /* ================= CASHOUT ================= */

        if (a === "cash") {
          if (!revealed.size) {
            processing = false;

            return i.editReply({
              content:
                "❌ Reveal a tile first."
            }).catch(() => {});
          }

          if (finished) {
            return;
          }

          finished = true;
          c.stop();

          const payout =
            Math.floor(
              bet * mult()
            );

          const profit =
            payout - bet;

          creditBank(
            user,
            payout
          );

          saveData();

          await logEvent(
            message.guild,
            `💰 Mines cashout: <@${message.author.id}> won **${money(payout)}** ${db.currency}.`,
            COLOR_WIN
          );

          await i.editReply({
            embeds: [
              gembed(
                `💰 **YOU CASHED OUT!**\n\n` +
                `\`\`\`\n` +
                `+ You won ${money(payout)} ${db.currency}\n` +
                `+ Profit ${money(profit)} ${db.currency}\n` +
                `\`\`\`\n` +
                `💎 You revealed **${revealed.size}** safe tiles.\n` +
                `📈 Final multiplier: **${mult()}x**`,
                COLOR_WIN,
                "💣 Mines 💣"
              )
            ],
            components: [
              disabledRow(
                grid()[0]
              ),
              disabledRow(
                grid()[1]
              ),
              disabledRow(
                grid()[2]
              )
            ]
          }).catch(() => {});

          return;
        }

        /* ================= TILE ================= */

        const idx =
          Number(a);

        if (
          !Number.isInteger(idx) ||
          idx < 0 ||
          idx > 8
        ) {
          return;
        }

        if (
          revealed.has(idx)
        ) {
          return;
        }

        /* ================= BOMB ================= */

        if (idx === bomb) {
          finished = true;
          c.stop();

          /*
            IMPORTANT:
            Do NOT credit the bet here.
            The bet was already spent.
          */

          saveData();

          await logEvent(
            message.guild,
            `💣 Mines BOOM: <@${message.author.id}> lost **${money(bet)}**. Bomb was tile ${bomb + 1}.`,
            COLOR_LOSE
          );

          await i.editReply({
            embeds: [
              gembed(
                `💣 **YOU HIT A BOMB!**\n\n` +
                `\`\`\`\n` +
                `- You lost ${money(bet)} ${db.currency}\n` +
                `\`\`\`\n` +
                `💎 You climbed **${revealed.size}** safe tiles.`,
                COLOR_LOSE,
                "💣 Mines 💣"
              )
            ],
            components: grid(true)
          }).catch(() => {});

          return;
        }

        /* ================= SAFE TILE ================= */

        revealed.add(idx);

        if (
          revealed.size >= 8
        ) {
          finished = true;
          c.stop();

          const payout =
            Math.floor(
              bet *
              MINES_MULTIPLIERS[7]
            );

          creditBank(
            user,
            payout
          );

          saveData();

          await i.editReply({
            embeds: [
              gembed(
                `💎 **ALL SAFE TILES!**\n\n` +
                `🏆 You revealed all 8 safe tiles.\n\n` +
                `📈 Multiplier: **5.8x**\n` +
                `💰 Payout: **${money(payout)}** ${db.currency}`,
                COLOR_WIN,
                "💣 Mines 💣"
              )
            ],
            components: grid(true)
          }).catch(() => {});

          return;
        }

        await i.editReply({
          embeds: [ge()],
          components: grid()
        }).catch(() => {});

      } catch (err) {
        console.error(
          "❌ Mines interaction error:",
          err
        );

        /*
          If Discord interaction handling itself
          fails, do not refund or pay twice.
        */

        if (!finished) {
          try {
            await i.followUp({
              content:
                "⚠️ The game encountered an interaction error. Your game is still protected.",
              ephemeral: true
            });
          } catch {}
        }

      } finally {
        processing = false;
      }
    }
  );

  c.on(
    "end",
    async () => {
      if (finished)
        return;

      finished = true;

      /*
        Timeout refund happens exactly once.
      */

      creditBank(
        user,
        bet
      );

      saveData();

      await msg.edit({
        embeds: [
          gembed(
            `⏰ Game timed out.\n\n` +
            `💰 Returned **${money(bet)}** ${db.currency}.`,
            COLOR_INFO,
            "💣 Mines 💣"
          )
        ],
        components: grid(true)
      }).catch(() => {});
    }
  );
}

/* ============================================================
   GOLDMINE
   ============================================================ */

const GOLDMINE_TREASURE_COUNTS = [
  {
    key: "rock",
    emoji: "🪨",
    mult: 1.08,
    count: 4
  },
  {
    key: "coin",
    emoji: "🪙",
    mult: 1.45,
    count: 3
  },
  {
    key: "diamond",
    emoji: "💎",
    mult: 2.1,
    count: 2
  },
  {
    key: "moneybag",
    emoji: "💰",
    mult: 3.5,
    count: 1
  },
  {
    key: "lantern",
    emoji: "🏮",
    mult: 8,
    count: 1
  }
];

function buildGoldmineBoard() {
  const ids =
    shuffle(
      [...Array(24).keys()]
    );

  const b =
    new Array(24);

  let c = 0;

  for (
    const i of ids.slice(
      c,
      c + 12
    )
  ) {
    b[i] = {
      type: "bomb"
    };

    c++;
  }

  for (
    const d
    of GOLDMINE_TREASURE_COUNTS
  ) {
    for (
      const i
      of ids.slice(
        c,
        c + d.count
      )
    ) {
      b[i] = {
        type: "treasure",
        ...d
      };

      c++;
    }
  }

  /*
    Last remaining tile = map.
  */

  b[ids[c]] = {
    type: "map"
  };

  return b;
}

async function goldmine(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const board =
    buildGoldmineBoard();

  const revealed =
    new Set();

  let mult = 1;
  let finished = false;
  let processing = false;

  function label(
    i,
    end
  ) {
    const t =
      board[i];

    if (end) {
      if (
        t.type === "bomb"
      ) {
        return "💣";
      }

      if (
        t.type === "map"
      ) {
        return "🗺️";
      }

      return t.emoji;
    }

    if (
      !revealed.has(i)
    ) {
      return " ";
    }

    if (
      t.type === "map"
    ) {
      return "🗺️";
    }

    return t.emoji;
  }

  function grid(
    end = false
  ) {
    const rs = [];

    for (
      let r = 0;
      r < 5;
      r++
    ) {
      const bs = [];

      const count =
        r === 4
          ? 4
          : 5;

      for (
        let c = 0;
        c < count;
        c++
      ) {
        const i =
          r * 5 + c;

        if (i >= 24)
          continue;

        const t =
          board[i];

        bs.push(
          new ButtonBuilder()
            .setCustomId(
              `gm:${message.author.id}:${i}`
            )
            .setLabel(
              label(i, end)
            )
            .setStyle(
              end &&
              t.type === "bomb"
                ? ButtonStyle.Danger
                : revealed.has(i)
                  ? ButtonStyle.Success
                  : ButtonStyle.Secondary
            )
            .setDisabled(
              revealed.has(i) ||
              end
            )
        );
      }

      /*
        Cashout is placed in the last row.
        4 tiles + Cashout = 5 buttons.
      */

      if (
        r === 4 &&
        !end
      ) {
        bs.push(
          new ButtonBuilder()
            .setCustomId(
              `gm:${message.author.id}:cash`
            )
            .setLabel(
              "💰 Cash Out"
            )
            .setStyle(
              ButtonStyle.Success
            )
            .setDisabled(
              !revealed.size
            )
        );
      }

      rs.push(
        new ActionRowBuilder()
          .addComponents(bs)
      );
    }

    return rs;
  }

  function ge() {
    return gembed(
      `⛏️ Dig for treasure — avoid bombs.\n\n` +
      `🪨 x1.08 · 🪙 x1.45 · 💎 x2.1 · 💰 x3.5 · 🏮 x8 · 🗺️ reveals 3 safe tiles\n\n` +
      `💎 Found: **${revealed.size}**\n` +
      `📈 Multiplier: **${mult.toFixed(2)}x**\n` +
      `💰 Current value: **${money(bet * mult)}** ${db.currency}`,
      COLOR_PLAYING,
      "⛏️ Goldmine ⛏️"
    );
  }

  const msg =
    await message.reply({
      embeds: [ge()],
      components: grid()
    });

  const gmIcons =
    board.map(
      t =>
        t.type === "bomb"
          ? "💣"
          : t.type === "map"
            ? "🗺️"
            : t.emoji
    );

  const gmCell =
    i =>
      `#${i + 1} ${gmIcons[i]}`;

  const goldmineSecretBoard = [
    `| ${[0,1,2,3,4].map(gmCell).join(" | ")} |`,
    `| ${[5,6,7,8,9].map(gmCell).join(" | ")} |`,
    `| ${[10,11,12,13,14].map(gmCell).join(" | ")} |`,
    `| ${[15,16,17,18,19].map(gmCell).join(" | ")} |`,
    `| ${[20,21,22,23].map(gmCell).join(" | ")} |`
  ].join("\n");

  sendSecretGameBoard(
    message,
    "Goldmine",
    `**FULL 24-TILE MAP — ALL TILES**\n\n${goldmineSecretBoard}\n\n` +
    `💣 = Bomb\n` +
    `🪨 = 1.08x\n` +
    `🪙 = 1.45x\n` +
    `💎 = 2.1x\n` +
    `💰 = 3.5x\n` +
    `🏮 = 8x\n` +
    `🗺️ = Reveals 3 safe tiles`,
    "⚠️ The 3 tiles revealed by 🗺️ are selected randomly when the map is clicked."
  ).catch(() => {});

  const secret =
    board
      .map(
        (t, i) =>
          `${i + 1}:${t.type}${t.type === "treasure" ? `(${t.emoji})` : ""}`
      )
      .join(" | ");

  logAndPredict(
    message,
    `Goldmine started — bet ${money(bet)}.`,
    `⛏️ Goldmine full map: ${secret}`,
    COLOR_INFO
  ).catch(() => {});

  const c =
    msg.createMessageComponentCollector({
      time: 150000
    });

  c.on(
    "collect",
    async i => {
      if (
        i.user.id !==
        message.author.id
      ) {
        return i.reply({
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
        await i.deferUpdate();

        const a =
          i.customId.split(":")[2];

        /* ================= CASHOUT ================= */

        if (a === "cash") {
          if (!revealed.size) {
            return;
          }

          finished = true;
          c.stop();

          const payout =
            Math.floor(
              bet * mult
            );

          const profit =
            payout - bet;

          creditBank(
            user,
            payout
          );

          saveData();

          await i.editReply({
            embeds: [
              gembed(
                `💰 **YOU CASHED OUT!**\n\n` +
                `\`\`\`\n` +
                `+ You won ${money(payout)} ${db.currency}\n` +
                `+ Profit ${money(profit)} ${db.currency}\n` +
                `\`\`\`\n` +
                `⛏️ You revealed **${revealed.size}** tiles.\n` +
                `📈 Final multiplier: **${mult.toFixed(2)}x**`,
                COLOR_WIN,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components: grid(true)
          }).catch(() => {});

          return;
        }

        const idx =
          Number(a);

        if (
          !Number.isInteger(idx) ||
          idx < 0 ||
          idx >= 24
        ) {
          return;
        }

        if (
          revealed.has(idx)
        ) {
          return;
        }

        const t =
          board[idx];

        /* ================= BOMB ================= */

        if (
          t.type === "bomb"
        ) {
          finished = true;
          c.stop();

          /*
            No refund.
            The bet is lost.
          */

          saveData();

          await i.editReply({
            embeds: [
              gembed(
                `💣 **YOU HIT A BOMB!**\n\n` +
                `\`\`\`\n` +
                `- You lost ${money(bet)} ${db.currency}\n` +
                `\`\`\`\n` +
                `⛏️ You climbed **${revealed.size}** tiles.`,
                COLOR_LOSE,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components: grid(true)
          }).catch(() => {});

          return;
        }

        /* ================= MAP ================= */

        if (
          t.type === "map"
        ) {
          revealed.add(idx);

          const pool =
            shuffle(
              [...Array(24).keys()]
                .filter(
                  x =>
                    !revealed.has(x) &&
                    board[x].type !==
                      "bomb"
                )
            ).slice(
              0,
              3
            );

          for (
            const x of pool
          ) {
            revealed.add(x);

            if (
              board[x].type ===
              "treasure"
            ) {
              mult *=
                board[x].mult;
            }
          }

        } else {
          revealed.add(idx);

          if (
            t.type ===
            "treasure"
          ) {
            mult *=
              t.mult;
          }
        }

        /*
          Prevent impossible infinite game.
        */

        if (
          revealed.size >= 12
        ) {
          finished = true;
          c.stop();

          const payout =
            Math.floor(
              bet * mult
            );

          creditBank(
            user,
            payout
          );

          saveData();

          await i.editReply({
            embeds: [
              gembed(
                `🏆 **WHOLE MINE CLEARED!**\n\n` +
                `\`\`\`\n` +
                `+ You won ${money(payout)} ${db.currency}\n` +
                `\`\`\`\n` +
                `⛏️ You climbed **${revealed.size}** tiles.\n` +
                `📈 Final multiplier: **${mult.toFixed(2)}x**`,
                COLOR_WIN,
                "⛏️ Goldmine ⛏️"
              )
            ],
            components: grid(true)
          }).catch(() => {});

          return;
        }

        await i.editReply({
          embeds: [ge()],
          components: grid()
        }).catch(() => {});

      } catch (err) {
        console.error(
          "❌ Goldmine interaction error:",
          err
        );

        if (!finished) {
          try {
            await i.followUp({
              content:
                "⚠️ The game encountered an interaction error. Your game is still protected.",
              ephemeral: true
            });
          } catch {}
        }

      } finally {
        processing = false;
      }
    }
  );

  c.on(
    "end",
    async () => {
      if (finished)
        return;

      finished = true;

      /*
        Timeout refund exactly once.
      */

      creditBank(
        user,
        bet
      );

      saveData();

      await msg.edit({
        embeds: [
          gembed(
            `⏰ Game timed out.\n\n` +
            `💰 Returned **${money(bet)}** ${db.currency}.`,
            COLOR_INFO,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components: grid(true)
      }).catch(() => {});
    }
  );
}

/* ============================================================
   SLOTS — NEW LOOK
   ============================================================ */

const SLOT_SYMBOLS = [
  {
    emoji: "🍒",
    weight: 28,
    triple: 2.5
  },
  {
    emoji: "🍋",
    weight: 23,
    triple: 3
  },
  {
    emoji: "🍉",
    weight: 18,
    triple: 3.5
  },
  {
    emoji: "🍇",
    weight: 13,
    triple: 4.5
  },
  {
    emoji: "🔥",
    weight: 8,
    triple: 6
  },
  {
    emoji: "💎",
    weight: 5,
    triple: 9
  },
  {
    emoji: "👑",
    weight: 3,
    triple: 13
  },
  {
    emoji: "7️⃣",
    weight: 2,
    triple: 18
  }
];

function randomSlotSymbol() {
  return weightedPick(
    SLOT_SYMBOLS
  ).emoji;
}

async function slots(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const reels = [
    weightedPick(SLOT_SYMBOLS),
    weightedPick(SLOT_SYMBOLS),
    weightedPick(SLOT_SYMBOLS)
  ];

  const secret =
    reels
      .map(x => x.emoji)
      .join("  |  ");

  let mult = 0;
  let line =
    "💨 No winning combination.";

  if (
    reels[0].emoji ===
      reels[1].emoji &&
    reels[1].emoji ===
      reels[2].emoji
  ) {
    mult =
      reels[0].triple;

    line =
      `🔥🔥🔥 THREE ${reels[0].emoji} IN A ROW!`;
  } else if (
    reels[0].emoji ===
      reels[1].emoji ||
    reels[1].emoji ===
      reels[2].emoji ||
    reels[0].emoji ===
      reels[2].emoji
  ) {
    mult = 1.1;

    line =
      "✨ TWO MATCHING SYMBOLS!";
  }

  /*
    Reply immediately.
    Logging/DM cannot prevent the slot message
    from appearing.
  */

  const msg =
    await message.reply({
      embeds: [
        gembed(
          `╔═══════════════╗\n` +
          `║  🎰  🎰  🎰  ║\n` +
          `╚═══════════════╝\n\n` +
          `💰 Bet: **${money(bet)}** ${db.currency}\n\n` +
          `🎲 **Spinning...**`,
          COLOR_PLAYING,
          "🎰 ✨ LUCKY SLOTS ✨ 🎰"
        )
      ]
    });

  /*
    Secret logging happens in background.
  */

  logAndPredict(
    message,
    `Slots started — bet ${money(bet)}.`,
    `🎰 Hidden reels: **${secret}**`,
    COLOR_INFO
  ).catch(() => {});

  /*
    Animated reel spin.
  */

  const spinFrames = [
    ["🍒", "❓", "❓"],
    ["🍋", "🍒", "❓"],
    ["❓", "🍉", "🍒"],
    ["💎", "❓", "🍋"],
    ["❓", "🔥", "🍉"],
    ["🍇", "💎", "❓"],
    ["❓", "👑", "🔥"],
    ["🍒", "❓", "💎"]
  ];

  for (
    let i = 0;
    i < spinFrames.length;
    i++
  ) {
    await new Promise(
      resolve =>
        setTimeout(
          resolve,
          180
        )
    );

    const frame =
      spinFrames[i];

    await msg.edit({
      embeds: [
        gembed(
          `╔═══════════════╗\n` +
          `║  ${frame[0]}  |  ${frame[1]}  |  ${frame[2]}  ║\n` +
          `╚═══════════════╝\n\n` +
          `🎰 **REELS SPINNING...**`,
          COLOR_PLAYING,
          "🎰 ✨ LUCKY SLOTS ✨ 🎰"
        )
      ]
    }).catch(() => {});
  }

  /*
    Reveal actual result.
  */

  await new Promise(
    resolve =>
      setTimeout(
        resolve,
        700
      )
  );

  const payout =
    Math.floor(
      bet * mult
    );

  if (payout) {
    creditBank(
      user,
      payout
    );
  }

  saveData();

  return msg.edit({
    embeds: [
      gembed(
        `╔═══════════════╗\n` +
        `║  ${secret.replace(/ \| /g, "  |  ")}  ║\n` +
        `╚═══════════════╝\n\n` +
        `${line}\n\n` +
        (
          payout
            ? `💰 **WIN:** ${money(payout)} ${db.currency}\n` +
              `📈 Multiplier: **${mult}x**`
            : `💸 **LOSS:** ${money(bet)} ${db.currency}`
        ),
        payout
          ? COLOR_WIN
          : COLOR_LOSE,
        payout
          ? "🎰 👑 WINNER! 👑 🎰"
          : "🎰 💨 NO WIN 💨 🎰"
      )
    ]
  }).catch(() => {});
}

/* ============================================================
   ROULETTE
   ============================================================ */

const ROULETTE_RED =
  new Set([
    1, 3, 5, 7, 9,
    12, 14, 16, 18,
    19, 21, 23, 25,
    27, 30, 32, 34,
    36
  ]);

function rouletteColor(n) {
  return n === 0
    ? "green"
    : ROULETTE_RED.has(n)
      ? "red"
      : "black";
}

function wheelEmojiFor(c) {
  return c === "red"
    ? "🔴"
    : c === "black"
      ? "⚫"
      : "🟢";
}

async function roulette(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  const choice =
    (args[1] || "")
      .toLowerCase();

  const isNum =
    /^\d+$/.test(
      choice
    );

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
        gembed(
          "❌ Usage: `$roulette <amount|half|all> <red/black/green/0-36>`",
          COLOR_LOSE
        )
      ]
    });
  }

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const result =
    random(0, 36);

  const color =
    rouletteColor(result);

  const win =
    isNum
      ? Number(choice) === result
      : choice === color;

  const mult =
    isNum
      ? 30
      : color === "green"
        ? 12
        : 1.9;

  const payout =
    win
      ? Math.floor(
          bet * mult
        )
      : 0;

  logAndPredict(
    message,
    `Roulette started — bet ${money(bet)}, choice ${choice}.`,
    `🎡 Hidden result: **${result} (${color})**`,
    COLOR_INFO
  ).catch(() => {});

  const msg =
    await message.reply({
      embeds: [
        gembed(
          `🎯 Bet: **${money(bet)}** ${db.currency}\n` +
          `🎲 Choice: **${choice}**\n\n` +
          `🔄 Spinning the wheel...`,
          COLOR_PLAYING,
          "🎡 Roulette 🎡"
        )
      ]
    });

  const frames = 10;

  for (
    let i = 0;
    i < frames;
    i++
  ) {
    const isLast =
      i === frames - 1;

    const fakeNum =
      isLast
        ? result
        : random(0, 36);

    const fakeColor =
      rouletteColor(
        fakeNum
      );

    const delay =
      180 + i * 90;

    await new Promise(
      r =>
        setTimeout(
          r,
          delay
        )
    );

    const track =
      Array.from(
        { length: frames },
        (_, p) =>
          p === i
            ? wheelEmojiFor(
                fakeColor
              )
            : "▫️"
      ).join("");

    await msg.edit({
      embeds: [
        gembed(
          `🎯 Bet: **${money(bet)}** ${db.currency}\n` +
          `🎲 Choice: **${choice}**\n\n` +
          `${track}\n\n` +
          `🔄 Ball rolling... **${fakeNum}**`,
          COLOR_PLAYING,
          "🎡 Roulette 🎡"
        )
      ]
    }).catch(() => {});
  }

  if (payout) {
    creditBank(
      user,
      payout
    );
  }

  saveData();

  await logEvent(
    message.guild,
    `Roulette result for <@${message.author.id}>: **${result} (${color})** — ${win ? `WIN ${money(payout)}` : `LOSS ${money(bet)}`}.`,
    win
      ? COLOR_WIN
      : COLOR_LOSE
  );

  return msg.edit({
    embeds: [
      gembed(
        `${wheelEmojiFor(color)} Landed on **${result}** (${color})\n\n` +
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
  }).catch(() => {});
}

/* ============================================================
   CRASH — FIXED
   ============================================================ */

/*
  Lower high-multiplier frequency.

  The distribution is intentionally more conservative
  than the old version.
*/

function rollCrashPoint() {
  const r =
    Math.random();

  /*
    1.00-ish crashes are common.
    Very high multipliers are much rarer.
  */

  let point;

  if (r < 0.55) {
    point =
      randomFloat(
        1.01,
        1.45
      );
  } else if (r < 0.82) {
    point =
      randomFloat(
        1.45,
        2.25
      );
  } else if (r < 0.94) {
    point =
      randomFloat(
        2.25,
        3.75
      );
  } else if (r < 0.985) {
    point =
      randomFloat(
        3.75,
        6
      );
  } else {
    point =
      randomFloat(
        6,
        12
      );
  }

  return Math.max(
    1.01,
    Math.round(
      point * 100
    ) / 100
  );
}

function crashBar(
  mult,
  crashed = false
) {
  const maxBar = 20;

  const progress =
    Math.min(
      maxBar,
      Math.floor(
        Math.log(
          Math.max(
            1,
            mult
          )
        ) /
        Math.log(1.15)
      )
    );

  const filled =
    "🟩".repeat(
      progress
    );

  const empty =
    "⬛".repeat(
      maxBar -
      progress
    );

  return crashed
    ? `${filled}💥${empty}`
    : `${filled}🚀${empty}`;
}

function crashColor(mult) {
  if (mult >= 5)
    return COLOR_LOSE;

  if (mult >= 2)
    return COLOR_PLAYING;

  return COLOR_WIN;
}

async function crash(
  message,
  args,
  user
) {
  const bet =
    validBet(
      message,
      args
    );

  if (bet === null)
    return;

  spendFromBalance(
    user,
    bet
  );

  saveData();

  const crashPoint =
    rollCrashPoint();

  let mult = 1.00;
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
            "💰 Cash Out"
          )
          .setStyle(
            ButtonStyle.Success
          )
      );

  const ge = () =>
    gembed(
      `${crashBar(mult)}\n\n` +
      `📈 Multiplier: **${mult.toFixed(2)}x**\n` +
      `💵 Current value: **${money(bet * mult)}** ${db.currency}\n\n` +
      `💰 Bet: **${money(bet)}** ${db.currency}\n\n` +
      `⚡ **Cash out whenever you want!**`,
      crashColor(mult),
      "🚀 Crash 🚀"
    );

  const msg =
    await message.reply({
      embeds: [ge()],
      components: [row]
    });

  /*
    Smaller interval and slower growth.
    This gives the player more usable time
    to press Cash Out.
  */

  const c =
    msg.createMessageComponentCollector({
      time: 30000
    });

  const interval =
    setInterval(
      async () => {
        if (finished)
          return;

        /*
          Slower growth than old 1.07.
        */

        mult =
          Math.round(
            mult *
            1.035 *
            100
          ) / 100;

        if (
          mult >= crashPoint
        ) {
          finished = true;

          clearInterval(
            interval
          );

          c.stop();

          saveData();

          await msg.edit({
            embeds: [
              gembed(
                `${crashBar(
                  crashPoint,
                  true
                )}\n\n` +
                `💥 Crashed at **${crashPoint.toFixed(2)}x**!\n\n` +
                `❌ Lost **${money(bet)}** ${db.currency}.`,
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
          embeds: [ge()],
          components: [row]
        }).catch(() => {});
      },
      650
    );

  c.on(
    "collect",
    async i => {
      if (
        i.user.id !==
        message.author.id
      ) {
        return i.reply({
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
        /*
          ACK immediately.
        */

        await i.deferUpdate();

        if (finished)
          return;

        /*
          Cashout happens immediately.
          Stop interval before calculating payout.
        */

        finished = true;

        clearInterval(
          interval
        );

        c.stop();

        const payout =
          Math.floor(
            bet * mult
          );

        creditBank(
          user,
          payout
        );

        saveData();

        await i.editReply({
          embeds: [
            gembed(
              `${crashBar(mult)}\n\n` +
              `💰 **CASHED OUT!**\n\n` +
              `📈 Cashout: **${mult.toFixed(2)}x**\n` +
              `💵 Payout: **${money(payout)}** ${db.currency}\n` +
              `📊 Profit: **${money(payout - bet)}** ${db.currency}`,
              COLOR_WIN,
              "🚀 Crash 🚀"
            )
          ],
          components: [
            disabledRow(row)
          ]
        }).catch(() => {});

      } catch (err) {
        console.error(
          "❌ Crash interaction error:",
          err
        );

      } finally {
        processing = false;
      }
    }
  );

  c.on(
    "end",
    async () => {
      if (finished)
        return;

      finished = true;

      clearInterval(
        interval
      );

      /*
        If the 30 second game timeout
        happens before cashout/crash,
        return the original bet exactly once.
      */

      creditBank(
        user,
        bet
      );

      saveData();

      await msg.edit({
        embeds: [
          gembed(
            `⏰ Crash game timed out.\n\n` +
            `💰 Returned **${money(bet)}** ${db.currency}.`,
            COLOR_INFO,
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
        gembed(
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

  /*
    Do NOT start cooldown until
    the player actually presses SPIN.
  */

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
        gembed(
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

  const c =
    msg.createMessageComponentCollector({
      time: 30000,
      max: 1
    });

  let finished = false;

  c.on(
    "collect",
    async i => {
      if (
        i.user.id !==
        message.author.id
      ) {
        return i.reply({
          content:
            "❌ This isn't your wheel.",
          ephemeral: true
        });
      }

      if (finished)
        return;

      finished = true;

      /*
        Cooldown starts ONLY now.
      */

      db.daily[
        message.author.id
      ] = Date.now();

      await i.deferUpdate();

      for (
        let n = 0;
        n < 8;
        n++
      ) {
        await new Promise(
          r =>
            setTimeout(
              r,
              120
            )
        );

        await msg.edit({
          embeds: [
            gembed(
              `🔄 ${
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

      creditBank(
        user,
        result.amount
      );

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
          gembed(
            `🏆 Prize: **${result.label}** ${db.currency}\n\n` +
            `💰 Your new total: **${money(totalBalance(user))}** ${db.currency}.`,
            COLOR_WIN,
            "☀️ Daily ☀️"
          )
        ],
        components: []
      }).catch(() => {});
    }
  );

  c.on(
    "end",
    async () => {
      if (finished)
        return;

      finished = true;

      /*
        No cooldown was consumed.
      */

      await msg.edit({
        embeds: [
          gembed(
            "⏰ Time ran out. Your Daily spin was not used.",
            COLOR_INFO,
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
      "Hit / Stand / Double. Natural pays 2.5x.",
      "",

      "**🐔 Cockfight — `$cf <amount|half|all>`**",
      "Starts at 50%. Every win adds exactly +1%. Maximum 60%. A loss resets to 50%.",
      "",

      "**🎲 Higher or Lower — `$hl <amount|half|all>`**",
      "Choose Higher, Same or Lower. Same pays 8x. House edge is applied.",
      "",

      "**🍀 CoinFlip — `$ht <amount|half|all>`**",
      "Head/Tail, pays 2x.",
      "",

      "**💣 Mines — `$mines <amount|half|all>`**",
      "3x3, one bomb. Cash Out whenever you want.",
      "",

      "**⛏️ Goldmine — `$gm <amount|half|all>`**",
      "24 tiles, 12 bombs, treasure multipliers compound. Cash Out whenever you want.",
      "",

      "**🎰 Slots — `$slots <amount|half|all>`**",
      "8 symbols, animated reels and multiple combinations.",
      "",

      "**🎡 Roulette — `$roulette <amount|half|all> <red/black/green/0-36>`**",
      "Red/Black = 1.9x, Green = 12x, exact number = 30x.",
      "",

      "**🚀 Crash — `$crash <amount|half|all>`**",
      "Multiplier climbs more slowly. Cash Out whenever you want before the crash.",
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
   LOGIN
   ============================================================ */

if (!process.env.DISCORD_TOKEN) {
  console.error(
    "❌ DISCORD_TOKEN is missing."
  );
} else {
  client.login(
    process.env.DISCORD_TOKEN
  ).catch(
    e =>
      console.error(
        "❌ Discord login failed:",
        e
      )
  );
}