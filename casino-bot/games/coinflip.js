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

/* ============================================================
   COINFLIP
   ============================================================ */

const activeGames = new Map();

/* ============================================================
   START GAME
   ============================================================ */

async function coinflip(
  message,
  bet
) {
  const userId =
    message.author.id;

  if (
    activeGames.has(userId)
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Coinflip game.",
          COLORS.LOSE,
          "🪙 Coinflip"
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

  const game = {
    userId,
    bet,
    finished: false,
    message: null
  };

  activeGames.set(
    userId,
    game
  );

  const row =
    new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(
            `cf:heads:${userId}`
          )
          .setLabel("Heads")
          .setEmoji("🪙")
          .setStyle(
            ButtonStyle.Primary
          ),

        new ButtonBuilder()
          .setCustomId(
            `cf:tails:${userId}`
          )
          .setLabel("Tails")
          .setEmoji("🪙")
          .setStyle(
            ButtonStyle.Secondary
          )
      );

  const sent =
    await message.reply({
      embeds: [
        embed(
          `💵 Bet: **${money(
            bet
          )}** ${db.currency}\n\n` +
          `🪙 Choose **Heads** or **Tails**.`,
          COLORS.ACTIVE,
          "🪙 Coinflip"
        )
      ],
      components: [
        row
      ]
    });

  game.message = sent;
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleCoinflipButton(
  interaction
) {
  const customId =
    interaction.customId;

  if (
    !customId.startsWith(
      "cf:"
    )
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
        "❌ This Coinflip game belongs to another player.",
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
        "❌ This Coinflip game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (
    game.finished
  ) {
    return true;
  }

  game.finished = true;

  const user =
    getUser(userId);

  /*
   * The bet is removed only after
   * the player actually chooses.
   */
  user.cash -= game.bet;

  const result =
    Math.random() < 0.5
      ? "heads"
      : "tails";

  const won =
    choice === result;

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

  const resultName =
    result === "heads"
      ? "HEADS 🪙"
      : "TAILS 🪙";

  const choiceName =
    choice === "heads"
      ? "HEADS 🪙"
      : "TAILS 🪙";

  const color =
    won
      ? COLORS.WIN
      : COLORS.LOSE;

  const title =
    won
      ? "🪙 YOU WIN!"
      : "🪙 YOU LOSE!";

  const description =
    `🎯 Your choice: **${choiceName}**\n` +
    `🪙 Coin landed on: **${resultName}**\n\n` +
    `💵 Bet: **${money(
      game.bet
    )}** ${db.currency}\n` +
    `💰 Payout: **${money(
      payout
    )}** ${db.currency}\n` +
    `💳 Cash: **${money(
      user.cash
    )}** ${db.currency}`;

  await interaction.update({
    embeds: [
      embed(
        description,
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
  coinflip,
  handleCoinflipButton
};
