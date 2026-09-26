const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

const SPOTS = 9;
const GOLD_SPOTS = 3;

function createBoard() {
  const board = Array(SPOTS).fill(false);
  let placed = 0;

  while (placed < GOLD_SPOTS) {
    const index = Math.floor(Math.random() * SPOTS);

    if (!board[index]) {
      board[index] = true;
      placed++;
    }
  }

  return board;
}

function createRow(game, userId) {
  const row = new ActionRowBuilder();

  for (let i = 0; i < SPOTS; i++) {
    const revealed = game.revealed.includes(i);

    row.addComponents(
      new ButtonBuilder()
        .setCustomId(`goldmine:${i}:${userId}`)
        .setLabel(
          revealed
            ? game.board[i]
              ? "🪙"
              : "⬛"
            : "❓"
        )
        .setStyle(
          revealed
            ? game.board[i]
              ? ButtonStyle.Success
              : ButtonStyle.Secondary
            : ButtonStyle.Primary
        )
        .setDisabled(revealed)
    );
  }

  return row;
}

async function goldmine(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Goldmine פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  const game = {
    bet,
    board: createBoard(),
    revealed: [],
    multiplier: 1
  };

  const msg = await message.reply({
    embeds: [
      embed(
        "⛏️ Goldmine",
        `💸 הימור: **${money(bet)}**\n\n` +
        "מצא זהב כדי לזכות!\n" +
        "בחר משבצת:"
      )
    ],
    components: [createRow(game, userId)]
  });

  game.messageId = msg.id;
  activeGames.set(userId, game);
}

async function handleGoldmineButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "goldmine") {
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

  if (!Number.isInteger(index) || index < 0 || index >= SPOTS) {
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

  game.revealed.push(index);

  const user = getUser(userId);

  if (game.board[index]) {
    const payout = Math.floor(game.bet * 2);

    user.cash += payout;

    activeGames.delete(userId);
    saveData();

    return interaction.update({
      embeds: [
        embed(
          "⛏️ Goldmine — מצאת זהב!",
          `🪙 מצאת זהב!\n\n` +
          `💰 זכייה: **${money(payout)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`
        )
      ],
      components: [createRow(game, userId)]
    });
  }

  game.multiplier += 0.25;

  if (game.revealed.length >= SPOTS) {
    activeGames.delete(userId);
    saveData();

    return interaction.update({
      embeds: [
        embed(
          "⛏️ Goldmine — הפסדת",
          `לא נשאר זהב למצוא.\n\n` +
          `💸 הפסד: **${money(game.bet)}**`
        )
      ],
      components: [createRow(game, userId)]
    });
  }

  return interaction.update({
    embeds: [
      embed(
        "⛏️ Goldmine",
        `💸 הימור: **${money(game.bet)}**\n` +
        `📈 מכפיל: **x${game.multiplier.toFixed(2)}**\n\n` +
        "לא היה כאן זהב. נסה שוב!"
      )
    ],
    components: [createRow(game, userId)]
  });
}

module.exports = {
  goldmine,
  handleGoldmineButton
};