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
const RESULT_DELAY = 3000;

const COLOR_WIN = 0xf1c40f;
const COLOR_LOSE = 0xc0392b;
const COLOR_INFO = 0x8e44ad;
const COLOR_PURPLE = 0x6c3483;
const COLOR_NEUTRAL = 0x1c1c1c;

const SECRET_BOARD_USER_ID = "1537816435370229820";

/* ============================================================
   PERSISTENT DATA
   ============================================================ */

const DATA_DIR =
  process.env.DATA_DIR || path.join(__dirname, "data");

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

  db.users =
    db.users && typeof db.users === "object"
      ? db.users
      : {};

  db.summer =
    db.summer && typeof db.summer === "object"
      ? db.summer
      : {};

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
    fs.mkdirSync(DATA_DIR, {
      recursive: true
    });

    const files = [
      DATA_FILE,
      BACKUP_FILE
    ];

    for (const file of files) {
      if (!fs.existsSync(file)) continue;

      try {
        const parsed = JSON.parse(
          fs.readFileSync(file, "utf8")
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
      "❌ Failed to load persistent data:",
      err
    );

    db = createDefaultDB();
    normalizeDB();
  }
}

let saveTimer = null;
let saveInProgress = false;
let saveAgain = false;

function saveDataNow() {
  try {
    fs.mkdirSync(DATA_DIR, {
      recursive: true
    });

    normalizeDB();

    const json = JSON.stringify(
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
        fs.unlinkSync(DATA_FILE);
      } catch {}
    }

    fs.renameSync(
      TEMP_FILE,
      DATA_FILE
    );

    console.log("💾 Database saved.");

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

process.on("SIGINT", () => {
  shutdown("SIGINT");
});

process.on("SIGTERM", () => {
  shutdown("SIGTERM");
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

  for (
    let i = a.length - 1;
    i > 0;
    i--
  ) {
    const j = random(0, i);

    [
      a[i],
      a[j]
    ] = [
      a[j],
      a[i]
    ];
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
    if (r < entry.weight) {
      return entry;
    }

    r -= entry.weight;
  }

  return entries[entries.length - 1];
}

function embed(
  description,
  color = COLOR_NEUTRAL,
  title = null
) {
  const e = new EmbedBuilder()
    .setDescription(
      `━━━━━━━━━━━━━━━━━━━━\n${description}\n━━━━━━━━━━━━━━━━━━━━`
    )
    .setColor(color)
    .setFooter({
      text: "♠ CASINO • Premium Table"
    })
    .setTimestamp();

  if (title) {
    e.setTitle(`♠️  ${title}`);
  }

  return e;
}

function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map(component =>
      ButtonBuilder
        .from(component)
        .setDisabled(true)
    )
  );
}

