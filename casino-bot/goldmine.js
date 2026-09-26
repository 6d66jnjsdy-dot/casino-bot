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
   GOLDMINE
   ============================================================ */

const activeGames = new Map();

const GRID_SIZE = 9;
const GOLD_COUNT = 3;

/* ============================================================
   CREATE BOARD
   ============================================================ */

function createBoard() {
  const gold = new Set();

  while (gold.size < GOLD_COUNT) {
    gold.add(
      random(0, GRID_SIZE - 1)
    );
  }

  return gold;
}

/* ============================================================
   CREATE BUTTONS
   ============================================================ */

function createRow(game, disabled = false) {
  const row = new ActionRowBuilder();

  for (let i = 0; i < GRID_SIZE; i++) {
    let label = "⛏️";

    if (game.revealed.has(i)) {
      label = game.gold.has(i)
        ? "💰"
        : "🪨";
    }

    row.addComponents(
      new ButtonBuilder()
        .setCustomId(
          `goldmine:${i}:${game.userId}`
        )
        .setLabel(label)
        .setStyle(
          game.revealed.has(i)
            ? ButtonStyle.Secondary
            : ButtonStyle.Primary
        )
        .setDisabled(
          disabled ||
          game.revealed.has(i)
        )
    );
  }

  return [row];
}

/* ============================================================
   START GAME
   ============================================================ */

async function goldmine(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Goldmine game.",
          COLORS.LOSE,
          "⛏️ Goldmine"
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
    gold: createBoard(),
    revealed: new Set(),
    finished: false,
    message: null
  };

  activeGames.set(userId, game);

  const sent = await message.reply({
    embeds: [
      embed(
        `⛏️ **GOLDMINE**\n\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `💰 Find the hidden gold!\n` +
        `🪨 Some tiles contain nothing.\n\n` +
        `Choose a tile to begin.`,
        COLORS.ACTIVE,
        "⛏️ Goldmine"
      )
    ],
    components: createRow(game)
  });

  game.message = sent;
}

/* ============================================================
   FINISH GAME
   ============================================================ */

async function finishGame(
  interaction,
  game,
  won
) {
  const user = getUser(game.userId);

  game.finished = true;

  activeGames.delete(game.userId);

  let payout = 0;

  if (won) {
    payout = game.bet * 2;
    user.cash += payout;
  }

  saveData();

  await interaction.update({
    embeds: [
      embed(
        won
          ? `💰 **You found the gold!**\n\n` +
            `💵 Bet: **${money(
              game.bet
            )}** ${db.currency}\n` +
            `💰 Payout: **${money(
              payout
            )}** ${db.currency}\n` +
            `💳 Cash: **${money(
              user.cash
            )}** ${db.currency}`
          : `🪨 **Nothing here!**\n\n` +
            `You lost your bet.\n\n` +
            `💵 Lost: **${money(
              game.bet
            )}** ${db.currency}\n` +
            `💳 Cash: **${money(
              user.cash
            )}** ${db.currency}`,
        won
          ? COLORS.WIN
          : COLORS.LOSE,
        won
          ? "💰 GOLD FOUND!"
          : "🪨 EMPTY MINE"
      )
    ],
    components: createRow(
      game,
      true
    )
  });
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleGoldmineButton(interaction) {
  const customId = interaction.customId;

  if (!customId.startsWith("goldmine:")) {
    return false;
  }

  const parts = customId.split(":");

  const index = Number(parts[1]);
  const userId = parts[2];

  if (interaction.user.id !== userId) {
    await interaction.reply({
      content:
        "❌ This Goldmine game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content:
        "❌ This Goldmine game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (game.finished) {
    return true;
  }

  if (
    !Number.isInteger(index) ||
    index < 0 ||
    index >= GRID_SIZE
  ) {
    return true;
  }

  if (game.revealed.has(index)) {
    return true;
  }

  /*
   * Remove the bet only on the first actual selection.
   */
  if (game.revealed.size === 0) {
    const user = getUser(userId);

    if (user.cash < game.bet) {
      game.finished = true;
      activeGames.delete(userId);

      await interaction.update({
        embeds: [
          embed(
            "❌ You no longer have enough cash for this bet.",
            COLORS.LOSE,
            "⛏️ Goldmine"
          )
        ],
        components: []
      });

      return true;
    }

    user.cash -= game.bet;
    saveData();
  }

  game.revealed.add(index);

  if (game.gold.has(index)) {
    await finishGame(
      interaction,
      game,
      true
    );

    return true;
  }

  /*
   * If all non-gold tiles are revealed,
   * the game ends as a loss.
   */
  if (
    game.revealed.size >=
    GRID_SIZE
  ) {
    await finishGame(
      interaction,
      game,
      false
    );

    return true;
  }

  const safeTiles =
    game.revealed.size;

  const multiplier =
    1 +
    safeTiles * 0.25;

  const currentValue =
    Math.floor(
      game.bet * multiplier
    );

  const user = getUser(userId);

  await interaction.update({
    embeds: [
      embed(
        `🪨 Empty mine!\n\n` +
        `⛏️ Tiles searched: **${safeTiles}**\n` +
        `📈 Current multiplier: **${multiplier.toFixed(2)}x**\n` +
        `💰 Current value: **${money(
          currentValue
        )}** ${db.currency}\n\n` +
        `Keep searching for gold.`,
        COLORS.ACTIVE,
        "⛏️ Goldmine"
      )
    ],
    components: createRow(game)
  });

  return true;
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  goldmine,
  handleGoldmineButton
};
