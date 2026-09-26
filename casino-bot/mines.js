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
   MINES
   ============================================================ */

const activeGames = new Map();

const BOARD_SIZE = 25;
const MINE_COUNT = 5;
const CLICK_DELAY = 550;

/* ============================================================
   CREATE BOARD
   ============================================================ */

function createBoard() {
  const mines = new Set();

  while (mines.size < MINE_COUNT) {
    mines.add(
      random(0, BOARD_SIZE - 1)
    );
  }

  return mines;
}

/* ============================================================
   BUTTON ROWS
   ============================================================ */

function createRows(
  game,
  disabled = false
) {
  const rows = [];

  for (let r = 0; r < 5; r++) {
    const row =
      new ActionRowBuilder();

    for (let c = 0; c < 5; c++) {
      const index =
        r * 5 + c;

      let label = "⬜";

      if (
        game.revealed.has(index)
      ) {
        label =
          game.mines.has(index)
            ? "💣"
            : "💎";
      }

      const button =
        new ButtonBuilder()
          .setCustomId(
            `mines:${index}:${game.userId}`
          )
          .setLabel(label)
          .setStyle(
            game.revealed.has(index)
              ? ButtonStyle.Secondary
              : ButtonStyle.Primary
          )
          .setDisabled(
            disabled ||
            game.revealed.has(index)
          );

      row.addComponents(button);
    }

    rows.push(row);
  }

  return rows;
}

/* ============================================================
   START GAME
   ============================================================ */

async function mines(
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
          "❌ You already have an active Mines game.",
          COLORS.LOSE,
          "💣 Mines"
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

  user.cash -= bet;

  const game = {
    userId,
    bet,
    mines: createBoard(),
    revealed: new Set(),
    finished: false,
    lastClick: 0,
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
          `💣 **${MINE_COUNT} mines** are hidden in the board.\n\n` +
          `💵 Bet: **${money(
            bet
          )}** ${db.currency}\n\n` +
          `💎 Find safe tiles to increase your payout.\n` +
          `💣 Hit a mine and lose your bet.`,
          COLORS.ACTIVE,
          "💣 Mines"
        )
      ],
      components:
        createRows(game)
    });

  game.message = sent;
}

/* ============================================================
   CASHOUT
   ============================================================ */

async function cashout(
  interaction,
  game
) {
  const user =
    getUser(game.userId);

  const safeCount =
    game.revealed.size;

  /*
   * Payout increases with every
   * safe tile revealed.
   */
  const multiplier =
    1 +
    safeCount * 0.18;

  const payout =
    Math.floor(
      game.bet *
      multiplier
    );

  user.cash += payout;

  game.finished = true;

  activeGames.delete(
    game.userId
  );

  saveData();

  await interaction.update({
    embeds: [
      embed(
        `💎 You cashed out safely!\n\n` +
        `💎 Safe tiles: **${safeCount}**\n` +
        `📈 Multiplier: **${multiplier.toFixed(2)}x**\n\n` +
        `💵 Bet: **${money(
          game.bet
        )}** ${db.currency}\n` +
        `💰 Payout: **${money(
          payout
        )}** ${db.currency}\n` +
        `💳 Cash: **${money(
          user.cash
        )}** ${db.currency}`,
        COLORS.WIN,
        "💎 CASHED OUT!"
      )
    ],
    components:
      createRows(
        game,
        true
      )
  });
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleMinesButton(
  interaction
) {
  const customId =
    interaction.customId;

  if (
    !customId.startsWith(
      "mines:"
    )
  ) {
    return false;
  }

  const parts =
    customId.split(":");

  const index =
    Number(parts[1]);

  const userId =
    parts[2];

  if (
    interaction.user.id !==
    userId
  ) {
    await interaction.reply({
      content:
        "❌ This Mines game belongs to another player.",
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
        "❌ This Mines game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (
    game.finished
  ) {
    return true;
  }

  /*
   * Prevent extremely fast repeated clicks.
   */
  const now =
    Date.now();

  if (
    now -
      game.lastClick <
    CLICK_DELAY
  ) {
    await interaction.reply({
      content:
        "⏳ Slow down a little.",
      ephemeral: true
    });

    return true;
  }

  game.lastClick = now;

  if (
    !Number.isInteger(index) ||
    index < 0 ||
    index >= BOARD_SIZE
  ) {
    return true;
  }

  if (
    game.revealed.has(index)
  ) {
    return true;
  }

  /*
   * Mine hit.
   */
  if (
    game.mines.has(index)
  ) {
    game.revealed.add(index);
    game.finished = true;

    activeGames.delete(
      userId
    );

    saveData();

    await interaction.update({
      embeds: [
        embed(
          `💣 **BOOM!**\n\n` +
          `You hit a mine.\n\n` +
          `💵 Lost: **${money(
            game.bet
          )}** ${db.currency}`,
          COLORS.LOSE,
          "💣 MINED!"
        )
      ],
      components:
        createRows(
          game,
          true
        )
    });

    return true;
  }

  /*
   * Safe tile.
   */
  game.revealed.add(index);

  /*
   * All safe tiles discovered.
   */
  if (
    game.revealed.size >=
    BOARD_SIZE -
      MINE_COUNT
  ) {
    return cashout(
      interaction,
      game
    );
  }

  const multiplier =
    1 +
    game.revealed.size *
      0.18;

  await interaction.update({
    embeds: [
      embed(
        `💎 Safe!\n\n` +
        `💎 Safe tiles: **${game.revealed.size}**\n` +
        `📈 Current multiplier: **${multiplier.toFixed(2)}x**\n` +
        `💰 Current cashout: **${money(
          Math.floor(
            game.bet *
              multiplier
          )
        )}** ${db.currency}\n\n` +
        `Continue playing or cash out.`,
        COLORS.ACTIVE,
        "💣 Mines"
      )
    ],
    components:
      createRows(game)
  });

  return true;
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  mines,
  handleMinesButton
};
