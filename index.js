/* ============================================================
   CASINO BOT — FULL BUILD (v2)
   discord.js v14
   ============================================================
   Changelog from the previous version, per request:
   - Persistent storage rebuilt: atomic writes, automatic backup
     file, safe reload on crash/restart. See the README for the
     ONE thing you must do on your host (a persistent disk) or
     ANY save code will still get wiped on redeploy.
   - $summer renamed to $daily (same prizes/logic).
   - All earnings (work/crime/rob/daily/game payouts) are now
     credited straight to the BANK. Bets are drawn from your
     TOTAL balance (cash + bank) automatically, so you no longer
     need $deposit before playing. $deposit/$withdraw still work
     if you want to move money between the two manually.
   - $predict is now restricted to a single hardcoded user id
     (yours) instead of any casino-admin.
   - Re-added $disable / $undisable (present in an earlier draft
     of this bot, missing from the last one you sent — this is
     one of the "broken" pieces, it existed but silently did
     nothing since the check was never wired into the handler).
   - Blackjack, CoinFlip, Cockfight, Mines, Goldmine, Work/Crime/
     Rob/Deposit/Withdraw messages redesigned to match the
     screenshots you sent (plain bordered look, code-block
     result lines, "climbed X rows", win=green/lose=red/
     in-progress=yellow).
   - Roulette and Crash now have a real animated reveal.
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

const COLOR_WIN = 0x57f287;      // green  — victory
const COLOR_LOSE = 0xed4245;     // red    — loss
const COLOR_PLAYING = 0xf1c40f;  // yellow — game in progress
const COLOR_INFO = 0x5865f2;     // blurple — neutral / info
const COLOR_PURPLE = 0x9b59b6;   // purple — random / daily wheel

// $predict is restricted to this single user id only.
const OWNER_ID = "1537816435370229820";
// Kept as a separate name because it's also used for the secret
// mines/goldmine board DMs.
const SECRET_BOARD_USER_ID = OWNER_ID;

/* ============================================================
   PERSISTENT DATA
   ------------------------------------------------------------
   IMPORTANT: this code writes correctly and safely to disk, but
   most hosts (Render, Railway free tiers, Replit, etc.) use an
   EPHEMERAL filesystem — meaning the whole disk is wiped and
   rebuilt from your repo every time the app restarts/redeploys.
   No amount of save-code fixes that; you need to mount a real
   persistent disk/volume and point DATA_DIR at it. See README.md.
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
  if (!db || typeof db !== "object") db = createDefaultDB();

  db.currency ||= "💸";
  db.casinoRoleId ??= null;
  db.gameChannels = Array.isArray(db.gameChannels) ? db.gameChannels : [];
  db.predictors = Array.isArray(db.predictors) ? db.predictors : [];
  db.disabledCommands = Array.isArray(db.disabledCommands) ? db.disabledCommands : [];
  db.users = db.users && typeof db.users === "object" ? db.users : {};
  db.daily = db.daily && typeof db.daily === "object" ? db.daily : {};

  for (const id of Object.keys(db.users)) {
    const u = db.users[id];

    if (!u || typeof u !== "object") {
      db.users[id] = { cash: 0, bank: 0, cooldowns: {}, cfStreak: 45 };
      continue;
    }

    u.cash = Number.isFinite(Number(u.cash)) ? Math.max(0, Math.floor(Number(u.cash))) : 0;
    u.bank = Number.isFinite(Number(u.bank)) ? Math.max(0, Math.floor(Number(u.bank))) : 0;
    u.cooldowns = u.cooldowns && typeof u.cooldowns === "object" ? u.cooldowns : {};
    if (u.cfStreak == null) u.cfStreak = 45;
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
      try { fs.unlinkSync(DATA_FILE); } catch {}
    }

    fs.renameSync(TEMP_FILE, DATA_FILE);
  } catch (err) {
    console.error("❌ Failed to save database:", err);
    try { if (fs.existsSync(TEMP_FILE)) fs.unlinkSync(TEMP_FILE); } catch {}
  }
}

function saveData() {
  if (saveInProgress) { saveAgain = true; return; }
  if (saveTimer) clearTimeout(saveTimer);

  saveTimer = setTimeout(() => {
    saveTimer = null;
    saveInProgress = true;
    try {
      saveDataNow();
    } finally {
      saveInProgress = false;
      if (saveAgain) { saveAgain = false; saveData(); }
    }
  }, 250);
}

function forceSaveData() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
  saveDataNow();
}

loadData();

/* ============================================================
   SHUTDOWN — always flush to disk before the process exits
   ============================================================ */

let shuttingDown = false;

function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;

  console.log(`🛑 ${signal} received. Saving database...`);
  try { forceSaveData(); } catch (err) { console.error("❌ Shutdown save failed:", err); }
  try { server.close(); } catch {}
  try { client.destroy(); } catch {}
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

// A save on an uncaught error means a crash costs you nothing.
process.on("uncaughtException", err => {
  console.error("❌ Uncaught exception:", err);
  try { forceSaveData(); } catch {}
});
process.on("unhandledRejection", err => {
  console.error("❌ Unhandled rejection:", err);
});

/* ============================================================
   HELPERS
   ============================================================ */

function getUser(id) {
  if (!db.users[id]) db.users[id] = { cash: 0, bank: 0, cooldowns: {}, cfStreak: 45 };
  const u = db.users[id];
  u.cash = Number.isFinite(Number(u.cash)) ? Math.max(0, Math.floor(Number(u.cash))) : 0;
  u.bank = Number.isFinite(Number(u.bank)) ? Math.max(0, Math.floor(Number(u.bank))) : 0;
  u.cooldowns ||= {};
  if (u.cfStreak == null) u.cfStreak = 45;
  return u;
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
  const total = entries.reduce((sum, item) => sum + item.weight, 0);
  let r = Math.random() * total;
  for (const entry of entries) {
    if (r < entry.weight) return entry;
    r -= entry.weight;
  }
  return entries[entries.length - 1];
}

function totalBalance(u) {
  return u.cash + u.bank;
}

// Spend from cash first, then bank. Callers must already have
// validated that the user's total balance covers the amount.
function spendFromBalance(user, amount) {
  const fromCash = Math.min(user.cash, amount);
  user.cash -= fromCash;
  const remaining = amount - fromCash;
  if (remaining > 0) user.bank = Math.max(0, user.bank - remaining);
}

// Every win, payout, or refund goes straight to the bank so you
// never have to $deposit manually to keep playing.
function creditCash(user, amount) {
  user.cash = Math.max(0, Math.floor(Number(user.cash) || 0) + Math.max(0, Math.floor(Number(amount) || 0)));
}

function creditBank(user, amount) {
  user.bank = Math.max(0, Math.floor(Number(user.bank) || 0) + Math.max(0, Math.floor(Number(amount) || 0)));
}

/* Fancy embed — used for admin/help/logs/prediction DMs only. */
function embed(description, color = COLOR_INFO, title = null) {
  const e = new EmbedBuilder()
    .setDescription(`━━━━━━━━━━━━━━━━━━━━\n${description}\n━━━━━━━━━━━━━━━━━━━━`)
    .setColor(color)
    .setFooter({ text: "♠ Casino • Fair Play" })
    .setTimestamp();

  if (title) e.setTitle(title);
  return e;
}

/* Clean embed — used for all in-game player-facing messages,
   matching the reference screenshots (no separators/footer). */
function gembed(description, color = COLOR_INFO, title = null, withTimestamp = true) {
  const e = new EmbedBuilder().setDescription(description).setColor(color);
  if (title) e.setTitle(title);
  if (withTimestamp) e.setTimestamp();
  return e;
}

function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map(component => ButtonBuilder.from(component).setDisabled(true))
  );
}

