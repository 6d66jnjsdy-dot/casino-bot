const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

const segments = [
  { multiplier: 0, weight: 35 },
  { multiplier: 0.5, weight: 25 },
  { multiplier: 1, weight: 20 },
  { multiplier: 2, weight: 12 },
  { multiplier: 3, weight: 6 },
  { multiplier: 5, weight: 2 }
];

function spinWheel() {
  const totalWeight = segments.reduce(
    (sum, segment) => sum + segment.weight,
    0
  );

  let random = Math.random() * totalWeight;

  for (const segment of segments) {
    random -= segment.weight;

    if (random <= 0) {
      return segment.multiplier;
    }
  }

  return 0;
}

function createRow(userId) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`wheel:spin:${userId}`)
      .setLabel("🎡 SPIN")
      .setStyle(ButtonStyle.Primary)
  );
}

async function wheel(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Wheel פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  const msg = await message.reply({
    embeds: [
      embed(
        "🎡 Wheel",
        `💸 הימור: **${money(bet)}**\n\n` +
        "לחץ על SPIN כדי לסובב את הגלגל!"
      )
    ],
    components: [createRow(userId)]
  });

  activeGames.set(userId, {
    bet,
    messageId: msg.id
  });
}

async function handleWheelButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "wheel") {
    return;
  }

  const action = parts[1];
  const userId = parts[2];

  if (action !== "spin") return;

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
          "❌ Wheel",
          "אין לך מספיק כסף בשביל ההימור."
        )
      ],
      components: []
    });
  }

  user.cash -= bet;

  const multiplier = spinWheel();
  const payout = Math.floor(bet * multiplier);

  if (payout > 0) {
    user.cash += payout;
  }

  saveData();
  activeGames.delete(userId);

  if (multiplier > 0) {
    return interaction.update({
      embeds: [
        embed(
          "🎡 Wheel — זכייה!",
          `🎯 המכפיל: **x${multiplier}**\n\n` +
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
        "🎡 Wheel — הפסדת",
        `🎯 המכפיל: **x0**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  wheel,
  handleWheelButton
};