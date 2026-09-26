const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

async function coinflip(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Coinflip פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`cf:heads:${userId}`)
      .setLabel("🪙 Heads")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`cf:tails:${userId}`)
      .setLabel("🪙 Tails")
      .setStyle(ButtonStyle.Secondary)
  );

  const msg = await message.reply({
    embeds: [
      embed(
        "🪙 Coinflip",
        `**הימור:** ${money(bet)}\n\nבחר Heads או Tails.`
      )
    ],
    components: [row]
  });

  activeGames.set(userId, {
    bet,
    messageId: msg.id
  });
}

async function handleCoinflipButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "cf") return;

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
          "❌ Coinflip",
          "אין לך מספיק כסף בשביל ההימור."
        )
      ],
      components: []
    });
  }

  // מורידים את ההימור רק כשהשחקן בוחר
  user.cash -= bet;

  const result = Math.random() < 0.5 ? "heads" : "tails";
  const won = choice === result;

  if (won) {
    user.cash += bet * 2;
  }

  saveData();
  activeGames.delete(userId);

  const resultText =
    result === "heads" ? "🪙 Heads" : "🪙 Tails";

  if (won) {
    return interaction.update({
      embeds: [
        embed(
          "🪙 Coinflip — ניצחת!",
          `התוצאה: **${resultText}**\n\n` +
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
        "🪙 Coinflip — הפסדת",
        `התוצאה: **${resultText}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  coinflip,
  handleCoinflipButton
};