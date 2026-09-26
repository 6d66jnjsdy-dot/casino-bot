const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

async function cockfight(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Cockfight פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
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
        "🐔 Cockfight",
        `**הימור:** ${money(bet)}\n\n` +
        "בחר את התרנגול שלך:"
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

  if (user.cash < bet) {
    activeGames.delete(userId);

    return interaction.update({
      embeds: [
        embed(
          "❌ Cockfight",
          "אין לך מספיק כסף בשביל ההימור."
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
          "🐔 Cockfight — ניצחת!",
          `המנצח: **${winnerText}**\n\n` +
          `💰 זכייה: **${money(bet * 2)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`
        )
      ],
      components: []
    });
  }

  return interaction.update({
    embeds: [
      embed(
        "🐔 Cockfight — הפסדת",
        `המנצח: **${winnerText}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  cockfight,
  handleCockfightButton
};