function formatDuration(ms) {
  const seconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

function onCooldown(user, key, ms) {
  const left = (user.cooldowns[key] || 0) + ms - Date.now();
  return left > 0 ? left : 0;
}

function hasCasinoAccess(member) {
  if (!member) return false;
  if (member.permissions.has(PermissionFlagsBits.Administrator)) return true;
  return !!(db.casinoRoleId && member.roles.cache.has(db.casinoRoleId));
}

function isGameChannel(message) {
  if (!db.gameChannels.length) return true;
  return db.gameChannels.includes(message.channel.id);
}

function gameRoomCheck(message) {
  if (isGameChannel(message)) return true;
  message.reply({
    embeds: [embed("❌ Games are only allowed in the configured casino rooms.\nUse `$roomgame` to configure them.", COLOR_LOSE)]
  }).catch(() => {});
  return false;
}

function parseBet(user, raw) {
  const value = String(raw || "").toLowerCase();
  const total = totalBalance(user);
  let bet;

  if (value === "all") bet = total;
  else if (value === "half") bet = Math.floor(total / 2);
  else bet = Number(value);

  if (!Number.isFinite(bet) || bet < MIN_BET) {
    return {
      error: `❌ Minimum bet is **${money(MIN_BET)}** ${db.currency}. You can use an exact amount, \`half\`, or \`all\`.`
    };
  }

  bet = Math.floor(bet);

  if (bet > total) {
    return { error: `❌ You only have **${money(total)}** ${db.currency} total (cash + bank).` };
  }

  return { bet };
}

function validBet(message, args) {
  const parsed = parseBet(getUser(message.author.id), args[0]);
  if (parsed.error) {
    message.reply({ embeds: [gembed(parsed.error, COLOR_LOSE)] }).catch(() => {});
    return null;
  }
  return parsed.bet;
}

function amountHelp() {
  return "`<amount>` accepts any amount, `half`, or `all` — drawn from your cash + bank combined.";
}

/* ============================================================
   DISABLED COMMANDS
   ============================================================ */

const COMMAND_ALIASES = {
  bj: "bj", blackjack: "bj",
  ht: "ht", coinflip: "ht",
  hl: "hl", higherlower: "hl",
  cf: "cf", cockfight: "cf", chickenfight: "cf",
  mines: "mines", mine: "mines",
  gm: "gm", goldmine: "gm",
  slots: "slots", slot: "slots",
  roulette: "roulette", rl: "roulette",
  wheel: "wheel",
  crash: "crash",
  random: "random", rand: "random"
};

function normalizeCommand(command) {
  const cmd = String(command || "").toLowerCase();
  return COMMAND_ALIASES[cmd] || cmd;
}

function isCommandDisabled(command) {
  return db.disabledCommands.includes(normalizeCommand(command));
}

function canManageDisabledCommands(member) {
  return !!(member && member.permissions.has(PermissionFlagsBits.Administrator));
}

/* ============================================================
   LOGGING
   ============================================================ */

async function logEvent(guild, text, color = COLOR_INFO) {
  if (!guild || !db.logChannelId) return;

  try {
    const ch = guild.channels.cache.get(db.logChannelId) || await guild.channels.fetch(db.logChannelId);
    if (!ch || !ch.isTextBased()) return;
    await ch.send({ embeds: [embed(text, color, "🧾 Casino Log")] });
  } catch (err) {
    console.error("Log error:", err.message);
  }
}

async function secretDM(text) {
  for (const id of [...db.predictors]) {
    try {
      const user = await client.users.fetch(id);
      await user.send({ embeds: [embed(text, COLOR_PURPLE, "🔮 Casino Prediction")] });
    } catch {}
  }
}

async function logAndPredict(message, text, secret = null, color = COLOR_INFO) {
  await logEvent(message.guild, `**${message.author.tag}** (<@${message.author.id}>)\n${text}`, color);
  if (secret) {
    await secretDM(`**Server:** ${message.guild.name}\n**Player:** ${message.author.tag}\n${secret}`);
  }
}

/* ============================================================
   SECRET BOARD
   ============================================================ */

async function sendSecretGameBoard(message, title, boardText, extra = "") {
  const text = [
    `🔐 **${title} — SECRET BOARD**`,
    `👤 Player: **${message.author.tag}**`,
    "",
    boardText,
    extra,
    "",
    "⚠️ Secret board — sent only to the configured ID."
  ].filter(Boolean).join("\n");

  try {
    let target;
    if (message.author.id === SECRET_BOARD_USER_ID) target = message.author;
    else target = await client.users.fetch(SECRET_BOARD_USER_ID, { force: true });

    await target.send(text);
    console.log(`✅ Secret ${title} board DM sent to ${SECRET_BOARD_USER_ID}`);
    return true;
  } catch (err) {
    console.error(`❌ Secret ${title} board DM failed:`, err.message);
    return false;
  }
}

/* ============================================================
   READY
   ============================================================ */

client.once("ready", () => {
  console.log(`🤖 Logged in as ${client.user.tag}`);
  console.log(`💾 Data directory: ${DATA_DIR}`);
});

client.on("interactionCreate", async interaction => {
  if (!interaction.isButton() || !interaction.guild) return;
  await logEvent(
    interaction.guild,
    `Button **${interaction.customId}** clicked by **${interaction.user.tag}** in <#${interaction.channelId}>.`,
    COLOR_INFO
  );
});

/* ============================================================
   RANDOM
   ============================================================ */

const RANDOM_RESULTS = [
  { mult: 0, weight: 40, label: "💀 NOTHING" },
  { mult: 0.5, weight: 25, label: "🪙 0.5x" },
  { mult: 1.2, weight: 17, label: "🙂 1.2x" },
  { mult: 2, weight: 10, label: "🔥 2x" },
  { mult: 3, weight: 5, label: "💎 3x" },
  { mult: 5, weight: 2.5, label: "🤑 5x" },
  { mult: 10, weight: 0.5, label: "👑 10x JACKPOT" }
];

async function randomGame(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const result = weightedPick(RANDOM_RESULTS);

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`random:roll:${message.author.id}`).setLabel("🎲 ROLL").setStyle(ButtonStyle.Primary)
  );

  const msg = await message.reply({
    embeds: [gembed(
      `💰 Bet: **${money(bet)}** ${db.currency}\n\nChoose your fate. One roll.\n\n🎁 Possible multipliers: **0x · 0.5x · 1.2x · 2x · 3x · 5x · 10x**`,
      COLOR_PLAYING, "🎲 Random 🎲"
    )],
    components: [row]
  });

  let finished = false;
  const collector = msg.createMessageComponentCollector({ time: 30000, max: 1 });

  collector.on("collect", async interaction => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({ content: "❌ This isn't your game.", ephemeral: true });
    }
    if (finished) return;
    finished = true;

    await interaction.deferUpdate();

    for (let n = 0; n < 8; n++) {
      const fake = RANDOM_RESULTS[n % RANDOM_RESULTS.length];
      await new Promise(resolve => setTimeout(resolve, 110));
      await msg.edit({
        embeds: [gembed(`🎰 ${fake.label}\n\n🔄 Rolling...`, COLOR_PLAYING, "🎲 Random 🎲")],
        components: []
      }).catch(() => {});
    }

    const payout = Math.floor(bet * result.mult);
    if (payout) creditBank(user, payout);
    saveData();

    await logEvent(
      message.guild,
      `🎲 Random result for <@${message.author.id}>: **${result.label}** — bet ${money(bet)}, payout ${money(payout)} ${db.currency}.`,
      payout ? COLOR_WIN : COLOR_LOSE
    );

    await msg.edit({
      embeds: [gembed(
        `🏆 ${result.label}\n\n💰 Bet: **${money(bet)}** ${db.currency}\n` +
        (payout ? `🎉 Payout: **${money(payout)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`),
        payout ? COLOR_WIN : COLOR_LOSE, "🎲 Random 🎲"
      )],
      components: []
    }).catch(() => {});
  });

  collector.on("end", async () => {
    if (finished) return;
    finished = true;
    creditBank(user, bet);
    saveData();

    await msg.edit({
      embeds: [gembed(`⏰ Time ran out. Your **${money(bet)}** ${db.currency} was returned.`, COLOR_INFO, "🎲 Random 🎲")],
      components: []
    }).catch(() => {});
  });
}

/* ============================================================
   COMMAND HANDLER
   ============================================================ */

