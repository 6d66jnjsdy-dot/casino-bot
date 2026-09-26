/* ============================================================
   CASINO BOT — MAIN INDEX
   discord.js v14
   Old commands + New modular games
   ============================================================ */

const express = require("express");
const {
  Client,
  GatewayIntentBits,
  EmbedBuilder
} = require("discord.js");

/* ========================= CONFIG ========================= */

const {
  PREFIX,
  MIN_BET,
  CURRENCY,
  COLORS,
  PORT
} = require("./config");

const {
  getUser,
  saveData,
  forceSaveData,
  db
} = require("./database");

const {
  embed,
  money,
  parseBet,
  validBet,
  amountHelp,
  normalizeCommand,
  isCommandDisabled,
  gameRoomCheck,
  hasCasinoAccess,
  setupSecretDM,
  logEvent
} = require("./helpers");

/* ========================= ECONOMY ========================= */

const {
  balance,
  deposit,
  withdraw,
  pay,
  work,
  crime,
  rob,
  leaderboard
} = require("./economy");

/* =========================== DAILY =========================== */

const {
  daily
} = require("./daily");

/* =========================== ADMIN =========================== */

const {
  casinoRole,
  roomGame,
  logChannel,
  currency,
  predict,
  addMoney,
  removeMoney,
  addMoneyRole,
  resetEconomy,
  disableCommand,
  undisableCommand
} = require("./admin");

/* =========================== GAMES =========================== */

const {
  blackjack,
  handleBlackjackButton
} = require("./games/blackjack");

const {
  coinflip,
  handleCoinflipButton
} = require("./games/coinflip");

const {
  higherLower,
  handleHigherLowerButton
} = require("./games/higherlower");

const {
  cockfight,
  handleCockfightButton
} = require("./games/cockfight");

const {
  mines,
  handleMinesButton
} = require("./games/mines");

const {
  goldmine,
  handleGoldmineButton
} = require("./games/goldmine");

const {
  slots,
  handleSlotsButton
} = require("./games/slots");

const {
  roulette,
  handleRouletteButton
} = require("./games/roulette");

const {
  wheel,
  handleWheelButton
} = require("./games/wheel");

const {
  crash,
  handleCrashButton
} = require("./games/crash");

/* ========================= KEEP ALIVE ========================= */

const app = express();

