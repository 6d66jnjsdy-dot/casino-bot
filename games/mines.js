const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

const SIZE = 25;
const MINES = 5;

function createBoard() {
  const board = Array(SIZE).fill(false);
  let placed = 0;

  while (placed < MINES) {
    const index = Math.floor(Math.random() * SIZE);

    if (!board[index]) {
      board[index] = true;
      placed++;
    }
  }

  return board;
}

function createRows(game, userId) {
  const rows = [];

  for (let rowIndex = 0; rowIndex < 5; rowIndex++) {
    const row = new ActionRowBuilder();

    for (let colIndex = 0; colIndex < 5; colIndex++) {
      const index = rowIndex * 5 + colIndex;
      const revealed = game.revealed.includes(index);

      row.addComponents(
        new ButtonBuilder()
          .setCustomId(`mines:${index}:${userId}`)
          .setLabel(
            revealed
              ? game.board[index]
                ? "💣"
                : "💎"
              : "❓"
          )
          .setStyle(
            revealed
              ? game.board[index]
                ? ButtonStyle.Danger
                : ButtonStyle.Success
              : ButtonStyle.Secondary
          )
          .setDisabled(revealed)
      );
    }

    rows.push(row);
  }

  return rows;
}

async function mines(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Mines פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  user.cash -= bet;
  saveData();

  const board = createBoard();

  const game = {
    bet,
    board,
    revealed: [],
    messageId: null
  };

  const msg = await message.reply({
    embeds: [
      embed(
        "💣 Mines",
        `💸 הימור: **${money(bet)}**\n\n` +
        `💣 מוקשים: **${MINES}**\n` +
        `💎 מצא את כל היהלומים כדי לנצח!\n\n` +
        `בחר משבצת:`
      )
    ],
    components: createRows(game, userId)
  });

  game.messageId = msg.id;
  activeGames.set(userId, game);
}

async function handleMinesButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "mines") {
    return;
  }

  const index = Number(parts[1]);
  const userId = parts[2];

  if (interaction.user.id !== userId) {
    return interaction.reply({
      content: "❌ המשחק הזה לא שלך.",
      ephemeral: true
    });
  }

  const game = activeGames.get(userId);

  if (!game) {
    return interaction.reply({
      content: "❌ המשחק כבר הסתיים.",
      ephemeral: true
    });
  }

  if (!Number.isInteger(index) || index < 0 || index >= SIZE) {
    return interaction.reply({
      content: "❌ משבצת לא חוקית.",
      ephemeral: true
    });
  }

  if (game.revealed.includes(index)) {
    return interaction.reply({
      content: "❌ המשבצת הזאת כבר נפתחה.",
      ephemeral: true
    });
  }

  await new Promise(resolve => setTimeout(resolve, 550));

  game.revealed.push(index);

  if (game.board[index]) {
    activeGames.delete(userId);
    saveData();

    const finalRows = [];

    for (let rowIndex = 0; rowIndex < 5; rowIndex++) {
      const row = new ActionRowBuilder();

      for (let colIndex = 0; colIndex < 5; colIndex++) {
        const i = rowIndex * 5 + colIndex;

        row.addComponents(
          new ButtonBuilder()
            .setCustomId(`mines:end:${i}:${userId}`)
            .setLabel(game.board[i] ? "💣" : "💎")
            .setStyle(
              game.board[i]
                ? ButtonStyle.Danger
                : ButtonStyle.Success
            )
            .setDisabled(true)
        );
      }

      finalRows.push(row);
    }

    return interaction.update({
      embeds: [
        embed(
          "💣 Mines — הפסדת",
          `פתחת מוקש!\n\n` +
          `💸 הפסד: **${money(game.bet)}**`
        )
      ],
      components: finalRows
    });
  }

  const safeCount = game.revealed.length;

  if (safeCount >= SIZE - MINES) {
    const payout = game.bet * 2;

    const user = getUser(userId);
    user.cash += payout;

    activeGames.delete(userId);
    saveData();

    return interaction.update({
      embeds: [
        embed(
          "💎 Mines — ניצחת!",
          `מצאת את כל **${SIZE - MINES}** המשבצות הבטוחות!\n\n` +
          `💰 זכייה: **${money(payout)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`
        )
      ],
      components: createRows(game, userId)
    });
  }

  return interaction.update({
    embeds: [
      embed(
        "💣 Mines",
        `💸 הימור: **${money(game.bet)}**\n\n` +
        `💎 משבצות בטוחות: **${safeCount}/${SIZE - MINES}**\n\n` +
        `המשך לבחור משבצות...`
      )
    ],
    components: createRows(game, userId)
  });
}

module.exports = {
  mines,
  handleMinesButton
};