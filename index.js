/* ============================================================
   CASINO BOT — MAIN INDEX
   discord.js v14
   ============================================================ */

const express = require("express");

const {
  Client,
  GatewayIntentBits
} = require("discord.js");

/* ============================================================
   CONFIG / DATABASE / HELPERS
   ============================================================ */

const {
  PREFIX,
  PORT,
  CURRENCY
} = require("./config");

const {
  forceSaveData
} = require("./database");

const {
  normalizeCommand,
  parseBet,
  validBet,
  gameRoomCheck,
  isCommandDisabled,
  setupSecretDM
} = require("./helpers");

/* ============================================================
   ECONOMY
   ============================================================ */

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

/* ============================================================
   DAILY
   ============================================================ */

const {
  daily
} = require("./daily");

/* ============================================================
   ADMIN
   ============================================================ */

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

/* ============================================================
   GAMES
   ============================================================ */

const {
  blackjack,
  handleBlackjackButton
} = require("./Games/blackjack");

const {
  coinflip,
  handleCoinflipButton
} = require("./Games/coinflip");

const {
  higherLower,
  handleHigherLowerButton
} = require("./Games/higherlower");

const {
  cockfight,
  handleCockfightButton
} = require("./Games/cockfight");

const {
  mines,
  handleMinesButton
} = require("./Games/mines");

const {
  goldmine,
  handleGoldmineButton
} = require("./Games/goldmine");

const {
  slots,
  handleSlotsButton
} = require("./Games/slots");

const {
  roulette,
  handleRouletteButton
} = require("./Games/roulette");

const {
  wheel,
  handleWheelButton
} = require("./Games/wheel");

const {
  crash,
  handleCrashButton
} = require("./Games/crash");

/* ============================================================
   EXPRESS KEEP ALIVE
   ============================================================ */

const app = express();

app.get("/", (req, res) => {
  res.send("🎰 Casino Bot is online!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`🌐 Keep Alive running on port ${PORT}`);
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
   READY
   ============================================================ */

client.once("ready", async () => {
  console.log(`✅ Logged in as ${client.user.tag}`);
  console.log(`🌐 Servers: ${client.guilds.cache.size}`);
  console.log(`🎰 Prefix: ${PREFIX}`);

  setupSecretDM(client);
});

/* ============================================================
   MESSAGE COMMANDS
   ============================================================ */

client.on("messageCreate", async message => {
  try {
    if (message.author.bot) {
      return;
    }

    if (!message.content.startsWith(PREFIX)) {
      return;
    }

    const raw = message.content
      .slice(PREFIX.length)
      .trim();

    if (!raw) {
      return;
    }

    const parts = raw.split(/\s+/);

    const command = normalizeCommand(
      parts.shift().toLowerCase()
    );

    const args = parts;

    /* ========================================================
       DISABLED COMMAND CHECK
       ======================================================== */

    if (isCommandDisabled(command)) {
      return message.reply(
        "❌ This command is currently disabled."
      );
    }

    /* ========================================================
       BASIC COMMANDS
       ======================================================== */

    if (command === "balance") {
      return balance(message);
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
      return rob(message, args);
    }

    if (command === "top") {
      return leaderboard(message, args);
    }

    if (command === "daily") {
      return daily(message);
    }

    /* ========================================================
       ADMIN COMMANDS
       ======================================================== */

    if (command === "casinorole") {
      return casinoRole(message, args);
    }

    if (command === "roomgame") {
      return roomGame(message);
    }

    if (command === "log-channel") {
      return logChannel(message);
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

    if (command === "reset-economy") {
      return resetEconomy(message);
    }

    if (command === "disable") {
      return disable(message, args);
    }

    if (command === "undisable") {
      return undisable(message, args);
    }

    /* ========================================================
       CASINO COMMANDS
       ======================================================== */

    const casinoCommands = new Set([
      "bj",
      "ht",
      "hl",
      "cf",
      "mines",
      "gm",
      "slots",
      "roulette",
      "wheel",
      "crash"
    ]);

    if (!casinoCommands.has(command)) {
      return;
    }

    /* ========================================================
       GAME ROOM CHECK
       ======================================================== */

    if (!gameRoomCheck(message)) {
      return;
    }

    /* ========================================================
       BET CHECK
       ======================================================== */

    const bet = parseBet(args[0]);

    if (!validBet(bet)) {
      return message.reply(
        `❌ Minimum bet is **175** ${CURRENCY || "💸"}.\n` +
        `Usage: \`${PREFIX}${command} <bet>\``
      );
    }

    /* ========================================================
       GAME DISPATCH
       ======================================================== */

    switch (command) {
      case "bj":
        return blackjack(message, bet);

      case "ht":
        return coinflip(message, bet);

      case "hl":
        return higherLower(message, bet);

      case "cf":
        return cockfight(message, bet);

      case "mines":
        return mines(message, bet);

      case "gm":
        return goldmine(message, bet);

      case "slots":
        return slots(message, bet);

      case "roulette":
        return roulette(message, bet);

      case "wheel":
        return wheel(message, bet);

      case "crash":
        return crash(message, bet);
    }

  } catch (error) {
    console.error(
      "❌ messageCreate error:",
      error
    );

    try {
      await message.reply(
        "❌ An unexpected error occurred."
      );
    } catch {}
  }
});

/* ============================================================
   BUTTON INTERACTIONS
   ============================================================ */

client.on(
  "interactionCreate",
  async interaction => {
    try {
      if (!interaction.isButton()) {
        return;
      }

      /* BLACKJACK */
      if (
        await handleBlackjackButton(interaction)
      ) {
        return;
      }

      /* COINFLIP */
      if (
        await handleCoinflipButton(interaction)
      ) {
        return;
      }

      /* HIGHER / LOWER */
      if (
        await handleHigherLowerButton(interaction)
      ) {
        return;
      }

      /* COCKFIGHT */
      if (
        await handleCockfightButton(interaction)
      ) {
        return;
      }

      /* MINES */
      if (
        await handleMinesButton(interaction)
      ) {
        return;
      }

      /* GOLDMINE */
      if (
        await handleGoldmineButton(interaction)
      ) {
        return;
      }

      /* SLOTS */
      if (
        await handleSlotsButton(interaction)
      ) {
        return;
      }

      /* ROULETTE */
      if (
        await handleRouletteButton(interaction)
      ) {
        return;
      }

      /* WHEEL */
      if (
        await handleWheelButton(interaction)
      ) {
        return;
      }

      /* CRASH */
      if (
        await handleCrashButton(interaction)
      ) {
        return;
      }

    } catch (error) {
      console.error(
        "❌ interactionCreate error:",
        error
      );

      try {
        if (
          !interaction.replied &&
          !interaction.deferred
        ) {
          await interaction.reply({
            content:
              "❌ An unexpected error occurred.",
            ephemeral: true
          });
        }
      } catch {}
    }
  }
);

/* ============================================================
   PROCESS SAFETY
   ============================================================ */

process.on(
  "uncaughtException",
  error => {
    console.error(
      "❌ Uncaught Exception:",
      error
    );
  }
);

process.on(
  "unhandledRejection",
  error => {
    console.error(
      "❌ Unhandled Rejection:",
      error
    );
  }
);

/* ============================================================
   LOGIN TO DISCORD
   ============================================================ */

client.login(process.env.DISCORD_TOKEN);