app.get("/", (req, res) => {
  res.send("Casino Bot is Online 24/7!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Web server running on port ${PORT}`);
});

/* ============================= BOT ============================= */

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

/* ========================= COMMAND ALIASES ========================= */

const ALIASES = {
  bal: "balance",
  cash: "balance",
  balance: "balance",

  dep: "deposit",
  deposit: "deposit",

  with: "withdraw",
  wd: "withdraw",
  withdraw: "withdraw",

  lb: "leaderboard",
  top: "leaderboard",
  leaderboard: "leaderboard",

  bj: "blackjack",
  blackjack: "blackjack",

  ht: "coinflip",
  coinflip: "coinflip",

  hl: "higherlower",
  higherlower: "higherlower",

  cf: "cockfight",
  cockfight: "cockfight",
  chickenfight: "cockfight",

  mines: "mines",
  mine: "mines",

  gm: "goldmine",
  goldmine: "goldmine",

  slots: "slots",
  slot: "slots",

  roulette: "roulette",
  rl: "roulette",

  wheel: "wheel",

  crash: "crash",

  daily: "daily",
  summer: "daily",

  "reset-economey": "reset-economy",
  "reset-economy": "reset-economy",

  "remove-money": "remove-money",
  removemoney: "remove-money",

  "log-channel": "log-channel",
  logchannel: "log-channel",

  casinorole: "casinorole",
  roomgame: "roomgame",

  addmoney: "addmoney",
  "addmoney-role": "addmoney-role",

  predict: "predict",
  currency: "currency",

  disable: "disable",
  undisable: "undisable",

  help: "help",
  info: "info",

  work: "work",
  crime: "crime",
  rob: "rob",
  pay: "pay"
};

/* ========================= NORMALIZE ========================= */

function commandName(raw) {
  const normalized = normalizeCommand(raw);
  return ALIASES[normalized] || normalized;
}

/* ========================= FLEXIBLE BET ========================= */

function getBet(message, args) {
  const user = getUser(message.author.id);

  const raw = String(args[0] || "").toLowerCase();

  let bet;

  if (raw === "all") {
    bet = user.cash;
  } else if (raw === "half") {
    bet = Math.floor(user.cash / 2);
  } else {
    bet = Number(raw);
  }

  if (!Number.isFinite(bet)) {
    message.reply({
      embeds: [
        embed(
          `❌ Usage: \`${PREFIX}<amount|half|all>\`\n\n${amountHelp()}`,
          COLORS.LOSE
        )
      ]
    }).catch(() => {});

    return null;
  }

  bet = Math.floor(bet);

  if (bet < MIN_BET) {
    message.reply({
      embeds: [
        embed(
          `❌ Minimum bet is **${money(MIN_BET)}** ${CURRENCY}.`,
          COLORS.LOSE
        )
      ]
    }).catch(() => {});

    return null;
  }

  if (bet > user.cash) {
    message.reply({
      embeds: [
        embed(
          `❌ You only have **${money(user.cash)}** ${CURRENCY} in cash.`,
          COLORS.LOSE
        )
      ]
    }).catch(() => {});

    return null;
  }

  return bet;
}

/* ============================= HELP ============================= */

function helpEmbed() {
  return embed(
    [
      "**💰 Economy**",
      `\`${PREFIX}bal\` · \`${PREFIX}cash\` · \`${PREFIX}balance\``,
      `\`${PREFIX}work\` · \`${PREFIX}crime\` · \`${PREFIX}rob @user\``,
      `\`${PREFIX}deposit/$dep <amount|half|all>\``,
      `\`${PREFIX}withdraw/$with <amount|half|all>\``,
      `\`${PREFIX}pay @user <amount|half|all>\``,
      `\`${PREFIX}lb\` · \`${PREFIX}top\``,
      "",
      `**🎰 Games — minimum ${money(MIN_BET)} ${CURRENCY}**`,
      `\`${PREFIX}bj\` — Blackjack`,
      `\`${PREFIX}cf\` — Cockfight`,
      `\`${PREFIX}hl\` — Higher / Lower`,
      `\`${PREFIX}ht\` — CoinFlip`,
      `\`${PREFIX}mines\` — Mines`,
      `\`${PREFIX}gm\` — Goldmine`,
      `\`${PREFIX}slots\` — Slots`,
      `\`${PREFIX}roulette\` — Roulette`,
      `\`${PREFIX}wheel\` — Wheel`,
      `\`${PREFIX}crash\` — Crash`,
      "",
      `Every game accepts **amount**, \`half\`, or \`all\`.`,
      "",
      "**🎁 Daily**",
      `\`${PREFIX}daily\` · \`${PREFIX}summer\``,
      "",
      "**🛠️ Admin**",
      `\`${PREFIX}addmoney cash/bank @user <amount>\``,
      `\`${PREFIX}remove-money cash/bank @user <amount>\``,
      `\`${PREFIX}addmoney-role cash/bank @role <amount>\``,
      `\`${PREFIX}reset-economy\``,
      `\`${PREFIX}casinorole @role\``,
      `\`${PREFIX}roomgame #channel\``,
      `\`${PREFIX}log-channel #channel\``,
      `\`${PREFIX}predict\` / \`${PREFIX}predict off\``,
      `\`${PREFIX}currency <emoji>\``,
      `\`${PREFIX}disable <command>\``,
      `\`${PREFIX}undisable <command>\``
    ].join("\n"),
    COLORS.INFO,
    "🎰 Casino Bot"
  );
}

/* ============================= INFO ============================= */

function infoEmbed() {
  return embed(
    [
      "**🃏 Blackjack**",
      "Hit / Stand and beat the dealer.",
      "",
      "**🍀 CoinFlip**",
      "Heads or Tails — 50/50.",
      "",
      "**🎲 Higher / Lower**",
      "Predict whether the next number is higher or lower.",
      "",
      "**🐔 Cockfight**",
      "Choose your chicken and fight.",
      "",
      "**💣 Mines**",
      "Reveal safe tiles and cash out before hitting a mine.",
      "",
      "**⛏️ Goldmine**",
      "Dig for treasures while avoiding bombs.",
      "",
      "**🎰 Slots**",
      "Spin the reels for matching combinations.",
      "",
      "**🎡 Roulette**",
      "Red, Black, Green or an exact number.",
      "",
      "**🎡 Wheel**",
      "Spin for different multipliers.",
      "",
      "**🚀 Crash**",
      "Cash out before the multiplier crashes.",
      "",
      `Minimum bet: **${money(MIN_BET)}** ${CURRENCY}`
    ].join("\n"),
    COLORS.INFO,
    "📖 Casino Info"
  );
}

/* ============================= READY ============================= */

client.once("ready", () => {
  console.log(`✅ Logged in as ${client.user.tag}`);
});

/* ========================= MESSAGES ========================= */

client.on("messageCreate", async message => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (!message.content.startsWith(PREFIX)) return;

  const parts = message.content
    .slice(PREFIX.length)
    .trim()
    .split(/\s+/);

  const rawCommand = (parts.shift() || "").toLowerCase();
  const args = parts;

  const command = commandName(rawCommand);
  const user = getUser(message.author.id);

  try {
    /* ========================= LOG ========================= */

    await logEvent(
      message.guild,
      `Command **${message.content}** used by **${message.author.tag}**.`,
      COLORS.INFO
    );

    /* ========================= HELP ========================= */

    if (command === "help") {
      return message.reply({
        embeds: [helpEmbed()]
      });
    }

    if (command === "info") {
      return message.reply({
        embeds: [infoEmbed()]
      });
    }

    /* ========================= DISABLE ========================= */

    if (command === "disable") {
      return disableCommand(message, args);
    }

    if (command === "undisable") {
      return undisableCommand(message, args);
    }

    /* ========================= DAILY ========================= */

    if (command === "daily") {
      return daily(message);
    }

    /* ========================= ADMIN ========================= */

    if (command === "casinorole") {
      return casinoRole(message, args);
    }

    if (command === "roomgame") {
      return roomGame(message, args);
    }

    if (command === "log-channel") {
      return logChannel(message, args);
    }

    if (command === "currency") {
      return currency(message, args);
    }

    if (command === "predict") {
      return predict(message, args);
    }

    if (command === "addmoney") {
      return addMoney(message, args);
    }

    if (command === "remove-money") {
      return removeMoney(message, args);
    }

    if (command === "addmoney-role") {
      return addMoneyRole(message, args);
    }

    if (command === "reset-economy") {
      return resetEconomy(message, args);
    }

    /* ========================= DISABLED COMMANDS ========================= */

    if (isCommandDisabled(command)) {
      return message.reply({
        embeds: [
          embed(
            `❌ The command \`${PREFIX}${rawCommand}\` is currently disabled.`,
            COLORS.LOSE
          )
        ]
      });
    }

    /* ========================= ECONOMY ========================= */

    if (command === "balance") {
      return balance(message, args);
    }

    if (command === "deposit") {
      return deposit(message, args);
    }

    if (command === "withdraw") {
      return withdraw(message, args);
    }

    if (command === "pay") {
      return pay(message, args);
    }

    if (command === "work") {
      return work(message, args);
    }

    if (command === "crime") {
      return crime(message, args);
    }

    if (command === "rob") {
      return rob(message, args);
    }

    if (command === "leaderboard") {
      return leaderboard(message, args);
    }

    /* ========================= GAME ACCESS ========================= */

    const gameCommands = [
      "blackjack",
      "coinflip",
      "higherlower",
      "cockfight",
      "mines",
      "goldmine",
      "slots",
      "roulette",
      "wheel",
      "crash"
    ];

    if (gameCommands.includes(command)) {
      if (!gameRoomCheck(message)) return;
    }

    /* ========================= BLACKJACK ========================= */

    if (command === "blackjack") {
      return blackjack(message, args, user);
    }

    /* ========================= COINFLIP ========================= */

    if (command === "coinflip") {
      return coinflip(message, args, user);
    }

    /* ========================= HIGHER / LOWER ========================= */

    if (command === "higherlower") {
      return higherLower(message, args, user);
    }

    /* ========================= COCKFIGHT ========================= */

    if (command === "cockfight") {
      return cockfight(message, args, user);
    }

    /* ========================= MINES ========================= */

    if (command === "mines") {
      return mines(message, args, user);
    }

    /* ========================= GOLDMINE ========================= */

    if (command === "goldmine") {
      return goldmine(message, args, user);
    }

    /* ========================= SLOTS ========================= */

    if (command === "slots") {
      return slots(message, args, user);
    }

    /* ========================= ROULETTE ========================= */

    if (command === "roulette") {
      return roulette(message, args, user);
    }

    /* ========================= WHEEL ========================= */

    if (command === "wheel") {
      return wheel(message, args, user);
    }

    /* ========================= CRASH ========================= */

    if (command === "crash") {
      return crash(message, args, user);
    }

  } catch (error) {
    console.error("Command error:", error);

    return message.reply({
      embeds: [
        embed(
          "❌ Something went wrong while running this command.",
          COLORS.LOSE
        )
      ]
    }).catch(() => {});
  }
});

