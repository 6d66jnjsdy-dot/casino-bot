const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

async function higherLower(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Higher/Lower פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  user.cash -= bet;
  saveData();

  const current = Math.floor(Math.random() * 98) + 2;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`hl:higher:${userId}`)
      .setLabel("⬆️ Higher")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`hl:lower:${userId}`)
      .setLabel("⬇️ Lower")
      .setStyle(ButtonStyle.Secondary)
  );

  const msg = await message.reply({
    embeds: [
      embed(
        "📈 Higher / Lower",
        `**מספר נוכחי:** ${current}\n\n` +
        `💸 הימור: **${money(bet)}**\n\n` +
        `האם המספר הבא יהיה גבוה או נמוך יותר?`
      )
    ],
    components: [row]
  });

  activeGames.set(userId, {
    bet,
    current,
    messageId: msg.id
  });
}

async function handleHigherLowerButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "hl") return;

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

  const next = Math.floor(Math.random() * 100) + 1;

  let won = false;

  if (choice === "higher") {
    won = next > game.current;
  } else if (choice === "lower") {
    won = next < game.current;
  }

  if (won && Math.random() < 0.02) {
    won = false;
  }

  const user = getUser(userId);
  const bet = game.bet;

  activeGames.delete(userId);

  if (won) {
    user.cash += bet * 2;
    saveData();

    return interaction.update({
      embeds: [
        embed(
          "📈 Higher / Lower — ניצחת!",
          `המספר הקודם: **${game.current}**\n` +
          `המספר החדש: **${next}**\n\n` +
          `💰 זכייה: **${money(bet * 2)}**\n` +
          `💵 יתרה: **${money(user.cash)}**`
        )
      ],
      components: []
    });
  }

  saveData();

  return interaction.update({
    embeds: [
      embed(
        "📉 Higher / Lower — הפסדת",
        `המספר הקודם: **${game.current}**\n` +
        `המספר החדש: **${next}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  higherLower,
  handleHigherLowerButton
};