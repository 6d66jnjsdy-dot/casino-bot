const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

const symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"];

const payouts = {
  "🍒": 2,
  "🍋": 2.5,
  "🍊": 3,
  "🍇": 4,
  "🔔": 5,
  "💎": 8,
  "7️⃣": 12
};

function randomSymbol() {
  return symbols[Math.floor(Math.random() * symbols.length)];
}

function spin() {
  let result = [
    randomSymbol(),
    randomSymbol(),
    randomSymbol()
  ];

  // 4% chance to break a winning triple
  if (
    result[0] === result[1] &&
    result[1] === result[2] &&
    Math.random() < 0.04
  ) {
    let replacement = randomSymbol();

    while (replacement === result[0]) {
      replacement = randomSymbol();
    }

    result[2] = replacement;
  }

  return result;
}

function createRow(userId) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`slots:spin:${userId}`)
      .setLabel("🎰 SPIN")
      .setStyle(ButtonStyle.Primary)
  );
}

async function slots(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Slots פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  const msg = await message.reply({
    embeds: [
      embed(
        "🎰 Slots",
        `💸 הימור: **${money(bet)}**\n\n` +
        "לחץ על SPIN כדי לסובב!"
      )
    ],
    components: [createRow(userId)]
  });

  activeGames.set(userId, {
    bet,
    messageId: msg.id
  });
}

async function handleSlotsButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "slots") {
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
          "❌ Slots",
          "אין לך מספיק כסף בשביל ההימור."
        )
      ],
      components: []
    });
  }

  user.cash -= bet;

  const result = spin();

  const isWin =
    result[0] === result[1] &&
    result[1] === result[2];

  let payout = 0;

  if (isWin) {
    payout = Math.floor(bet * payouts[result[0]]);
    user.cash += payout;
  }

  saveData();
  activeGames.delete(userId);

  const display = result.join("  ");

  if (isWin) {
    return interaction.update({
      embeds: [
        embed(
          "🎰 Slots — זכייה!",
          `**${display}**\n\n` +
          `🎉 מכפיל: **x${payouts[result[0]]}**\n` +
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
        "🎰 Slots — הפסדת",
        `**${display}**\n\n` +
        `💸 הפסד: **${money(bet)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  slots,
  handleSlotsButton
};