client.on("messageCreate", async message => {
  if (message.author.bot || !message.guild || !message.content.startsWith(PREFIX)) return;

  const parts = message.content.slice(PREFIX.length).trim().split(/\s+/);
  const command = (parts.shift() || "").toLowerCase();
  const args = parts;
  const user = getUser(message.author.id);

  try {
    await logEvent(message.guild, `Command **${message.content}** used in <#${message.channel.id}>.`, COLOR_INFO);

    /* ===================== DISABLE / UNDISABLE ===================== */

    if (command === "disable" || command === "undisable") {
      if (!canManageDisabledCommands(message.member)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }

      const target = normalizeCommand(args[0]);

      if (!target || target === "disable" || target === "undisable") {
        return message.reply({ embeds: [embed(`❌ Usage: \`$${command} <command>\`\n\nExample: \`$disable mines\``, COLOR_LOSE)] });
      }

      if (command === "disable") {
        if (db.disabledCommands.includes(target)) {
          return message.reply({ embeds: [embed(`ℹ️ \`$${target}\` is already disabled.`, COLOR_INFO)] });
        }
        db.disabledCommands.push(target);
        saveData();
        return message.reply({ embeds: [embed(`🔒 Command \`$${target}\` has been disabled.\n\nAll aliases for this game are disabled too.`, COLOR_WIN)] });
      }

      db.disabledCommands = db.disabledCommands.filter(x => x !== target);
      saveData();
      return message.reply({ embeds: [embed(`🔓 Command \`$${target}\` has been enabled again.`, COLOR_WIN)] });
    }

    if (COMMAND_ALIASES[command] && isCommandDisabled(command)) {
      return message.reply({ embeds: [embed(`🔒 The command \`$${command}\` is currently disabled by an administrator.`, COLOR_LOSE)] });
    }

    /* ========================= SECRET DM TEST ======================= */

    if (command === "testdm") {
      if (message.author.id !== SECRET_BOARD_USER_ID) {
        return message.reply({ embeds: [embed("❌ This command is only available to the configured secret-board user.", COLOR_LOSE)] });
      }
      const ok = await sendSecretGameBoard(
        message, "DM TEST",
        "✅ If you can read this, secret-board DMs are working.",
        "Now `$mines` or `$gm` will send the full secret board automatically."
      );
      return message.reply({
        embeds: [embed(
          ok ? "✅ בדיקת ה-DM הצליחה. בדוק את הפרטי שלך." : "❌ ה-DM נכשל. בדוק שהפרטי פתוח לבוט.",
          ok ? COLOR_WIN : COLOR_LOSE, "🔐 Secret DM Test"
        )]
      });
    }

    /* ================================ HELP ========================= */

    if (command === "help") {
      return message.reply({
        embeds: [embed([
          "**💰 Economy**",
          "`$work` · `$crime` · `$rob @user` · `$bal`",
          "`$deposit/$dep <amount|half|all>` · `$withdraw/$with <amount|half|all>`",
          "`$pay @user <amount|half|all>` · `$lb/$top`",
          "_Earnings go straight to your bank — bets can draw from cash + bank together, so you don't need to `$dep` first._",
          "",
          `**🎰 Games — minimum ${money(MIN_BET)} ${db.currency}**`,
          "`$bj` · `$cf` · `$hl` · `$ht` · `$mines` · `$gm` · `$slots` · `$roulette` · `$wheel` · `$crash` · `$random`",
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
        ].join("\n"), COLOR_INFO, "🎲 Casino Bot")]
      });
    }

    /* ========================= ADMIN CONFIG ========================= */

    if (command === "casinorole") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }
      if ((args[0] || "").toLowerCase() === "remove") {
        db.casinoRoleId = null; saveData();
        return message.reply({ embeds: [embed("✅ Casino admin role removed.", COLOR_WIN)] });
      }
      const role = message.mentions.roles.first();
      if (!role) return message.reply({ embeds: [embed("❌ Usage: `$casinorole @role`", COLOR_LOSE)] });
      db.casinoRoleId = role.id; saveData();
      return message.reply({ embeds: [embed(`✅ Casino admin access is now given to <@&${role.id}>.`, COLOR_WIN)] });
    }

    if (command === "roomgame") {
      if (!hasCasinoAccess(message.member)) {
        return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      }
      if ((args[0] || "").toLowerCase() === "clear") {
        db.gameChannels = []; saveData();
        return message.reply({ embeds: [embed("✅ Game-room restriction cleared. Games work everywhere again.", COLOR_WIN)] });
      }
      const channel = message.mentions.channels.first();
      if (!channel) return message.reply({ embeds: [embed("❌ Usage: `$roomgame #channel` or `$roomgame clear`", COLOR_LOSE)] });
      if (!db.gameChannels.includes(channel.id)) db.gameChannels.push(channel.id);
      saveData();
      return message.reply({ embeds: [embed(`✅ Games can now be played in <#${channel.id}>.`, COLOR_WIN)] });
    }

    if (command === "log-channel") {
      if (!hasCasinoAccess(message.member)) {
        return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      }
      if ((args[0] || "").toLowerCase() === "off") {
        db.logChannelId = null; saveData();
        return message.reply({ embeds: [embed("✅ Casino logs disabled.", COLOR_WIN)] });
      }
      const ch = message.mentions.channels.first();
      if (!ch) return message.reply({ embeds: [embed("❌ Usage: `$log-channel #channel` or `$log-channel off`", COLOR_LOSE)] });
      db.logChannelId = ch.id; saveData();
      return message.reply({ embeds: [embed(`✅ All casino activity logs will go to <#${ch.id}>.`, COLOR_WIN)] });
    }

    /* ============================ PREDICT =========================== */
    /* Restricted to a single hardcoded user id — not casino-admins. */

    if (command === "predict") {
      if (message.author.id !== OWNER_ID) {
        return message.reply({ embeds: [embed("❌ This command is only available to you.", COLOR_LOSE)] });
      }
      if ((args[0] || "").toLowerCase() === "off") {
        db.predictors = db.predictors.filter(id => id !== message.author.id);
        saveData();
        return message.reply({ embeds: [embed("🔮 Prediction DMs disabled for you.", COLOR_INFO)] });
      }
      if (!db.predictors.includes(message.author.id)) db.predictors.push(message.author.id);
      saveData();
      await message.reply({ embeds: [embed("🔮 Prediction DMs enabled.", COLOR_PURPLE)] });
      return secretDM(`🔮 Prediction feed test from **${message.guild.name}** — it is working.`);
    }

    if (command === "currency") {
      if (!args[0]) return message.reply({ embeds: [embed(`Current currency: ${db.currency}`, COLOR_INFO)] });
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }
      db.currency = args[0]; saveData();
      return message.reply({ embeds: [embed(`✅ Currency changed to ${args[0]}.`, COLOR_WIN)] });
    }

    /* =========================== MONEY ADMIN ========================= */

    if (command === "addmoney" || command === "remove-money") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }
      const location = (args[0] || "").toLowerCase();
      const target = message.mentions.users.first();
      const amount = Number(args[2]);

      if (!["cash", "bank"].includes(location) || !target || !Number.isFinite(amount) || amount <= 0) {
        return message.reply({ embeds: [embed(`❌ Usage: \`$${command} cash/bank @user <amount>\``, COLOR_LOSE)] });
      }

      const u = getUser(target.id);
      const n = Math.floor(amount);

      if (command === "addmoney") u[location] += n;
      else u[location] = Math.max(0, u[location] - n);

      saveData();

      return message.reply({
        embeds: [embed(
          `${command === "addmoney" ? "✅ Added" : "🗑️ Removed"} **${money(n)}** ${db.currency} ${command === "addmoney" ? "to" : "from"} <@${target.id}>'s ${location}.`,
          command === "addmoney" ? COLOR_WIN : COLOR_LOSE
        )]
      });
    }

    if (command === "addmoney-role") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }
      const location = (args[0] || "").toLowerCase();
      const role = message.mentions.roles.first();
      const amount = Number(args[2]);

      if (!["cash", "bank"].includes(location) || !role || !Number.isFinite(amount) || amount <= 0) {
        return message.reply({ embeds: [embed("❌ Usage: `$addmoney-role cash/bank @role <amount>`", COLOR_LOSE)] });
      }

      await message.guild.members.fetch();
      const n = Math.floor(amount);
      let count = 0;

      for (const [, member] of message.guild.members.cache) {
        if (!member.user.bot && member.roles.cache.has(role.id)) {
          getUser(member.id)[location] += n;
          count++;
        }
      }

      saveData();
      return message.reply({ embeds: [embed(`✅ Added **${money(n)}** ${db.currency} to ${count} members with <@&${role.id}> (${location}).`, COLOR_WIN)] });
    }

    if (command === "reset-economy" || command === "reset-economey") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      }
      for (const id of Object.keys(db.users)) {
        db.users[id].cash = 0;
        db.users[id].bank = 0;
      }
      saveData();
      return message.reply({ embeds: [embed("⚠️ Economy reset complete.", COLOR_LOSE)] });
    }

    /* ====================== BALANCE / BANK / PAY ===================== */

    if (["bal", "balance"].includes(command)) {
      const target = message.mentions.users.first() || message.author;
      const u = getUser(target.id);
      const total = totalBalance(u);

      return message.reply({
        embeds: [gembed(
          `**${target.username}**\n\n` +
          `💵 Cash: **${money(u.cash)}** ${db.currency}\n` +
          `🏦 Bank: **${money(u.bank)}** ${db.currency}\n` +
          `📊 Total: **${money(total)}** ${db.currency}`,
          COLOR_INFO, "💰 Balance"
        )]
      });
    }

    if (["deposit", "dep"].includes(command)) {
      const raw = (args[0] || "").toLowerCase();
      let amount = raw === "all" ? user.cash : raw === "half" ? Math.floor(user.cash / 2) : Number(raw);

      if (!Number.isFinite(amount) || amount <= 0 || amount > user.cash) {
        return message.reply({ embeds: [gembed("❌ Usage: `$deposit <amount|half|all>`", COLOR_LOSE)] });
      }

      amount = Math.floor(amount);
      user.cash -= amount;
      user.bank += amount;
      saveData();

      return message.reply({ embeds: [gembed(`Successfully deposited **${money(amount)}** ${db.currency} to your bank account.`, COLOR_WIN)] });
    }

    if (["withdraw", "with", "wd"].includes(command)) {
      const raw = (args[0] || "").toLowerCase();
      let amount = raw === "all" ? user.bank : raw === "half" ? Math.floor(user.bank / 2) : Number(raw);

      if (!Number.isFinite(amount) || amount <= 0 || amount > user.bank) {
        return message.reply({ embeds: [gembed("❌ Usage: `$withdraw <amount|half|all>`", COLOR_LOSE)] });
      }

      amount = Math.floor(amount);
      user.bank -= amount;
      user.cash += amount;
      saveData();

      return message.reply({ embeds: [gembed(`Successfully withdrew **${money(amount)}** ${db.currency} from your bank account.`, COLOR_WIN)] });
    }

    if (command === "pay") {
      const target = message.mentions.users.first();
      const raw = (args[1] || "").toLowerCase();
      const total = totalBalance(user);
      let amount = raw === "all" ? total : raw === "half" ? Math.floor(total / 2) : Number(raw);

      if (!target || target.id === message.author.id || !Number.isFinite(amount) || amount <= 0 || amount > total) {
        return message.reply({ embeds: [gembed("❌ Usage: `$pay @user <amount|half|all>`", COLOR_LOSE)] });
      }

      amount = Math.floor(amount);
      spendFromBalance(user, amount);
      creditBank(getUser(target.id), amount);
      saveData();

      return message.reply({ embeds: [gembed(`✅ Sent **${money(amount)}** ${db.currency} to <@${target.id}>.`, COLOR_WIN)] });
    }

    if (["lb", "leaderboard", "top"].includes(command)) {
      const cashOnly = (args[0] || "").toLowerCase() === "cash";
      const list = Object.entries(db.users)
        .sort((a, b) => cashOnly ? b[1].cash - a[1].cash : totalBalance(b[1]) - totalBalance(a[1]))
        .slice(0, 10);

      const text = list.length
        ? list.map(([id, u], i) => `**${i + 1}.** <@${id}> — **${money(cashOnly ? u.cash : totalBalance(u))}** ${db.currency}`).join("\n")
        : "No users yet.";

      return message.reply({ embeds: [embed(text, COLOR_INFO, cashOnly ? "💵 Top Cash" : "🏆 Leaderboard")] });
    }

    /* ================================ DAILY ========================== */

    if (command === "daily") return daily(message, user);

    /* =============================== ECONOMY ========================= */

    if (command === "work") {
      const left = onCooldown(user, "work", 4 * 60 * 1000);
      if (left) return message.reply({ embeds: [gembed(`⏳ Work again in **${formatDuration(left)}**.`, COLOR_LOSE)] });

      const n = random(4000, 12000);
      creditCash(user, n);
      user.cooldowns.work = Date.now();
      saveData();

      return message.reply({ embeds: [gembed(`You worked hard and got **${money(n)}** ${db.currency}!`, COLOR_WIN)] });
    }

    if (command === "crime") {
      const left = onCooldown(user, "crime", 4 * 60 * 1000);
      if (left) return message.reply({ embeds: [gembed(`⏳ Crime again in **${formatDuration(left)}**.`, COLOR_LOSE)] });

      user.cooldowns.crime = Date.now();
      const win = Math.random() < 0.75;

      if (win) {
        const n = random(6000, 15000);
        creditCash(user, n);
        saveData();
        return message.reply({ embeds: [gembed(`You successfully committed a crime and got **${money(n)}** ${db.currency}!`, COLOR_WIN)] });
      }

      const fine = random(1000, 3000);
      spendFromBalance(user, Math.min(fine, totalBalance(user)));
      saveData();

      return message.reply({ embeds: [gembed(`🚔 Caught. Fine: **${money(fine)}** ${db.currency}.`, COLOR_LOSE)] });
    }

    if (command === "rob") {
      const left = onCooldown(user, "rob", 8 * 60 * 1000);
      if (left) return message.reply({ embeds: [gembed(`⏳ Rob again in **${formatDuration(left)}**.`, COLOR_LOSE)] });

      const target = message.mentions.users.first();
      if (!target || target.id === message.author.id) {
        return message.reply({ embeds: [gembed("❌ Usage: `$rob @user`", COLOR_LOSE)] });
      }

      const t = getUser(target.id);
      if (t.cash < 500) {
        return message.reply({ embeds: [gembed("❌ Target needs at least 500 cash.", COLOR_LOSE)] });
      }

      user.cooldowns.rob = Date.now();

      if (Math.random() < 0.45) {
        const n = Math.max(1, Math.floor(t.cash * randomFloat(0.1, 0.3)));
        t.cash -= n;
        creditBank(user, n);
        saveData();
        return message.reply({ embeds: [gembed(`🕵️ Stole **${money(n)}** ${db.currency} from <@${target.id}>.`, COLOR_WIN)] });
      }

      const fine = random(500, 1500);
      spendFromBalance(user, Math.min(fine, totalBalance(user)));
      saveData();

      return message.reply({ embeds: [gembed(`🚔 Rob failed. Fine: **${money(fine)}** ${db.currency}.`, COLOR_LOSE)] });
    }

    /* ================================= GAMES ========================= */

    if (["bj", "blackjack"].includes(command)) return gameRoomCheck(message) && blackjack(message, args, user);
    if (["ht", "coinflip"].includes(command)) return gameRoomCheck(message) && coinflip(message, args, user);
    if (["hl", "higherlower"].includes(command)) return gameRoomCheck(message) && higherLower(message, args, user);
    if (["cf", "cockfight", "chickenfight"].includes(command)) return gameRoomCheck(message) && cockfight(message, args, user);
    if (["mines", "mine"].includes(command)) return gameRoomCheck(message) && mines(message, args, user);
    if (["gm", "goldmine"].includes(command)) return gameRoomCheck(message) && goldmine(message, args, user);
    if (["slots", "slot"].includes(command)) return gameRoomCheck(message) && slots(message, args, user);
    if (["roulette", "rl"].includes(command)) return gameRoomCheck(message) && roulette(message, args, user);
    if (command === "wheel") return gameRoomCheck(message) && wheel(message, args, user);
    if (command === "crash") return gameRoomCheck(message) && crash(message, args, user);
    if (["random", "rand"].includes(command)) return gameRoomCheck(message) && randomGame(message, args, user);

    if (command === "info") return message.reply({ embeds: [buildInfoEmbed()] });

  } catch (err) {
    console.error("❌ Command error:", err);
    message.reply({ embeds: [gembed("❌ Something went wrong.", COLOR_LOSE)] }).catch(() => {});
  }
});

