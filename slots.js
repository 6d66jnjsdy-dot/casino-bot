const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const {
  db,
  getUser,
  saveData
} = require("../database");

const {
  COLORS,
  money,
  random,
  embed
} = require("../helpers");

/* ============================================================
   SLOTS
   ============================================================ */

const activeGames = new Map();

const SYMBOLS = [
  "🍒",
  "🍋",
  "🍊",
  "🍇",
  "🔔",
  "💎",
  "7️⃣"
];

/*
 * The normal game is weighted toward losses.
 * There is also a 4% forced-loss result when the player
 * would otherwise get a winning combination.
 */
const PAYOUTS = {
  "🍒🍒🍒": 2,
  "🍋🍋🍋": 2.5,
  "🍊🍊🍊": 3,
  "🍇🍇🍇": 4,
  "🔔🔔🔔": 5,
  "💎💎💎": 8,
  "7️⃣7️⃣7️⃣": 12
};

/* ============================================================
   BUTTON
   ============================================================ */

function createRow(userId) {
  return [
    new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`slots:spin:${userId}`)
        .setLabel("SPIN")
        .setEmoji("🎰")
        .setStyle(ButtonStyle.Primary)
    )
  ];
}

/* ============================================================
   SPIN SYMBOL
   ============================================================ */

function spin() {
  return [
    SYMBOLS[random(0, SYMBOLS.length - 1)],
    SYMBOLS[random(0, SYMBOLS.length - 1)],
    SYMBOLS[random(0, SYMBOLS.length - 1)]
  ];
}

/* ============================================================
   START GAME
   ============================================================ */

async function slots(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Slots game.",
          COLORS.LOSE,
          "🎰 Slots"
        )
      ]
    });
  }

  const user = getUser(userId);

  if (
    !Number.isFinite(bet) ||
    bet <= 0
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Invalid bet.",
          COLORS.LOSE
        )
      ]
    });
  }

  if (user.cash < bet) {
    return message.reply({
      embeds: [
        embed(
          `❌ You only have **${money(
            user.cash
          )}** ${db.currency} in cash.`,
          COLORS.LOSE
        )
      ]
    });
  }

  /*
   * Remove the bet when the game starts.
   */
  user.cash -= bet;

  const game = {
    userId,
    bet,
    finished: false,
    message: null
  };

  activeGames.set(userId, game);

  saveData();

  const sent = await message.reply({
    embeds: [
      embed(
        `🎰 **SLOTS**\n\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `Press **SPIN** to play!`,
        COLORS.ACTIVE,
        "🎰 Slots"
      )
    ],
    components: createRow(userId)
  });

  game.message = sent;
}

/* ============================================================
   HANDLE SPIN
   ============================================================ */

async function handleSlotsButton(interaction) {
  const customId = interaction.customId;

  if (!customId.startsWith("slots:")) {
    return false;
  }

  const parts = customId.split(":");

  const action = parts[1];
  const userId = parts[2];

  if (action !== "spin") {
    return true;
  }

  if (interaction.user.id !== userId) {
    await interaction.reply({
      content:
        "❌ This Slots game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content:
        "❌ This Slots game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (game.finished) {
    return true;
  }

  game.finished = true;

  const user = getUser(userId);

  let result = spin();

  const key = result.join("");

  /*
   * 4% forced-loss protection.
   *
   * If the generated result is a winning triple,
   * replace it with three different symbols.
   */
  if (
    PAYOUTS[key] &&
    Math.random() < 0.04
  ) {
    let forcedLoss;

    do {
      forcedLoss = spin();
    } while (
      forcedLoss[0] === forcedLoss[1] &&
      forcedLoss[1] === forcedLoss[2]
    );

    result = forcedLoss;
  }

  const finalKey = result.join("");

  const multiplier =
    PAYOUTS[finalKey] || 0;

  let payout = 0;

  if (multiplier > 0) {
    payout =
      Math.floor(
        game.bet * multiplier
      );

    user.cash += payout;
  }

  activeGames.delete(userId);

  saveData();

  const won = payout > 0;

  const resultLine =
    result.join("  ");

  await interaction.update({
    embeds: [
      embed(
        `🎰 **${resultLine}**\n\n` +
        (
          won
            ? `🎉 **WIN!**\n\n` +
              `📈 Multiplier: **${multiplier.toFixed(2)}x**\n` +
              `💵 Bet: **${money(
                game.bet
              )}** ${db.currency}\n` +
              `💰 Payout: **${money(
                payout
              )}** ${db.currency}\n`
            : `💥 **LOSS!**\n\n` +
              `💵 Lost: **${money(
                game.bet
              )}** ${db.currency}\n`
        ) +
        `💳 Cash: **${money(
          user.cash
        )}** ${db.currency}`,
        won
          ? COLORS.WIN
          : COLORS.LOSE,
        won
          ? "🎰 JACKPOT!"
          : "🎰 Slots"
      )
    ],
    components: []
  });

  return true;
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  slots,
  handleSlotsButton
};
