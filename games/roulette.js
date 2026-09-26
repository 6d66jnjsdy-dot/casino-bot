const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

const redNumbers = new Set([
  1, 3, 5, 7, 9,
  12, 14, 16, 18,
  19, 21, 23, 25, 27,
  30, 32, 34, 36
]);

function getColor(number) {
  if (number === 0) return "green";
  return redNumbers.has(number) ? "red" : "black";
}

function colorText(color) {
  if (color === "red") return "🔴 אדום";
  if (color === "black") return "⚫ שחור";
  return "🟢 ירוק";
}

function createRow(userId) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`roulette:red:${userId}`)
      .setLabel("🔴 אדום")
      .setStyle(ButtonStyle.Danger),

    new ButtonBuilder()
      .setCustomId(`roulette:black:${userId}`)
      .setLabel("⚫ שחור")
      .setStyle(ButtonStyle.Secondary),

    new ButtonBuilder()
      .setCustomId(`roulette:green:${userId}`)
      .setLabel("🟢 ירוק")
      .setStyle(ButtonStyle.Success)
  );
}

async function roulette(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Roulette פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  const msg = await message.reply({
    embeds: [
      embed(
        "🎡 Roulette",
        `💸 הימור: **${money(bet)}**\n\n` +
        "בחר צבע:"
      )
    ],
    components: [createRow(userId)]
  });

  activeGames.set(userId, {
    bet,
    messageId: msg.id
  });
}

async function handleRouletteButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "roulette") {
    return;
  }

  const choice = parts[1];
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

  const user = getUser(userId);
  const bet = game.bet;

  if (user.cash < bet) {
    activeGames.delete(userId);

    return interaction.update({
      embeds: [
        embed(
          "❌ Roulette",
          "אין לך מספיק כסף בשביל ההימור."
        )
      ],
      components: []
    });
  }

  const number = Math.floor(Math.random() * 37);
  const resultColor = getColor(number);

  user.cash -= bet;

  let payout = 0;
  let won = false;

  if (choice === resultColor) {
    won = true;

    if (choice === "green") {
      payout = bet * 14;
    } else {
      payout = bet * 2;
    }

    user.cash += payout;
  }

  saveData();
  activeGames.delete(userId);

  if (won) {
    return interaction.update({
      embeds: [
        embed(
          "🎡 Roulette — ניצחת!",
          `🎯 המספר: **${number}**\n` +
          `🎨 הצבע: **${colorText(resultColor)}**\n\n` +
          `💰 זכייה: **${money(payout)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`
        )
      ],
      components: []
    });
  }

  return interaction.update({
    embeds: [
      embed(
        "🎡 Roulette — הפסדת",
        `🎯 המספר: **${number}**\n` +
        `🎨 הצבע: **${colorText(resultColor)}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  roulette,
  handleRouletteButton
};