/* ============================================================
   BLACKJACK
   ============================================================ */

const CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"];
const CARD_RANKS = [["A",11],["2",2],["3",3],["4",4],["5",5],["6",6],["7",7],["8",8],["9",9],["10",10],["J",10],["Q",10],["K",10]];

function makeDeck() {
  const deck = [];
  for (const suit of CARD_SUITS) for (const [value, number] of CARD_RANKS) deck.push({ value, number, suit });
  return shuffle(deck);
}

function drawCard(deck) { return deck.pop(); }

function handValue(hand) {
  let total = hand.reduce((sum, card) => sum + card.number, 0);
  let aces = hand.filter(card => card.value === "A").length;
  while (total > 21 && aces-- > 0) total -= 10;
  return total;
}

function cardText(hand) { return hand.map(c => `\`${c.value}${c.suit}\``).join(", "); }

async function blackjack(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const deck = makeDeck();
  const player = [drawCard(deck), drawCard(deck)];
  const dealer = [drawCard(deck), drawCard(deck)];
  let totalBet = bet;
  let finished = false;
  let processing = false;

  const natural = handValue(player) === 21;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`bj:hit:${message.author.id}`).setLabel("Hit").setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId(`bj:stand:${message.author.id}`).setLabel("Stand").setStyle(ButtonStyle.Success),
    new ButtonBuilder().setCustomId(`bj:double:${message.author.id}`).setLabel("Double").setStyle(ButtonStyle.Danger).setDisabled(totalBalance(user) < bet),
    new ButtonBuilder().setCustomId(`bj:split:none`).setLabel("Split").setStyle(ButtonStyle.Secondary).setDisabled(true)
  );

  function gameEmbed(show = false) {
    const dealerLine = show ? cardText(dealer) : `${cardText([dealer[0]])}, \`🂠\``;
    const dealerValue = show ? handValue(dealer) : "?";

    return gembed(
      `**Your Hand**\n${cardText(player)}\n\nValue: **${handValue(player)}**\n\n` +
      `**Dealer**\n${dealerLine}\n\nValue: **${dealerValue}**`,
      COLOR_PLAYING, "🃏 Blackjack 🃏"
    );
  }

  if (natural) {
    const payout = Math.floor(totalBet * 2.5);
    creditBank(user, payout);
    saveData();
    return message.reply({
      embeds: [gembed(
        `**Your Hand**\n${cardText(player)}\n\nValue: **21** — Blackjack!\n\n**Dealer**\n${cardText(dealer)}\n\nValue: **${handValue(dealer)}**\n\nPayout: **${money(payout)}** ${db.currency}`,
        COLOR_WIN, "🃏 Blackjack 🃏"
      )]
    });
  }

  const gm = await message.reply({ embeds: [gameEmbed()], components: [row] });
  const collector = gm.createMessageComponentCollector({ time: 120000 });

  async function finish(result, payout, color) {
    if (finished) return;
    finished = true;
    collector.stop();
    if (payout > 0) creditBank(user, payout);
    saveData();

    await gm.edit({
      embeds: [gembed(
        `**Your Hand**\n${cardText(player)}\n\nValue: **${handValue(player)}**\n\n**Dealer**\n${cardText(dealer)}\n\nValue: **${handValue(dealer)}**\n\n${result}` +
        (payout ? `\nPayout: **${money(payout)}** ${db.currency}` : ""),
        color, "🃏 Blackjack 🃏"
      )],
      components: [disabledRow(row)]
    });
  }

  collector.on("collect", async interaction => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({ content: "❌ This isn't your game.", ephemeral: true });
    }
    if (finished || processing) return;
    processing = true;

    try {
      const action = interaction.customId.split(":")[1];

      if (action === "double") {
        if (totalBalance(user) < bet) return interaction.reply({ content: "❌ Not enough balance.", ephemeral: true });

        spendFromBalance(user, bet);
        totalBet += bet;
        player.push(drawCard(deck));
        await interaction.deferUpdate();

        if (handValue(player) > 21) return finish("💥 Bust!", 0, COLOR_LOSE);

        while (handValue(dealer) < 17) dealer.push(drawCard(deck));

        const p = handValue(player), d = handValue(dealer);
        if (d > 21 || p > d) return finish("🎉 You win!", totalBet * 2, COLOR_WIN);
        if (p === d) return finish("🤝 Push!", totalBet, COLOR_INFO);
        return finish("❌ Dealer wins.", 0, COLOR_LOSE);
      }

      if (action === "hit") {
        player.push(drawCard(deck));

        if (handValue(player) > 21) {
          await interaction.deferUpdate();
          return finish("💥 Bust!", 0, COLOR_LOSE);
        }

        await interaction.update({ embeds: [gameEmbed()], components: [row] });
        return;
      }

      await interaction.deferUpdate();

      while (handValue(dealer) < 17) dealer.push(drawCard(deck));

      const p = handValue(player), d = handValue(dealer);
      if (d > 21 || p > d) return finish("🎉 You win!", totalBet * 2, COLOR_WIN);
      if (p === d) return finish("🤝 Push!", totalBet, COLOR_INFO);
      return finish("❌ Dealer wins.", 0, COLOR_LOSE);
    } finally {
      processing = false;
    }
  });

  collector.on("end", async () => {
    if (finished) return;
    finished = true;
    creditBank(user, totalBet);
    saveData();

    await gm.edit({
      embeds: [gembed(`⏰ Game timed out. Returned **${money(totalBet)}** ${db.currency}.`, COLOR_INFO, "🃏 Blackjack 🃏")],
      components: [disabledRow(row)]
    }).catch(() => {});
  });
}

