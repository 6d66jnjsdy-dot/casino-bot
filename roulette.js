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

const activeGames = new Map();

const RED_NUMBERS = new Set([
  1, 3, 5, 7, 9,
  12, 14, 16, 18,
  19, 21, 23, 25, 27,
  30, 32, 34, 36
]);

function getColor(number) {
  if (number === 0) return "🟢 Green";
  return RED_NUMBERS.has(number)
    ? "🔴 Red"
    : "⚫ Black";
}

function createRow(userId) {
  return [
    new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`roulette:red:${userId}`)
        .setLabel("Red")
        .setStyle(ButtonStyle.Danger),

      new ButtonBuilder()
        .setCustomId(`roulette:black:${userId}`)
        .setLabel("Black")
        .setStyle(ButtonStyle.Secondary),

      new ButtonBuilder()
        .setCustomId(`roulette:green:${userId}`)
        .setLabel("Green 0")
        .setStyle(ButtonStyle.Success)
    )
  ];
}

/* ============================================================
   START ROULETTE
   ============================================================ */

async function roulette(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Roulette game.",
          COLORS.LOSE,
          "🎯 Roulette"
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

  const game = {
    userId,
    bet,
    finished: false,
    message: null
  };

  activeGames.set(userId, game);

  const sent = await message.reply({
    embeds: [
      embed(
        `🎯 **ROULETTE**\n\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `🔴 Red — 2x\n` +
        `⚫ Black — 2x\n` +
        `🟢 Green 0 — 14x\n\n` +
        `Choose your color.`,
        COLORS.ACTIVE,
        "🎯 Roulette"
      )
    ],
    components: createRow(userId)
  });

  game.message = sent;
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleRouletteButton(interaction) {
  const customId = interaction.customId;

  if (!customId.startsWith("roulette:")) {
    return false;
  }

  const parts = customId.split(":");

  const choice = parts[1];
  const userId = parts[2];

  if (interaction.user.id !== userId) {
    await interaction.reply({
      content:
        "❌ This Roulette game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content:
        "❌ This Roulette game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (game.finished) {
    return true;
  }

  game.finished = true;

  const user = getUser(userId);

  /*
   * Bet is removed only after a valid choice.
   */
  if (user.cash < game.bet) {
    activeGames.delete(userId);

    await interaction.update({
      embeds: [
        embed(
          "❌ You no longer have enough cash for this bet.",
          COLORS.LOSE,
          "🎯 Roulette"
        )
      ],
      components: []
    });

    return true;
  }

  user.cash -= game.bet;

  /*
   * Standard roulette numbers: 0–36.
   */
  const number = random(0, 36);
  const resultColor = getColor(number);

  let multiplier = 0;

  if (number === 0) {
    if (choice === "green") {
      multiplier = 14;
    }
  } else if (
    choice === "red" &&
    RED_NUMBERS.has(number)
  ) {
    multiplier = 2;
  } else if (
    choice === "black" &&
    !RED_NUMBERS.has(number)
  ) {
    multiplier = 2;
  }

  const won = multiplier > 0;

  const payout = won
    ? game.bet * multiplier
    : 0;

  if (won) {
    user.cash += payout;
  }

  activeGames.delete(userId);

  saveData();

  await interaction.update({
    embeds: [
      embed(
        `🎯 **The wheel landed on ${number}**\n\n` +
        `🎨 Result: **${resultColor}**\n` +
        `👉 Your choice: **${choice}**\n\n` +
        (
          won
            ? `🎉 **WIN!**\n` +
              `📈 Multiplier: **${multiplier}x**\n` +
              `💰 Payout: **${money(
                payout
              )}** ${db.currency}\n`
            : `💥 **LOSS!**\n` +
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
          ? "🎉 ROULETTE WIN!"
          : "🎯 ROULETTE"
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
  roulette,
  handleRouletteButton
};
