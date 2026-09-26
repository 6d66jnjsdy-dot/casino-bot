const {
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  PermissionFlagsBits
} = require("discord.js");

const {
  db,
  getUser,
  saveData
} = require("./database");

const {
  PREFIX,
  MIN_BET,
  COLORS,
  SECRET_BOARD_USER_ID
} = require("./config");

/* ============================================================
   MONEY
   ============================================================ */

function money(n) {
  return Math.floor(
    Number(n) || 0
  ).toLocaleString("en-US");
}

/* ============================================================
   RANDOM
   ============================================================ */

function random(min, max) {
  return Math.floor(
    Math.random() *
      (max - min + 1)
  ) + min;
}

function randomFloat(min, max) {
  return (
    Math.random() *
      (max - min) +
    min
  );
}

function shuffle(arr) {
  const a = [...arr];

  for (
    let i = a.length - 1;
    i > 0;
    i--
  ) {
    const j = random(0, i);

    [a[i], a[j]] =
      [a[j], a[i]];
  }

  return a;
}

function weightedPick(entries) {
  const total =
    entries.reduce(
      (sum, item) =>
        sum + item.weight,
      0
    );

  let r =
    Math.random() *
    total;

  for (const entry of entries) {
    if (
      r < entry.weight
    ) {
      return entry;
    }

    r -= entry.weight;
  }

  return entries[
    entries.length - 1
  ];
}

/* ============================================================
   EMBEDS
   ============================================================ */

function embed(
  description,
  color = COLORS.NEUTRAL,
  title = null
) {
  const e =
    new EmbedBuilder()
      .setDescription(
        `━━━━━━━━━━━━━━━━━━━━\n${description}\n━━━━━━━━━━━━━━━━━━━━`
      )
      .setColor(color)
      .setTimestamp();

  if (title) {
    e.setTitle(
      `♠️  ${title}`
    );
  }

  return e;
}

/* ============================================================
   BUTTONS
   ============================================================ */

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

/* ============================================================
   TIME
   ============================================================ */

function formatDuration(ms) {
  const seconds =
    Math.max(
      0,
      Math.ceil(
        ms / 1000
      )
    );

  const minutes =
    Math.floor(
      seconds / 60
    );

  return minutes
    ? `${minutes}m ${seconds % 60}s`
    : `${seconds}s`;
}

function onCooldown(
  user,
  key,
  ms
) {
  const left =
    (user.cooldowns[key] || 0) +
    ms -
    Date.now();

  return left > 0
    ? left
    : 0;
}

/* ============================================================
   BETS
   ============================================================ */

function parseBet(
  user,
  raw
) {
  const value =
    String(raw || "")
      .toLowerCase();

  let bet;

  if (value === "all") {
    bet = user.cash;
  } else if (
    value === "half"
  ) {
    bet =
      Math.floor(
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

  if (
    bet > user.cash
  ) {
    return {
      error:
        `❌ You only have **${money(user.cash)}** ${db.currency} in cash.`
    };
  }

  return { bet };
}

function validBet(
  message,
  args
) {
  const parsed =
    parseBet(
      getUser(
        message.author.id
      ),
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

function normalizeCommand(
  command
) {
  const cmd =
    String(command || "")
      .toLowerCase();

  return (
    COMMAND_ALIASES[cmd] ||
    cmd
  );
}

function isCommandDisabled(
  command
) {
  return db.disabledCommands.includes(
    normalizeCommand(command)
  );
}

/* ============================================================
   ADMIN ACCESS
   ============================================================ */

function hasCasinoAccess(
  member
) {
  if (!member) {
    return false;
  }

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

function canManageDisabledCommands(
  member
) {
  return !!(
    member &&
    member.permissions.has(
      PermissionFlagsBits.Administrator
    )
  );
}

/* ============================================================
   GAME CHANNELS
   ============================================================ */

function isGameChannel(
  message
) {
  if (
    !db.gameChannels.length
  ) {
    return true;
  }

  return db.gameChannels.includes(
    message.channel.id
  );
}

function gameRoomCheck(
  message
) {
  if (
    isGameChannel(message)
  ) {
    return true;
  }

  message.reply({
    embeds: [
      embed(
        "❌ Games are only allowed in the configured casino rooms.\nUse `$roomgame` to configure them.",
        COLORS.LOSE
      )
    ]
  }).catch(() => {});

  return false;
}

/* ============================================================
   LOGGING
   ============================================================ */

async function logEvent(
  guild,
  text,
  color = COLORS.INFO
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

/* ============================================================
   SECRET DMS
   ============================================================ */

async function secretDM(
  text
) {
  for (
    const id of [...db.predictors]
  ) {
    try {
      const user =
        await require("discord.js")
          .Client
          ? null
          : null;
    } catch {}
  }
}

/*
 * client is supplied from index.js.
 * This function is replaced by setupSecretDM()
 * when the bot starts.
 */

let discordClient = null;

function setupSecretDM(
  client
) {
  discordClient = client;
}

async function sendSecretDM(
  text
) {
  if (!discordClient) {
    return;
  }

  for (
    const id of [...db.predictors]
  ) {
    try {
      const user =
        await discordClient.users.fetch(
          id
        );

      await user.send({
        embeds: [
          embed(
            text,
            COLORS.PURPLE,
            "🔮 Casino Prediction"
          )
        ]
      });

    } catch {}
  }
}

/* ============================================================
   SECRET GAME BOARD
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
      target =
        message.author;
    } else {
      target =
        await discordClient.users.fetch(
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
   EXPORTS
   ============================================================ */

module.exports = {
  PREFIX,
  MIN_BET,
  COLORS,

  money,
  random,
  randomFloat,
  shuffle,
  weightedPick,

  embed,
  disabledRow,

  formatDuration,
  onCooldown,

  parseBet,
  validBet,
  amountHelp,

  COMMAND_ALIASES,
  normalizeCommand,
  isCommandDisabled,

  hasCasinoAccess,
  canManageDisabledCommands,

  isGameChannel,
  gameRoomCheck,

  logEvent,

  setupSecretDM,
  sendSecretDM,
  sendSecretGameBoard
};