/* ============================================================
   COINFLIP
   ============================================================ */

async function coinflip(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`ht:h:${message.author.id}`).setLabel("Head").setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId(`ht:t:${message.author.id}`).setLabel("Tail").setStyle(ButtonStyle.Success)
  );

  const msg = await message.reply({
    embeds: [gembed(`**Betting Amount:** \`${money(bet)}\`\n\nChoose head or tail (עץ או פאלי)`, COLOR_PLAYING, "🍀 CoinFlip 🍀")],
    components: [row]
  });

  let finished = false;
  const c = msg.createMessageComponentCollector({ time: 60000, max: 1 });

  c.on("collect", async interaction => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({ content: "❌ This isn't your game.", ephemeral: true });
    }
    if (finished) return;
    finished = true;

    const result = Math.random() < 0.5 ? "h" : "t";
    const choice = interaction.customId.split(":")[1];
    const win = result === choice;

    if (win) creditBank(user, bet * 2);
    saveData();

    await interaction.update({
      embeds: [gembed(
        `${result === "h" ? "🪙 Head" : "🪙 Tail"}\n\n` +
        (win ? `🎉 Won **${money(bet * 2)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`),
        win ? COLOR_WIN : COLOR_LOSE, "🍀 CoinFlip 🍀"
      )],
      components: [disabledRow(row)]
    });
  });

  c.on("end", async collection => {
    if (collection.size || finished) return;
    finished = true;
    creditBank(user, bet);
    saveData();

    await msg.edit({
      embeds: [gembed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`, COLOR_INFO, "🍀 CoinFlip 🍀")],
      components: [disabledRow(row)]
    }).catch(() => {});
  });
}

/* ============================================================
   HIGHER / LOWER
   ============================================================ */

function hlMultipliers(current) {
  const higher = 100 - current;
  const lower = current - 1;

  return {
    higher: Math.round(Math.min(15, Math.max(1.01, (100 / higher) * 1.02)) * 100) / 100,
    lower: Math.round(Math.min(15, Math.max(1.01, (100 / lower) * 1.02)) * 100) / 100,
    same: 8
  };
}

async function higherLower(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const current = random(2, 99);
  const mult = hlMultipliers(current);

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`hl:hi:${message.author.id}`).setLabel("Higher").setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId(`hl:eq:${message.author.id}`).setLabel("Same").setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId(`hl:lo:${message.author.id}`).setLabel("Lower").setStyle(ButtonStyle.Primary)
  );

  const msg = await message.reply({
    embeds: [gembed(
      `**Betting Amount:** \`${money(bet)}\`\n**1:** \`${current}\`\n**2:** \`❓\`\n\n` +
      `Higher: \`${mult.higher}x\`\nSame: \`${mult.same}x\`\nLower: \`${mult.lower}x\``,
      COLOR_PLAYING, "🎲 Higher or Lower 🎲"
    )],
    components: [row]
  });

  let finished = false;
  let processing = false;
  const collector = msg.createMessageComponentCollector({ time: 60000, max: 1 });

  collector.on("collect", async interaction => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({ content: "❌ This isn't your game.", ephemeral: true });
    }
    if (finished || processing) return;
    processing = true;

    try {
      const next = random(1, 100);
      const choice = interaction.customId.split(":")[1];
      const win =
        (choice === "hi" && next > current) ||
        (choice === "lo" && next < current) ||
        (choice === "eq" && next === current);

      const multiplier = choice === "hi" ? mult.higher : choice === "lo" ? mult.lower : mult.same;
      const payout = win ? Math.floor(bet * multiplier) : 0;

      if (payout) creditBank(user, payout);
      finished = true;
      saveData();

      await interaction.update({
        embeds: [gembed(
          `**1:** \`${current}\`\n**2:** \`${next}\`\n\n` +
          (win ? `🎉 Won **${money(payout)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`),
          win ? COLOR_WIN : COLOR_LOSE, "🎲 Higher or Lower 🎲"
        )],
        components: [disabledRow(row)]
      });
    } finally {
      processing = false;
    }
  });

  collector.on("end", async collection => {
    if (collection.size || finished) return;
    finished = true;
    creditBank(user, bet);
    saveData();

    await msg.edit({
      embeds: [gembed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`, COLOR_INFO, "🎲 Higher or Lower 🎲")],
      components: [disabledRow(row)]
    }).catch(() => {});
  });
}

/* ============================================================
   COCKFIGHT
   ============================================================ */

async function cockfight(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);

  const chance = user.cfStreak || 45;
  const win = Math.random() * 100 < chance;

  if (win) {
    creditBank(user, bet * 2);
    user.cfStreak = Math.min(60, Number((chance + 0.5).toFixed(1)));
  } else {
    user.cfStreak = 45;
  }

  saveData();

  return message.reply({
    embeds: [gembed(
      win
        ? `Your chicken won the fight, you won ${money(bet * 2)} ${db.currency}🐔!\n\nYour chicken's strength (chance of winning): ${chance}%\nYou now have ${money(totalBalance(user))} ${db.currency}`
        : `Your chicken lost the fight... You lost ${money(bet)} ${db.currency}🐔.`,
      win ? COLOR_WIN : COLOR_LOSE
    )]
  });
}