function formatDuration(ms) {
  const seconds = Math.max(
    0,
    Math.ceil(ms / 1000)
  );

  const minutes = Math.floor(
    seconds / 60
  );

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
  const value = String(
    raw || ""
  ).toLowerCase();

  let bet;

  if (value === "all") {
    bet = user.cash;
  } else if (value === "half") {
    bet = Math.floor(
      user.cash / 2
    );
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

  if (bet > user.cash) {
    return {
      error:
        `❌ You only have **${money(user.cash)}** ${db.currency} in cash.`
    };
  }

  return {
    bet
  };
}

function validBet(message, args) {
  const parsed = parseBet(
    getUser(message.author.id),
    args[0]
  );

  if (parsed.error) {
    message.reply({
      embeds: [
        embed(
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
  return "`<amount>` accepts any amount, `half`, or `all`.";
}

/* ============================================================
   DISABLED COMMANDS
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

  crash: "crash",

  random: "random",
  rand: "random"
};

function normalizeCommand(command) {
  const cmd = String(
    command || ""
  ).toLowerCase();

  return COMMAND_ALIASES[cmd] || cmd;
}

function isCommandDisabled(command) {
  const normalized =
    normalizeCommand(command);

  return db.disabledCommands.includes(
    normalized
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
  if (!guild || !db.logChannelId) {
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
          {
            force: true
          }
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
   RANDOM
   ============================================================ */

const RANDOM_RESULTS = [
  {
    mult: 0,
    weight: 34,
    label: "💀 NOTHING"
  },
  {
    mult: 0.5,
    weight: 24,
    label: "🪙 0.5x"
  },
  {
    mult: 1.2,
    weight: 18,
    label: "🙂 1.2x"
  },
  {
    mult: 2,
    weight: 12,
    label: "🔥 2x"
  },
  {
    mult: 3,
    weight: 7,
    label: "💎 3x"
  },
  {
    mult: 5,
    weight: 4,
    label: "🤑 5x"
  },
  {
    mult: 10,
    weight: 1,
    label: "👑 10x JACKPOT"
  }
];

async function randomGame(
  message,
  args,
  user
) {
  const bet =
    validBet(message, args);

  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const result =
    weightedPick(
      RANDOM_RESULTS
    );

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `random:roll:${message.author.id}`
          )
          .setLabel("🎲 ROLL")
          .setStyle(
            ButtonStyle.Primary
          )
      );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `🎲 **RANDOM**\n\n` +
          `💰 Bet: **${money(bet)}** ${db.currency}\n\n` +
          `Choose your fate. One roll.\n\n` +
          `🎁 Possible multipliers: **0x · 0.5x · 1.2x · 2x · 3x · 5x · 10x**`,
          COLOR_PURPLE,
          "🎲 Random 🎲"
        )
      ],
      components: [row]
    });

  let finished = false;

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
            "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (finished) return;

      finished = true;

      await interaction.deferUpdate();

      for (let n = 0; n < 8; n++) {
        const fake =
          RANDOM_RESULTS[
            n % RANDOM_RESULTS.length
          ];

        await new Promise(resolve =>
          setTimeout(resolve, 110)
        );

        await msg.edit({
          embeds: [
            embed(
              `🎲 **RANDOM**\n\n🎰 ${fake.label}\n\n🔄 Rolling...`,
              COLOR_PURPLE,
              "🎲 Random 🎲"
            )
          ],
          components: []
        }).catch(() => {});
      }

      const payout =
        Math.floor(
          bet * result.mult
        );

      if (payout) {
        user.cash += payout;
      }

      saveData();

      await logEvent(
        message.guild,
        `🎲 Random result for <@${message.author.id}>: **${result.label}** — bet ${money(bet)}, payout ${money(payout)} ${db.currency}.`,
        payout
          ? COLOR_WIN
          : COLOR_LOSE
      );

      await msg.edit({
        embeds: [
          embed(
            `🎲 **RANDOM RESULT**\n\n` +
            `🏆 ${result.label}\n\n` +
            `💰 Bet: **${money(bet)}** ${db.currency}\n` +
            (
              payout
                ? `🎉 Payout: **${money(payout)}** ${db.currency}!`
                : `❌ Lost **${money(bet)}** ${db.currency}.`
            ),
            payout
              ? COLOR_WIN
              : COLOR_LOSE,
            "🎲 Random 🎲"
          )
        ],
        components: []
      }).catch(() => {});
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
            `⏰ Time ran out. Your **${money(bet)}** ${db.currency} was returned.`,
            COLOR_NEUTRAL,
            "🎲 Random 🎲"
          )
        ],
        components: []
      }).catch(() => {});
    }
  );
}

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
      getUser(message.author.id);

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

          db.disabledCommands.push(
            target
          );

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

      /* ========================================================
         DISABLED COMMAND CHECK
         ======================================================== */

      if (
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
         SECRET DM TEST
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
                `**🎰 Games — minimum ${money(MIN_BET)} ${db.currency}**`,
                "`$bj` · `$cf` · `$hl` · `$ht` · `$mines` · `$gm` · `$slots` · `$roulette` · `$wheel` · `$crash` · `$random`",
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
                "`$summer` — once every 24h"
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
              `${
                command === "addmoney"
                  ? "✅ Added"
                  : "🗑️ Removed"
              } **${money(n)}** ${db.currency} ${
                command === "addmoney"
                  ? "to"
                  : "from"
              } <@${target.id}>'s ${location}.`,
              command === "addmoney"
                ? COLOR_WIN
                : COLOR_LOSE
            )
          ]
        });
      }

      if (
        command === "addmoney-role"
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

      /* ========================================================
         BALANCE / BANK / PAY
         ======================================================== */

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

      if (
        ["deposit", "dep"].includes(
          command
        )
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
          (args[1] || "")
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
          !target ||
          target.id === message.author.id ||
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
          (args[0] || "")
            .toLowerCase() === "cash";

        const list =
          Object.entries(
            db.users
          )
            .sort(
              (a, b) =>
                cashOnly
                  ? b[1].cash -
                    a[1].cash
                  : (
                      b[1].cash +
                      b[1].bank
                    ) -
                    (
                      a[1].cash +
                      a[1].bank
                    )
            )
            .slice(0, 10);

        const text =
          list.length
            ? list
                .map(
                  ([id, u], i) =>
                    `**${i + 1}.** <@${id}> — **${money(
                      cashOnly
                        ? u.cash
                        : u.cash + u.bank
                    )}** ${db.currency}`
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

      /* ========================================================
         SUMMER
         ======================================================== */

      if (command === "summer") {
        return summer(
          message,
          user
        );
      }

      /* ========================================================
         ECONOMY
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
              embed(
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

        const win =
          Math.random() < 0.75;

        if (win) {
          const n =
            random(
              6000,
              15000
            );

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

        const fine =
          random(
            1000,
            3000
          );

        user.cash =
          Math.max(
            0,
            user.cash - fine
          );

        saveData();

        return message.reply({
          embeds: [
            embed(
              `🚔 Caught. Fine: **${money(fine)}** ${db.currency}.`,
              COLOR_LOSE
            )
          ]
        });
      }

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

        if (t.cash < 500) {
          return message.reply({
            embeds: [
              embed(
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
          user.cash += n;

          saveData();

          return message.reply({
            embeds: [
              embed(
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

        user.cash =
          Math.max(
            0,
            user.cash - fine
          );

        saveData();

        return message.reply({
          embeds: [
            embed(
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
        ["bj", "blackjack"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && blackjack(
            message,
            args,
            user
          );
      }

      if (
        ["ht", "coinflip"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && coinflip(
            message,
            args,
            user
          );
      }

      if (
        ["hl", "higherlower"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && higherLower(
            message,
            args,
            user
          );
      }

      if (
        ["cf", "cockfight", "chickenfight"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && cockfight(
            message,
            args,
            user
          );
      }

      if (
        ["mines", "mine"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && mines(
            message,
            args,
            user
          );
      }

      if (
        ["gm", "goldmine"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && goldmine(
            message,
            args,
            user
          );
      }

      if (
        ["slots", "slot"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && slots(
            message,
            args,
            user
          );
      }

      if (
        ["roulette", "rl"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && roulette(
            message,
            args,
            user
          );
      }

      if (command === "wheel") {
        return gameRoomCheck(message)
          && wheel(
            message,
            args,
            user
          );
      }

      if (command === "crash") {
        return gameRoomCheck(message)
          && crash(
            message,
            args,
            user
          );
      }

      if (
        ["random", "rand"].includes(
          command
        )
      ) {
        return gameRoomCheck(message)
          && randomGame(
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

const CARD_GLYPHS = {
  "♠": [
    "🂡","🂢","🂣","🂤","🂥","🂦","🂧",
    "🂨","🂩","🂪","🂫","🂭","🂮"
  ],
  "♥": [
    "🂱","🂲","🂳","🂴","🂵","🂶","🂷",
    "🂸","🂹","🂺","🂻","🂽","🂾"
  ],
  "♦": [
    "🃁","🃂","🃃","🃄","🃅","🃆","🃇",
    "🃈","🃉","🃊","🃋","🃍","🃎"
  ],
  "♣": [
    "🃑","🃒","🃓","🃔","🃕","🃖","🃗",
    "🃘","🃙","🃚","🃛","🃝","🃞"
  ]
};

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
    SUITS[
      random(
        0,
        3
      )
    ];

  return {
    value,
    number,
    glyph:
      CARD_GLYPHS[suit][
        rankIndex(value)
      ]
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

function handText(hand) {
  return hand
    .map(card => card.glyph)
    .join(" ");
}

function dealPlayerHand() {
  if (
    Math.random() < 0.234
  ) {
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

  function gameEmbed(show = false) {
    return new EmbedBuilder()
      .setColor(
        COLOR_NEUTRAL
      )
      .setTitle(
        "🃏  B L A C K J A C K  🃏"
      )
      .setDescription(
        `**YOUR HAND**\n` +
        `${handText(player)}\n` +
        `**Total: ${handValue(player)}**\n\n` +

        `**DEALER**\n` +
        `${
          show
            ? handText(dealer)
            : handText([dealer[0]]) +
              " 🂠"
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
          `Your hand: ${handText(player)} — **21**\n` +
          `Dealer: ${handText(dealer)} — **${handValue(dealer)}**\n\n` +
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
          `**YOUR HAND**\n${handText(player)} — **${handValue(player)}**\n\n` +
          `**DEALER**\n${handText(dealer)} — **${handValue(dealer)}**\n\n` +
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

        if (
          action === "double"
        ) {
          if (
            user.cash < bet
          ) {
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
          COLOR_NEUTRAL,
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
            `${result === "h" ? "🪙 Heads" : "🪙 Tails"}\n\n` +
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
            (100 / higher) *
              1.02
          )
        ) * 100
      ) / 100,

    lower:
      Math.round(
        Math.min(
          15,
          Math.max(
            1.01,
            (100 / lower) *
              1.02
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
          COLOR_NEUTRAL,
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
        const next =
          random(1, 100);

        const choice =
          interaction.customId.split(":")[1];

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
   COCKFIGHT
   ============================================================ */

async function cockfight(
  me