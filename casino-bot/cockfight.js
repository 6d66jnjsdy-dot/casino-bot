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
  embed
} = require("../helpers");

const activeGames = new Map();

/* ============================================================
   BUTTONS
   ============================================================ */

function gameRow(userId) {
  return new ActionRowBuilder()
    .addComponents(
      new ButtonBuilder()
        .setCustomId(`cfight:left:${userId}`)
        .setLabel("Left")
        .setEmoji("🐔")
        .setStyle(ButtonStyle.Primary),

      new ButtonBuilder()
        .setCustomId(`cfight:right:${userId}`)
        .setLabel("Right")
        .setEmoji("🐔")
        .setStyle(ButtonStyle.Danger)
    );
}

/* ============================================================
   START GAME
   ============================================================ */

async function cockfight(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Cockfight game.",
          COLORS.LOSE,
          "🐔 Cockfight"
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
        `🐔 **COCKFIGHT** 🐔\n\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `Choose your side!`,
        COLORS.ACTIVE,
        "🐔 Cockfight"
      )
    ],
    components: [
      gameRow(userId)
    ]
  });

  game.message = sent;
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleCockfightButton(interaction) {
  const customId = interaction.customId;

  if (!customId.startsWith("cfight:")) {
    return false;
  }

  const parts = customId.split(":");

  const choice = parts[1];
  const userId = parts[2];

  if (interaction.user.id !== userId) {
    await interaction.reply({
      content:
        "❌ This Cockfight game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content:
        "❌ This game has already ended.",
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
   * Exact 50 / 50 result.
   */
  const playerWon =
    Math.random() < 0.5;

  /*
   * Remove bet when the player chooses.
   */
  user.cash -= game.bet;

  let payout = 0;

  if (playerWon) {
    payout = game.bet * 2;
    user.cash += payout;
  }

  saveData();

  activeGames.delete(userId);

  const choiceText =
    choice === "left"
      ? "🐔 Left"
      : "🐔 Right";

  const resultText =
    playerWon
      ? "🏆 Your chicken won!"
      : "💥 Your chicken lost!";

  const title =
    playerWon
      ? "🐔 YOU WIN!"
      : "🐔 YOU LOSE!";

  const color =
    playerWon
      ? COLORS.WIN
      : COLORS.LOSE;

  await interaction.update({
    embeds: [
      embed(
        `👉 Your choice: **${choiceText}**\n\n` +
        `${resultText}\n\n` +
        `💵 Bet: **${money(
          game.bet
        )}** ${db.currency}\n` +
        `💰 Payout: **${money(
          payout
        )}** ${db.currency}\n` +
        `💳 Cash: **${money(
          user.cash
        )}** ${db.currency}`,
        color,
        title
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
  cockfight,
  handleCockfightButton
};