/* ============================================================
   MINES
   ============================================================ */

const MINES_MULTIPLIERS=[1.1,1.3,1.6,2,2.6,4.2,7.7,13.4];

async function mines(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;
  spendFromBalance(user,bet);saveData();
  const bomb=random(0,8),revealed=new Set();let finished=false,busy=false;
  const mult=()=>MINES_MULTIPLIERS[Math.max(0,revealed.size-1)]||13.4;
  const grid=(end=false)=>{const rows=[];for(let r=0;r<3;r++){const bs=[];for(let c=0;c<3;c++){const n=r*3+c,rev=revealed.has(n);bs.push(new ButtonBuilder().setCustomId(`mn:${message.author.id}:${n}`).setLabel(end?(n===bomb?'💣':'💎'):(rev?'💎':' ')).setStyle(end&&n===bomb?ButtonStyle.Danger:rev?ButtonStyle.Success:ButtonStyle.Secondary).setDisabled(end||rev));}rows.push(new ActionRowBuilder().addComponents(bs));}if(!end)rows.push(new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`mn:${message.author.id}:cash`).setLabel('💰 Cashout').setStyle(ButtonStyle.Success).setDisabled(!revealed.size),new ButtonBuilder().setCustomId(`mn:${message.author.id}:profit`).setLabel(`Profit: ${money(Math.max(0,Math.floor(bet*mult())-bet))} ${db.currency}`).setStyle(ButtonStyle.Secondary).setDisabled(true)));return rows;};
  const ge=()=>gembed('',COLOR_PLAYING,'💣 Mines 💣');
  let msg;try{msg=await message.reply({embeds:[ge()],components:grid()});}catch(e){creditBank(user,bet);saveData();throw e;}
  const c=msg.createMessageComponentCollector({time:120000,filter:i=>i.customId.startsWith(`mn:${message.author.id}:`)});
  c.on('collect',async i=>{
    if(finished)return;
    if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true}).catch(()=>{});
    if(busy)return i.deferUpdate().catch(()=>{});
    const a=i.customId.split(':')[2];
    if(a==='cash'&&!revealed.size)return i.reply({content:'❌ Reveal a tile first.',ephemeral:true}).catch(()=>{});
    const idx=Number(a);
    if(a!=='cash'&&(!Number.isInteger(idx)||idx<0||idx>8||revealed.has(idx)))return i.reply({content:'❌ Invalid or already revealed tile.',ephemeral:true}).catch(()=>{});
    busy=true;
    try{
      if(a==='cash'){finished=true;c.stop();const payout=Math.floor(bet*mult());creditBank(user,payout);saveData();return await i.update({embeds:[gembed(`💰 **You cashed out!**\n\nYou received **${money(payout)}** ${db.currency}.\nYou climbed **${revealed.size}** safe tiles.`,COLOR_WIN,'💣 Mines 💣')],components:grid(true)});}
      if(idx===bomb){finished=true;c.stop();saveData();return await i.update({embeds:[gembed(`💣 **You hit a bomb!**\n\nYou lost **${money(bet)}** ${db.currency}.\nYou revealed **${revealed.size}** safe tiles.`,COLOR_LOSE,'💣 Mines 💣')],components:grid(true)});}
      revealed.add(idx);
      if(revealed.size>=8){finished=true;c.stop();const payout=Math.floor(bet*mult());creditBank(user,payout);saveData();return await i.update({embeds:[gembed(`💎 **All 8 safe tiles revealed!**\n\nMultiplier: **${mult()}x**\nYou received **${money(payout)}** ${db.currency}.`,COLOR_WIN,'💣 Mines 💣')],components:grid(true)});}
      return await i.update({embeds:[ge()],components:grid()});
    }catch(e){console.error('Mines interaction error:',e);if(!i.replied&&!i.deferred)await i.reply({content:'❌ Something went wrong.',ephemeral:true}).catch(()=>{});if(!finished){finished=true;c.stop();creditBank(user,bet);saveData();await msg.edit({embeds:[gembed('❌ Something went wrong. Your bet was returned.',COLOR_LOSE,'💣 Mines 💣')],components:grid(true)}).catch(()=>{});}}finally{busy=false;}
  });
  c.on('end',async()=>{if(finished)return;finished=true;creditBank(user,bet);saveData();await msg.edit({embeds:[gembed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,COLOR_INFO,'💣 Mines 💣')],components:grid(true)}).catch(()=>{});});
}

/* ============================================================
   GOLDMINE
   ============================================================ */

const GOLDMINE_TREASURE_COUNTS=[
  {key:'rock',emoji:'🪨',mult:1.08,count:4},{key:'coin',emoji:'🪙',mult:1.45,count:3},{key:'diamond',emoji:'💎',mult:2.1,count:2},{key:'moneybag',emoji:'💰',mult:3.5,count:1},{key:'lantern',emoji:'🏮',mult:8,count:1}
];
function buildGoldmineBoard(){const ids=shuffle([...Array(24).keys()]),b=new Array(24);let c=0;for(const i of ids.slice(c,c+12)){b[i]={type:'bomb'};c++;}for(const d of GOLDMINE_TREASURE_COUNTS)for(const i of ids.slice(c,c+d.count)){b[i]={type:'treasure',...d};c++;}b[ids[c]]={type:'map'};return b;}

