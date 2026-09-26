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

/* ============================================================
   WHEEL
   ============================================================ */

const SEGMENTS = [
  { label: "💀 0x", multiplier: 0 },
  { label: "💰 1.5x", multiplier: 1.5 },
  { label: "💰 2x", multiplier: 2 },
  { label: "💰 3x", multiplier: 3 },
  { label: "💰 5x", multiplier: 5 },
  { label: "💎 10x", multiplier: 10 }
];

/* ============================================================
   BUTTON
   ============================================================ */

function createRow(userId) {
  return [
    new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`wheel:spin:${userId}`)
        .setLabel("SPIN THE WHEEL")
        .setEmoji("🎡")
        .setStyle(ButtonStyle.Primary)
    )
  ];
}

/* ============================================================
   START GAME
   ============================================================ */

async function wheel(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Wheel game.",
          COLORS.LOSE,
          "🎡 Wheel"
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
        `🎡 **WHEEL**\n\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `💀 0x\n` +
        `💰 1.5x\n` +
        `💰 2x\n` +
        `💰 3x\n` +
        `💰 5x\n` +
        `💎 10x\n\n` +
        `Press the button to spin!`,
        COLORS.ACTIVE,
        "🎡 Wheel"
      )
    ],
    components: createRow(userId)
  });

  game.message = sent;
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleWheelButton(interaction) {
  const customId = interaction.customId;

  if (!customId.startsWith("wheel:")) {
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
        "❌ This Wheel game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content:
        "❌ This Wheel game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (game.finished) {
    return true;
  }

  game.finished = true;

  const user = getUser(userId);

  if (user.cash < game.bet) {
    activeGames.delete(userId);

    await interaction.update({
      embeds: [
        embed(
          "❌ You no longer have enough cash for this bet.",
          COLORS.LOSE,
          "🎡 Wheel"
        )
      ],
      components: []
    });

    return true;
  }

  user.cash -= game.bet;

  const result =
    SEGMENTS[
      random(0, SEGMENTS.length - 1)
    ];

  const payout =
    Math.floor(
      game.bet * result.multiplier
    );

  if (payout > 0) {
    user.cash += payout;
  }

  const won =
    result.multiplier > 0;

  activeGames.delete(userId);

  saveData();

  await interaction.update({
    embeds: [
      embed(
        `🎡 **The wheel landed on:**\n\n` +
        `### ${result.label}\n\n` +
        `💵 Bet: **${money(
          game.bet
        )}** ${db.currency}\n` +
        `💰 Payout: **${money(
          payout
        )}** ${db.currency}\n` +
        `💳 Cash: **${money(
          user.cash
        )}** ${db.currency}`,
        won
          ? COLORS.WIN
          : COLORS.LOSE,
        won
          ? "🎉 WHEEL WIN!"
          : "💀 WHEEL LOSS"
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
  wheel,
  handleWheelButton
};
