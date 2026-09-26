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
   HIGHER / LOWER
   ============================================================ */

const activeGames = new Map();

/* ============================================================
   BUTTONS
   ============================================================ */

function gameRow(userId) {
  return new ActionRowBuilder()
    .addComponents(
      new ButtonBuilder()
        .setCustomId(`hl:higher:${userId}`)
        .setLabel("Higher")
        .setEmoji("⬆️")
        .setStyle(ButtonStyle.Primary),

      new ButtonBuilder()
        .setCustomId(`hl:lower:${userId}`)
        .setLabel("Lower")
        .setEmoji("⬇️")
        .setStyle(ButtonStyle.Secondary)
    );
}

/* ============================================================
   START GAME
   ============================================================ */

async function higherLower(message, bet) {
  const userId =
    message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Higher / Lower game.",
          COLORS.LOSE
        )
      ]
    });
  }

  const user =
    getUser(userId);

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

  if (
    user.cash < bet
  ) {
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
   * Take the bet when the game starts.
   */
  user.cash -= bet;

  const game = {
    userId,
    bet,
    current: random(2, 98),
    finished: false,
    message: null
  };

  activeGames.set(
    userId,
    game
  );

  saveData();

  const sent =
    await message.reply({
      embeds: [
        embed(
          `🎯 Current number: **${game.current}**\n\n` +
          `Do you think the next number will be **higher** or **lower**?\n\n` +
          `💵 Bet: **${money(
            bet
          )}** ${db.currency}`,
          COLORS.ACTIVE,
          "🔼 Higher / Lower 🔽"
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

async function handleHigherLowerButton(
  interaction
) {
  const customId =
    interaction.customId;

  if (
    !customId.startsWith("hl:")
  ) {
    return false;
  }

  const parts =
    customId.split(":");

  const choice =
    parts[1];

  const userId =
    parts[2];

  if (
    interaction.user.id !==
    userId
  ) {
    await interaction.reply({
      content:
        "❌ This Higher / Lower game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game =
    activeGames.get(
      userId
    );

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

  const next =
    random(1, 100);

  const user =
    getUser(userId);

  /*
   * Original extra 2% losing gate.
   */
  const forcedLoss =
    Math.random() < 0.02;

  let won = false;

  if (
    next !== game.current &&
    !forcedLoss
  ) {
    if (
      choice === "higher"
    ) {
      won =
        next >
        game.current;
    }

    if (
      choice === "lower"
    ) {
      won =
        next <
        game.current;
    }
  }

  let payout = 0;

  if (won) {
    payout =
      game.bet * 2;

    user.cash += payout;
  }

  saveData();

  activeGames.delete(
    userId
  );

  const choiceText =
    choice === "higher"
      ? "⬆️ Higher"
      : "⬇️ Lower";

  const resultText =
    next > game.current
      ? "⬆️ Higher"
      : next < game.current
        ? "⬇️ Lower"
        : "🟰 Same";

  const title =
    won
      ? "🎉 YOU WIN!"
      : "💥 YOU LOSE!";

  const color =
    won
      ? COLORS.WIN
      : COLORS.LOSE;

  await interaction.update({
    embeds: [
      embed(
        `🎯 Previous number: **${game.current}**\n` +
        `🎲 New number: **${next}**\n\n` +
        `👉 Your choice: **${choiceText}**\n` +
        `📊 Result: **${resultText}**\n\n` +
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
  higherLower,
  handleHigherLowerButton
};