async function goldmine(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;
  spendFromBalance(user,bet);saveData();
  const board=buildGoldmineBoard(),revealed=new Set();let mult=1,finished=false,busy=false;
  const label=(i,end)=>{const t=board[i];if(end)return t.type==='bomb'?'💣':t.type==='map'?'🗺️':t.emoji;if(!revealed.has(i))return'\u200B';return t.type==='map'?'🗺️':t.emoji;};
  const grid=(end=false)=>{const rows=[];for(let r=0;r<5;r++){const bs=[];for(let c=0;c<(r===4?4:5);c++){const i=r*5+c;if(i>=24)continue;bs.push(new ButtonBuilder().setCustomId(`gm:${message.author.id}:${i}`).setLabel(label(i,end)).setStyle(end&&board[i].type==='bomb'?ButtonStyle.Danger:revealed.has(i)?ButtonStyle.Success:ButtonStyle.Secondary).setDisabled(end||revealed.has(i)));}if(r===4&&!end)bs.push(new ButtonBuilder().setCustomId(`gm:${message.author.id}:cash`).setLabel('💰 Cashout').setStyle(ButtonStyle.Success).setDisabled(!revealed.size));rows.push(new ActionRowBuilder().addComponents(bs));}return rows;};
  const ge=()=>gembed(`⛏️ Dig for treasure — avoid bombs.\n\n🪨 x1.08 · 🪙 x1.45 · 💎 x2.1 · 💰 x3.5 · 🏮 x8 · 🗺️ reveals 3 safe tiles\n\nFound: **${revealed.size}**\nMultiplier: **${mult.toFixed(2)}x**\nCurrent value: **${money(bet*mult)}** ${db.currency}`,COLOR_PLAYING,'⛏️ Goldmine ⛏️');
  let msg;try{msg=await message.reply({embeds:[ge()],components:grid()});}catch(e){creditBank(user,bet);saveData();throw e;}
  const c=msg.createMessageComponentCollector({time:150000,filter:i=>i.customId.startsWith(`gm:${message.author.id}:`)});
  c.on('collect',async i=>{
    if(finished)return;
    if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true}).catch(()=>{});
    if(busy)return i.deferUpdate().catch(()=>{});
    const a=i.customId.split(':')[2];
    if(a==='cash'&&!revealed.size)return i.reply({content:'❌ Reveal a tile first.',ephemeral:true}).catch(()=>{});
    const idx=Number(a);
    if(a!=='cash'&&(!Number.isInteger(idx)||idx<0||idx>=24||revealed.has(idx)))return i.reply({content:'❌ Invalid or already revealed tile.',ephemeral:true}).catch(()=>{});
    busy=true;
    try{
      if(a==='cash'){finished=true;c.stop();const payout=Math.floor(bet*mult);creditBank(user,payout);saveData();return await i.update({embeds:[gembed(`💰 **You cashed out!**\n\nYou received **${money(payout)}** ${db.currency}.\nYou found **${revealed.size}** tiles.`,COLOR_WIN,'⛏️ Goldmine ⛏️')],components:grid(true)});}
      const t=board[idx];
      if(t.type==='bomb'){finished=true;c.stop();saveData();return await i.update({embeds:[gembed(`💣 **You hit a bomb!**\n\nYou lost **${money(bet)}** ${db.currency}.`,COLOR_LOSE,'⛏️ Goldmine ⛏️')],components:grid(true)});}
      revealed.add(idx);
      if(t.type==='map'){const pool=shuffle([...Array(24).keys()].filter(x=>!revealed.has(x)&&board[x].type!=='bomb')).slice(0,3);for(const x of pool){revealed.add(x);if(board[x].type==='treasure')mult*=board[x].mult;}}else mult*=t.mult;
      if(revealed.size>=12){finished=true;c.stop();const payout=Math.floor(bet*mult);creditBank(user,payout);saveData();return await i.update({embeds:[gembed(`🏆 **Whole mine cleared!**\n\nYou received **${money(payout)}** ${db.currency}.`,COLOR_WIN,'⛏️ Goldmine ⛏️')],components:grid(true)});}
      return await i.update({embeds:[ge()],components:grid()});
    }catch(e){console.error('Goldmine interaction error:',e);if(!i.replied&&!i.deferred)await i.reply({content:'❌ Something went wrong.',ephemeral:true}).catch(()=>{});if(!finished){finished=true;c.stop();creditBank(user,bet);saveData();await msg.edit({embeds:[gembed('❌ Something went wrong. Your bet was returned.',COLOR_LOSE,'⛏️ Goldmine ⛏️')],components:grid(true)}).catch(()=>{});}}finally{busy=false;}
  });
  c.on('end',async()=>{if(finished)return;finished=true;creditBank(user,bet);saveData();await msg.edit({embeds:[gembed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,COLOR_INFO,'⛏️ Goldmine ⛏️')],components:grid(true)}).catch(()=>{});});
}

/* ============================================================
   SLOTS
   ============================================================ */

const SLOT_SYMBOLS = [
  { emoji: "🍒", weight: 32, triple: 2.5 },
  { emoji: "🍋", weight: 26, triple: 3.2 },
  { emoji: "🍊", weight: 20, triple: 4 },
  { emoji: "🍇", weight: 13, triple: 5 },
  { emoji: "⭐", weight: 7, triple: 8 },
  { emoji: "7️⃣", weight: 2, triple: 15 }
];

