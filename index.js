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
  PORT
} = require("./config");

const {
  saveData,
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

/* ============================================================
   EXPRESS KEEP ALIVE
   ============================================================ */

const app = express();

app.get("/", (req, res) => {
  res.send("🎰 Casino Bot is online!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(
    `🌐 Keep Alive running on port ${PORT}`
  );
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
  console.log(
    `✅ Logged in as ${client.user.tag}`
  );

  console.log(
    `🌐 Servers: ${client.guilds.cache.size}`
  );

  console.log(
    `🎰 Prefix: ${PREFIX}`
  );

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

    const command =
      normalizeCommand(
        parts.shift().toLowerCase()
      );

    const args = parts;

    /* ========================================================
       DISABLED COMMAND CHECK
       ======================================================== */

    if (
      isCommandDisabled(command)
    ) {
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
       GAME ROOM CHECK
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

    if (
      casinoCommands.has(command)
    ) {
      if (
        !gameRoomCheck(message)
      ) {
        return;
      }
    }

    /* ========================================================
       BET REQUIRED
       ======================================================== */

    if (
      casinoCommands.has(command)
    ) {
      const bet = parseBet(args[0]);

      if (!validBet(bet)) {
        return message.reply(
          `❌ Minimum bet is **175** ${require("./config").CURRENCY || "💸"}.\n` +
          `Usage: \`${PREFIX}${command} <bet>\``
        );
      }

      /* ==============================================
         BLACKJACK
         ============================================== */

      if (command === "bj") {
        return blackjack(
          message,
          bet
        );
      }

      /* ==============================================
         COINFLIP
         ============================================== */

      if (command === "ht") {
        return coinflip(
          message,
          bet
        );
      }

      /* ==============================================
         HIGHER / LOWER
         ============================================== */

      if (command === "hl") {
        return higherLower(
          message,
          bet
        );
      }

      /* ==============================================
         COCKFIGHT
         ============================================== */

      if (command === "cf") {
        return cockfight(
          message,
          bet
        );
      }

      /* ==============================================
         MINES
         ============================================== */

      if (command === "mines") {
        return mines(
          message,
          bet
        );
      }

      /* ==============================================
         GOLDMINE
         ============================================== */

      if (command === "gm") {
        return goldmine(
          message,
          bet
        );
      }

      /* ==============================================
         SLOTS
         ============================================== */

      if (command === "slots") {
        return slots(
          message,
          bet
        );
      }

      /* ==============================================
         ROULETTE
         ============================================== */

      if (command === "roulette") {
        return roulette(
          message,
          bet
        );
      }

      /* ==============================================
         WHEEL
         ============================================== */

      if (command === "wheel") {
        return wheel(
          message,
          bet
        );
      }

      /* ==============================================
         CRASH
         ============================================== */

      if (command === "crash") {
        return crash(
          message,
          bet
        );
      }
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

      /*
       * Each game handler returns true when it owns
       * the button interaction.
       */

      if (
        await handleBlackjackButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleCoinflipButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleHigherLowerButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleCockfightButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleMinesButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleGoldmineButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleSlotsButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleRouletteButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleWheelButton(
          interaction
        )
      ) {
        return;
      }

      if (
        await handleCrashButton(
          interaction
        )
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
   SAVE BEFORE SHUTDOWN
   ============================================================ */

async function shutdown(signal) {
  console.log(
    `🛑 Received ${signal}. Saving data...`
  );

  try {
    forceSaveData();
  } catch (error) {
    console.error(
      "❌ Failed to save data:",
      error
    );
  }

  try {
    client.destroy();
  } catch {}

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
    "❌ DISCORD_TOKEN environment variable is missing."
  );

  process.exit(1);
}

client.login(
  process.env.DISCORD_TOKEN
);