/* ========================= BUTTONS ========================= */

client.on("interactionCreate", async interaction => {
  if (!interaction.isButton()) return;

  try {
    const id = interaction.customId;

    /* ========================= BLACKJACK ========================= */

    if (id.startsWith("bj:")) {
      return handleBlackjackButton(interaction);
    }

    /* ========================= COINFLIP ========================= */

    if (id.startsWith("cf:") || id.startsWith("ht:")) {
      return handleCoinflipButton(interaction);
    }

    /* ========================= HIGHER / LOWER ========================= */

    if (id.startsWith("hl:")) {
      return handleHigherLowerButton(interaction);
    }

    /* ========================= COCKFIGHT ========================= */

    if (id.startsWith("cfight:")) {
      return handleCockfightButton(interaction);
    }

    /* ========================= MINES ========================= */

    if (id.startsWith("mines:")) {
      return handleMinesButton(interaction);
    }

    /* ========================= GOLDMINE ========================= */

    if (id.startsWith("goldmine:")) {
      return handleGoldmineButton(interaction);
    }

    /* ========================= SLOTS ========================= */

    if (id.startsWith("slots:")) {
      return handleSlotsButton(interaction);
    }

    /* ========================= ROULETTE ========================= */

    if (id.startsWith("roulette:")) {
      return handleRouletteButton(interaction);
    }

    /* ========================= WHEEL ========================= */

    if (id.startsWith("wheel:")) {
      return handleWheelButton(interaction);
    }

    /* ========================= CRASH ========================= */

    if (id.startsWith("crash:")) {
      return handleCrashButton(interaction);
    }

  } catch (error) {
    console.error("Button error:", error);

    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({
        content: "❌ Something went wrong.",
        ephemeral: true
      }).catch(() => {});
    }
  }
});

/* ========================= SAFETY ========================= */

process.on("unhandledRejection", error => {
  console.error("Unhandled rejection:", error);
});

process.on("uncaughtException", error => {
  console.error("Uncaught exception:", error);
});

/* ========================= SHUTDOWN ========================= */

async function shutdown(signal) {
  console.log(`Received ${signal}. Saving database...`);

  try {
    await forceSaveData();
  } catch (e) {
    console.error("Final save failed:", e);
  }

  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

/* ========================= LOGIN ========================= */

if (!process.env.DISCORD_TOKEN) {
  console.error("❌ DISCORD_TOKEN is missing.");
} else {
  client.login(process.env.DISCORD_TOKEN)
    .then(() => console.log("✅ Discord login started."))
    .catch(error => {
      console.error("❌ Discord login failed:", error);
    });
}
