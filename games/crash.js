const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { getUser, saveData } = require("../database");
const { money, embed } = require("../helpers");

const activeGames = new Map();

function createRow(userId) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`crash:cashout:${userId}`)
      .setLabel("💰 CASH OUT")
      .setStyle(ButtonStyle.Success)
  );
}

async function crash(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר משחק Crash פעיל.");
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply("❌ אין לך מספיק כסף.");
  }

  user.cash -= bet;
  saveData();

  const crashPoint = Math.max(
    1.01,
    1 + Math.random() * Math.random() * 9
  );

  const game = {
    bet,
    multiplier: 1.00,
    crashPoint,
    messageId: null,
    interval: null
  };

  const msg = await message.reply({
    embeds: [
      embed(
        "📈 Crash",
        `💸 הימור: **${money(bet)}**\n\n` +
        `📈 מכפיל: **x1.00**\n\n` +
        "לחץ CASH OUT לפני שהגרף קורס!"
      )
    ],
    components: [createRow(userId)]
  });

  game.messageId = msg.id;
  activeGames.set(userId, game);

  game.interval = setInterval(async () => {
    const currentGame = activeGames.get(userId);

    if (!currentGame) {
      clearInterval(game.interval);
      return;
    }

    currentGame.multiplier += 0.15;
    currentGame.multiplier =
      Math.round(currentGame.multiplier * 100) / 100;

    if (currentGame.multiplier >= currentGame.crashPoint) {
      clearInterval(currentGame.interval);
      activeGames.delete(userId);
      saveData();

      try {
        await msg.edit({
          embeds: [
            embed(
              "💥 Crash — התרסק!",
              `📉 המכפיל הגיע ל־**x${currentGame.crashPoint.toFixed(2)}**\n\n` +
              `💸 הפסד: **${money(currentGame.bet)}**`
            )
          ],
          components: []
        });
      } catch {}
      
      return;
    }

    try {
      await msg.edit({
        embeds: [
          embed(
            "📈 Crash",
            `💸 הימור: **${money(currentGame.bet)}**\n\n` +
            `📈 מכפיל: **x${currentGame.multiplier.toFixed(2)}**\n\n` +
            "💰 CASH OUT לפני ההתרסקות!"
          )
        ],
        components: [createRow(userId)]
      });
    } catch {}
  }, 1000);
}

async function handleCrashButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3 || parts[0] !== "crash") {
    return;
  }

  const action = parts[1];
  const userId = parts[2];

  if (action !== "cashout") return;

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

  clearInterval(game.interval);
  activeGames.delete(userId);

  const user = getUser(userId);
  const payout = Math.floor(game.bet * game.multiplier);

  user.cash += payout;
  saveData();

  return interaction.update({
    embeds: [
      embed(
        "📈 Crash — CASH OUT!",
        `🎯 יצאת ב־**x${game.multiplier.toFixed(2)}**\n\n` +
        `💰 זכייה: **${money(payout)}**\n` +
        `💵 יתרה: **${money(user.cash)}**`
      )
    ],
    components: []
  });
}

module.exports = {
  crash,
  handleCrashButton
};