async function slots(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const reels = [weightedPick(SLOT_SYMBOLS), weightedPick(SLOT_SYMBOLS), weightedPick(SLOT_SYMBOLS)];
  const secret = reels.map(x => x.emoji).join(" | ");

  let mult = 0, line = "❌ No match.";
  if (reels[0].emoji === reels[1].emoji && reels[1].emoji === reels[2].emoji) {
    mult = reels[0].triple;
    line = `🎉 Triple ${reels[0].emoji}!`;
  } else if (reels[0].emoji === reels[1].emoji || reels[1].emoji === reels[2].emoji || reels[0].emoji === reels[2].emoji) {
    mult = 1.1;
    line = "🙂 Two matching symbols.";
  }

  await logAndPredict(message, `Slots started — bet ${money(bet)}.`, `🎰 Hidden reels: **${secret}**`, COLOR_INFO);

  const msg = await message.reply({ embeds: [gembed(`[ ❔ | ❔ | ❔ ]\n\n⏳ Result in **3 seconds**...`, COLOR_PLAYING, "🎰 Slots 🎰")] });

  for (let n = 2; n >= 1; n--) {
    await new Promise(r => setTimeout(r, 1000));
    await msg.edit({
      embeds: [gembed(`[ ${n === 2 ? reels[0].emoji : "❔"} | ${n === 2 ? "❔" : reels[1].emoji} | ❔ ]\n\n⏳ **${n} second${n === 1 ? "" : "s"}**...`, COLOR_PLAYING, "🎰 Slots 🎰")]
    }).catch(() => {});
  }

  const payout = Math.floor(bet * mult);
  if (payout) creditBank(user, payout);
  saveData();

  return msg.edit({
    embeds: [gembed(
      `[ ${secret} ]\n\n${line}\n\n${payout ? `🎉 Won **${money(payout)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`}`,
      payout ? COLOR_WIN : COLOR_LOSE, "🎰 Slots 🎰"
    )]
  });
}

/* ============================================================
   ROULETTE — with an animated spin
   ============================================================ */

const ROULETTE_RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

function rouletteColor(n) {
  return n === 0 ? "green" : ROULETTE_RED.has(n) ? "red" : "black";
}

function wheelEmojiFor(c) {
  return c === "red" ? "🔴" : c === "black" ? "⚫" : "🟢";
}

async function roulette(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  const choice = (args[1] || "").toLowerCase();
  const isNum = /^\d+$/.test(choice);

  if ((!isNum && !["red", "black", "green"].includes(choice)) || (isNum && (Number(choice) < 0 || Number(choice) > 36))) {
    return message.reply({ embeds: [gembed("❌ Usage: `$roulette <amount|half|all> <red/black/green/0-36>`", COLOR_LOSE)] });
  }

  spendFromBalance(user, bet);
  saveData();

  const result = random(0, 36);
  const color = rouletteColor(result);
  const win = isNum ? Number(choice) === result : choice === color;
  const mult = isNum ? 30 : (color === "green" ? 12 : 1.9);
  const payout = win ? Math.floor(bet * mult) : 0;

  await logAndPredict(message, `Roulette started — bet ${money(bet)}, choice ${choice}.`, `🎡 Hidden result: **${result} (${color})**`, COLOR_INFO);

  const msg = await message.reply({
    embeds: [gembed(`🎯 Bet: **${money(bet)}** ${db.currency}\n🎲 Choice: **${choice}**\n\n🔄 Spinning the wheel...`, COLOR_PLAYING, "🎡 Roulette 🎡")]
  });

  const frames = 10;
  for (let i = 0; i < frames; i++) {
    const isLast = i === frames - 1;
    const fakeNum = isLast ? result : random(0, 36);
    const fakeColor = rouletteColor(fakeNum);
    const delay = 180 + i * 90; // gradually slows down, like a real wheel

    await new Promise(r => setTimeout(r, delay));

    const track = Array.from({ length: frames }, (_, p) => p === i ? wheelEmojiFor(fakeColor) : "▫️").join("");

    await msg.edit({
      embeds: [gembed(
        `🎯 Bet: **${money(bet)}** ${db.currency}\n🎲 Choice: **${choice}**\n\n${track}\n\n🔄 Ball rolling... **${fakeNum}**`,
        COLOR_PLAYING, "🎡 Roulette 🎡"
      )]
    }).catch(() => {});
  }

  if (payout) creditBank(user, payout);
  saveData();

  await logEvent(
    message.guild,
    `Roulette result for <@${message.author.id}>: **${result} (${color})** — ${win ? `WIN ${money(payout)}` : `LOSS ${money(bet)}`}.`,
    win ? COLOR_WIN : COLOR_LOSE
  );

  return msg.edit({
    embeds: [gembed(
      `${wheelEmojiFor(color)} Landed on **${result}** (${color})\n\n${win ? `🎉 Won **${money(payout)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`}`,
      win ? COLOR_WIN : COLOR_LOSE, "🎡 Roulette 🎡"
    )]
  });
}

/* ============================================================
   WHEEL
   ============================================================ */

const WHEEL_SEGMENTS = [
  { mult: 0, weight: 45, label: "💀 Bust" },
  { mult: 1.1, weight: 28, label: "🙂 1.1x" },
  { mult: 1.4, weight: 16, label: "😀 1.4x" },
  { mult: 2, weight: 8, label: "😃 2x" },
  { mult: 4, weight: 2.5, label: "🤑 4x" },
  { mult: 8, weight: 0.5, label: "🏆 8x" }
];

async function wheel(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  const r = weightedPick(WHEEL_SEGMENTS);
  const p = Math.floor(bet * r.mult);
  if (p) creditBank(user, p);
  saveData();

  return message.reply({
    embeds: [gembed(
      `🎡 The wheel lands on **${r.label}**\n\n${p ? `🎉 Won **${money(p)}** ${db.currency}!` : `❌ Lost **${money(bet)}** ${db.currency}.`}`,
      p ? COLOR_WIN : COLOR_LOSE, "🎡 Wheel of Fortune 🎡"
    )]
  });
}

/* ============================================================
   CRASH — animated climb with a visual progress bar
   ============================================================ */

function rollCrashPoint() {
  const r = Math.random();
  const point = 0.98 / (1 - r * 0.94);
  return Math.max(1.02, Math.round(point * 100) / 100);
}

function crashBar(mult, crashed = false) {
  const maxBar = 20;
  const progress = Math.min(maxBar, Math.floor(Math.log(mult) / Math.log(1.15)));
  const filled = "🟩".repeat(progress);
  const empty = "⬛".repeat(maxBar - progress);
  return crashed ? `${filled}💥${empty}` : `${filled}🚀${empty}`;
}

function crashColor(mult) {
  if (mult >= 5) return COLOR_LOSE;
  if (mult >= 2) return COLOR_PLAYING;
  return COLOR_WIN;
}

async function crash(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  spendFromBalance(user, bet);
  saveData();

  const crashPoint = rollCrashPoint();
  let mult = 1;
  let finished = false;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`cr:cash:${message.author.id}`).setLabel("💰 Cashout").setStyle(ButtonStyle.Success)
  );

  const ge = () => gembed(
    `${crashBar(mult)}\n\n📈 Multiplier: **${mult.toFixed(2)}x**\n💵 Current value: **${money(bet * mult)}** ${db.currency}\n\n` +
    `Bet: **${money(bet)}** ${db.currency}\n\nCash out before it crashes!`,
    crashColor(mult), "🚀 Crash 🚀"
  );

  const msg = await message.reply({ embeds: [ge()], components: [row] });
  const c = msg.createMessageComponentCollector({ time: 30000 });

  const interval = setInterval(async () => {
    if (finished) return;

    mult = Math.round(mult * 1.07 * 100) / 100;

    if (mult >= crashPoint) {
      finished = true;
      clearInterval(interval);
      c.stop();
      saveData();

      await msg.edit({
        embeds: [gembed(
          `${crashBar(crashPoint, true)}\n\n💥 Crashed at **${crashPoint.toFixed(2)}x**!\n\nLost **${money(bet)}** ${db.currency}.`,
          COLOR_LOSE, "🚀 Crash 🚀"
        )],
        components: [disabledRow(row)]
      }).catch(() => {});
      return;
    }

    await msg.edit({ embeds: [ge()], components: [row] }).catch(() => {});
  }, 700);

  c.on("collect", async i => {
    if (i.user.id !== message.author.id) return i.reply({ content: "❌ This isn't your game.", ephemeral: true });
    if (finished) return;

    finished = true;
    clearInterval(interval);
    c.stop();

    const payout = Math.floor(bet * mult);
    creditBank(user, payout);
    saveData();

    await i.update({
      embeds: [gembed(
        `${crashBar(mult)}\n\n💰 Cashed out at **${mult.toFixed(2)}x**!\n\nPayout: **${money(payout)}** ${db.currency}.`,
        COLOR_WIN, "🚀 Crash 🚀"
      )],
      components: [disabledRow(row)]
    });
  });

  c.on("end", async () => {
    if (finished) return;
    finished = true;
    clearInterval(interval);
    creditBank(user, bet);
    saveData();

    await msg.edit({
      embeds: [gembed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`, COLOR_INFO, "🚀 Crash 🚀")],
      components: [disabledRow(row)]
    }).catch(() => {});
  });
}

/* ============================================================
   DAILY (renamed from "summer")
   ============================================================ */

const DAILY_PRIZES = [
  { amount: 1750000, weight: 45, label: "1,750,000" },
  { amount: 25000000, weight: 30, label: "25,000,000" },
  { amount: 65000000, weight: 15, label: "65,000,000" },
  { amount: 100000000, weight: 5, label: "100,000,000 JACKPOT" }
];

async function daily(message, user) {
  const last = db.daily[message.author.id] || 0;
  const left = 24 * 60 * 60 * 1000 - (Date.now() - last);

  if (left > 0) {
    return message.reply({ embeds: [gembed(`⏳ Your Daily wheel is ready again in **${formatDuration(left)}**.`, COLOR_LOSE, "☀️ Daily ☀️")] });
  }

  const result = weightedPick(DAILY_PRIZES);
  db.daily[message.author.id] = Date.now();
  saveData();

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`daily:spin:${message.author.id}`).setLabel("☀️ SPIN").setStyle(ButtonStyle.Primary)
  );

  const msg = await message.reply({
    embeds: [gembed(
      `🎁 1,750,000 — 45%\n🎁 25,000,000 — 30%\n🎁 65,000,000 — 15%\n🏆 100,000,000 JACKPOT — 5%\n\nPress **SPIN**. You get one spin every 24 hours.`,
      COLOR_PURPLE, "☀️ Daily ☀️"
    )],
    components: [row]
  });

  const c = msg.createMessageComponentCollector({ time: 30000, max: 1 });

  c.on("collect", async i => {
    if (i.user.id !== message.author.id) return i.reply({ content: "❌ This isn't your wheel.", ephemeral: true });

    await i.deferUpdate();

    for (let n = 0; n < 8; n++) {
      await new Promise(r => setTimeout(r, 120));
      await msg.edit({
        embeds: [gembed(`🔄 ${["1,750,000", "25,000,000", "65,000,000", "100,000,000 JACKPOT"][n % 4]}\n\n🎡 Spinning...`, COLOR_PURPLE, "☀️ Daily ☀️")],
        components: []
      }).catch(() => {});
    }

    creditBank(user, result.amount);
    saveData();

    await logEvent(message.guild, `☀️ Daily result for <@${message.author.id}>: **${result.label}** ${db.currency}.`, COLOR_WIN);
    await secretDM(`☀️ Daily result: **${message.author.tag}** won **${result.label}**.`);

    await msg.edit({
      embeds: [gembed(
        `🏆 Prize: **${result.label}** ${db.currency}\n\nYour new total: **${money(totalBalance(user))}** ${db.currency}.`,
        COLOR_WIN, "☀️ Daily ☀️"
      )],
      components: []
    }).catch(() => {});
  });
}

/* ============================================================
   INFO
   ============================================================ */

function buildInfoEmbed() {
  return embed([
    "**🃏 Blackjack — `$bj <amount|half|all>`**", "Normal blackjack odds. Hit / Stand / Double. Natural pays 2.5x.", "",
    "**🐔 Cockfight — `$cf <amount|half|all>`**", "Starts at 45% and rises gradually, capped at 60%.", "",
    "**🎲 Higher or Lower — `$hl <amount|half|all>`**", "Choose Higher, Same or Lower. Same pays 8x.", "",
    "**🍀 CoinFlip — `$ht <amount|half|all>`**", "Head/Tail, pays 2x.", "",
    "**💣 Mines — `$mines <amount|half|all>`**", "3x3, one bomb. Multipliers: 1.05x → 5.8x. Cash out anytime.", "",
    "**⛏️ Goldmine — `$gm <amount|half|all>`**", "24 tiles, 12 bombs, treasure multipliers compound.", "",
    "**🎰 Slots — `$slots <amount|half|all>`**", "3 reels, 3-second reveal.", "",
    "**🎡 Roulette — `$roulette <amount|half|all> <red/black/green/0-36>`**", "Red/Black = 1.9x, Green = 12x, exact number = 30x. Animated spin.", "",
    "**🎡 Wheel — `$wheel <amount|half|all>`**", "0x, 1.1x, 1.4x, 2x, 4x or 8x.", "",
    "**🚀 Crash — `$crash <amount|half|all>`**", "Cash out before the multiplier crashes. Animated climb.", "",
    "**🎲 Random — `$random <amount|half|all>`**", "One mystery roll.", "",
    "**☀️ Daily — `$daily`**", "One free spin every 24 hours.", "",
    `_Minimum bet: ${money(MIN_BET)} ${db.currency}. ${amountHelp()}`
  ].join("\n"), COLOR_INFO, "📖 Casino Bot — Rules");
}

/* ============================================================
   LOGIN
   ============================================================ */

if (!process.env.DISCORD_TOKEN) console.error("❌ DISCORD_TOKEN is missing.");
else client.login(process.env.DISCORD_TOKEN).catch(e => console.error("❌ Discord login failed:", e));