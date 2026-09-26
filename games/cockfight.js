const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed, validBet } = require("../helpers");

const activeGames = new Map();

async function cockfight(message, args, user) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ יש לך כבר משחק Cockfight פעיל.",
          0xe74c3c,
          "🐔 Cockfight"
        )
      ]
    });
  }

  const bet = validBet(message, args);

  if (!bet) return;

  if (bet > user.cash) {
    return message.reply({
      embeds: [
        embed(
          "❌ אין לך מספיק כסף.",
          0xe74c3c,
          "🐔 Cockfight"
        )
      ]
    });
  }

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`cfight:left:${userId}`)
      .setLabel("🐔 תרנגול שמאל")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`cfight:right:${userId}`)
      .setLabel("🐔 תרנגול ימין")
      .setStyle(ButtonStyle.Secondary)
  );

  const msg = await message.reply({
    embeds: [
      embed(
        `**הימור:** ${money(bet)}\n\nבחר את התרנגול שלך:`,
        0x1c1c1c,
        "🐔 Cockfight"
      )
    ],
    components: [row]
  });

  activeGames.set(userId, {
    bet,
    messageId: msg.id
  });
}

async function handleCockfightButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "cfight") return;

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

  if (bet > user.cash) {
    activeGames.delete(userId);

    return interaction.update({
      embeds: [
        embed(
          "אין לך מספיק כסף בשביל ההימור.",
          0xe74c3c,
          "🐔 Cockfight"
        )
      ],
      components: []
    });
  }

  user.cash -= bet;

  const winner = Math.random() < 0.5 ? "left" : "right";
  const won = choice === winner;

  if (won) {
    user.cash += bet * 2;
  }

  saveData();
  activeGames.delete(userId);

  const winnerText =
    winner === "left"
      ? "🐔 התרנגול השמאלי"
      : "🐔 התרנגול הימני";

  if (won) {
    return interaction.update({
      embeds: [
        embed(
          `המנצח: **${winnerText}**\n\n` +
          `💰 זכייה: **${money(bet * 2)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`,
          0x2ecc71,
          "🐔 Cockfight — ניצחת!"
        )
      ],
      components: []
    });
  }

  return interaction.update({
    embeds: [
      embed(
        `המנצח: **${winnerText}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`,
        0xe74c3c,
        "🐔 Cockfight — הפסדת"
      )
    ],
    components: []
  });
}

module.exports = {
  cockfight,
  handleCockfightButton
};