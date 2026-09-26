/* ============================================================
   CASINO BOT — MAIN INDEX
   discord.js v14
   ============================================================ */

const express = require("express");

const {
  Client,
  GatewayIntentBits
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
  db,
  getUser,
  forceSaveData
} = require("./database");

const {
  money,
  parseBet,
  amountHelp,
  normalizeCommand,
  isCommandDisabled,
  gameRoomCheck,
  setupSecretDM,
  logEvent,
  embed
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

/* ========================= DAILY ========================= */

const {
  daily
} = require("./daily");

/* ========================= ADMIN ========================= */

const {
  casinoRole,
  roomGame,
  logChannel,
  currency,
  predict,
  addMoney,
  removeMoney,
  resetEconomy,
  disable,
  undisable
} = require("./admin");

/* ========================= GAMES ========================= */

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
  cockfight
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

/* ============================================================
   KEEP ALIVE
   ============================================================ */

const app = express();

app.get("/", (req, res) => {
  res.send("Casino Bot is Online 24/7!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`🌐 Web server running on port ${PORT}`);
});

/* ============================================================
   DISCORD CLIENT
   ============================================================ */

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

/* ============================================================
   COMMAND ALIASES
   ============================================================ */

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

function commandName(raw) {
  const normalized = normalizeCommand(raw);
  return ALIASES[normalized] || normalized;
}

/* ============================================================
   BET
   ============================================================ */

function getBet(message, args) {
  const user = getUser(message.author.id);

  const parsed = parseBet(
    user,
    args[0]
  );

  if (parsed.error) {
    message.reply({
      embeds: [
        embed(
          parsed.error,
          COLORS.LOSE
        )
      ]
    }).catch(() => {});

    return null;
  }

  return parsed.bet;
}

/* ============================================================
   HELP
   ============================================================ */

function helpEmbed() {
  return embed(
    [
      "**💰 Economy**",
      `\`${PREFIX}bal\` · \`${PREFIX}cash\` · \`${PREFIX}balance\``,
      `\`${PREFIX}work\` · \`${PREFIX}crime\` · \`${PREFIX}rob @user\``,
      `\`${PREFIX}deposit <amount|half|all>\``,
      `\`${PREFIX}withdraw <amount|half|all>\``,
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
      "Every game accepts an amount, `half`, or `all`.",
      "",
      "**🎁 Daily**",
      `\`${PREFIX}daily\` · \`${PREFIX}summer\``,
      "",
      "**🛠️ Admin**",
      `\`${PREFIX}addmoney @user <amount>\``,
      `\`${PREFIX}remove-money @user <amount>\``,
      `\`${PREFIX}reset-economy\``,
      `\`${PREFIX}casinorole @role\``,
      `\`${PREFIX}roomgame\``,
      `\`${PREFIX}log-channel\``,
      `\`${PREFIX}predict @user\``,
      `\`${PREFIX}currency <emoji>\``,
      `\`${PREFIX}disable <command>\``,
      `\`${PREFIX}undisable <command>\``
    ].join("\n"),
    COLORS.INFO,
    "🎰 Casino Bot"
  );
}

/* ============================================================
   INFO
   ============================================================ */

function infoEmbed() {
  return embed(
    [
      "**🃏 Blackjack**",
      "Hit / Stand / Double.",
      "",
      "**🪙 CoinFlip**",
      "Choose Heads or Tails.",
      "",
      "**📈 Higher / Lower**",
      "Guess whether the next number is higher or lower.",
      "",
      "**🐔 Cockfight**",
      "Fight with your chicken.",
      "",
      "**💣 Mines**",
      "Find safe tiles without hitting a mine.",
      "",
      "**⛏️ Goldmine**",
      "Search the board for gold.",
      "",
      "**🎰 Slots**",
      "Spin the reels.",
      "",
      "**🎡 Roulette**",
      "Choose Red, Black or Green.",
      "",
      "**🎡 Wheel**",
      "Spin for a multiplier.",
      "",
      "**📈 Crash**",
      "Cash out before the crash.",
      "",
      `Minimum bet: **${money(MIN_BET)}** ${CURRENCY}`
    ].join("\n"),
    COLORS.INFO,
    "📖 Casino Info"
  );
}

/* ============================================================
   READY
   ============================================================ */

client.once("ready", () => {
  console.log(`✅ Logged in as ${client.user.tag}`);

  setupSecretDM(client);
});

/* ============================================================
   MESSAGE COMMANDS
   ============================================================ */

client.on("messageCreate", async message => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (!message.content.startsWith(PREFIX)) return;

  const parts = message.content
    .slice(PREFIX.length)
    .trim()
    .split(/\s+/);

  const rawCommand =
    (parts.shift() || "").toLowerCase();

  const args = parts;

  const command =
    commandName(rawCommand);

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

    /* ========================= ADMIN DISABLE ========================= */

    if (command === "disable") {
      return disable(message, args);
    }

    if (command === "undisable") {
      return undisable(message, args);
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

    /* ========================= DISABLED ========================= */

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
      return work(message);
    }

    if (command === "crime") {
      return crime(message);
    }

    if (command === "rob") {
      return rob(message);
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
      if (!gameRoomCheck(message)) {
        return;
      }
    }

    /* ========================= BET ========================= */

    const betRequiredGames = [
      "blackjack",
      "coinflip",
      "higherlower",
      "mines",
      "goldmine",
      "slots",
      "roulette",
      "wheel",
      "crash"
    ];

    let bet = null;

    if (betRequiredGames.includes(command)) {
      bet = getBet(message, args);

      if (bet === null) {
        return;
      }
    }

    /* ========================= BLACKJACK ========================= */

    if (command === "blackjack") {
      return blackjack(
        message,
        [String(bet)],
        getUser(message.author.id)
      );
    }

    /* ========================= COINFLIP ========================= */

    if (command === "coinflip") {
      return coinflip(
        message,
        bet
      );
    }

    /* ========================= HIGHER / LOWER ========================= */

    if (command === "higherlower") {
      return higherLower(
        message,
        bet
      );
    }

    /* ========================= COCKFIGHT ========================= */

    if (command === "cockfight") {
      return cockfight(
        message,
        args,
        getUser(message.author.id)
      );
    }

    /* ========================= MINES ========================= */

    if (command === "mines") {
      return mines(
        message,
        bet
      );
    }

    /* ========================= GOLDMINE ========================= */

    if (command === "goldmine") {
      return goldmine(
        message,
        bet
      );
    }

    /* ========================= SLOTS ========================= */

    if (command === "slots") {
      return slots(
        message,
        bet
      );
    }

    /* ========================= ROULETTE ========================= */

    if (command === "roulette") {
      return roulette(
        message,
        bet
      );
    }

    /* ========================= WHEEL ========================= */

    if (command === "wheel") {
      return wheel(
        message,
        bet
      );
    }

    /* ========================= CRASH ========================= */

    if (command === "crash") {
      return crash(
        message,
        bet
      );
    }

  } catch (error) {
    console.error(
      "❌ Command error:",
      error
    );

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

/* ============================================================
   BUTTONS
   ============================================================ */

client.on("interactionCreate", async interaction => {
  if (!interaction.isButton()) return;

  try {
    const id = interaction.customId;

    /* ========================= BLACKJACK ========================= */

    if (id.startsWith("bj:")) {
      return handleBlackjackButton(
        interaction
      );
    }

    /* ========================= COINFLIP ========================= */

    if (id.startsWith("cf:")) {
      return handleCoinflipButton(
        interaction
      );
    }

    /* ========================= HIGHER / LOWER ========================= */

    if (id.startsWith("hl:")) {
      return handleHigherLowerButton(
        interaction
      );
    }

    /* ========================= MINES ========================= */

    if (id.startsWith("mines:")) {
      return handleMinesButton(
        interaction
      );
    }

    /* ========================= GOLDMINE ========================= */

    if (id.startsWith("goldmine:")) {
      return handleGoldmineButton(
        interaction
      );
    }

    /* ========================= SLOTS ========================= */

    if (id.startsWith("slots:")) {
      return handleSlotsButton(
        interaction
      );
    }

    /* ========================= ROULETTE ========================= */

    if (id.startsWith("roulette:")) {
      return handleRouletteButton(
        interaction
      );
    }

    /* ========================= WHEEL ========================= */

    if (id.startsWith("wheel:")) {
      return handleWheelButton(
        interaction
      );
    }

    /* ========================= CRASH ========================= */

    if (id.startsWith("crash:")) {
      return handleCrashButton(
        interaction
      );
    }

  } catch (error) {
    console.error(
      "❌ Button error:",
      error
    );

    if (
      !interaction.replied &&
      !interaction.deferred
    ) {
      await interaction.reply({
        content: "❌ Something went wrong.",
        ephemeral: true
      }).catch(() => {});
    }
  }
});

/* ============================================================
   SAFETY
   ============================================================ */

process.on(
  "unhandledRejection",
  error => {
    console.error(
      "❌ Unhandled rejection:",
      error
    );
  }
);

process.on(
  "uncaughtException",
  error => {
    console.error(
      "❌ Uncaught exception:",
      error
    );
  }
);

/* ============================================================
   SHUTDOWN
   ============================================================ */

async function shutdown(signal) {
  console.log(
    `Received ${signal}. Saving database...`
  );

  try {
    forceSaveData();
  } catch (error) {
    console.error(
      "❌ Final save failed:",
      error
    );
  }

  process.exit(0);
}

process.on(
  "SIGINT",
  () => shutdown("SIGINT")
);

process.on(
  "SIGTERM",
  () => shutdown("SIGTERM")
);

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
  )
    .then(() => {
      console.log(
        "✅ Discord login started."
      );
    })
    .catch(error => {
      console.error(
        "❌ Discord login failed:",
        error
      );
    });
}