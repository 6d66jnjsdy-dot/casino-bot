require("dotenv").config();

const {
  Client,
  GatewayIntentBits
} = require("discord.js");

const fs = require("fs");

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ]
});

const FILE = "./games.json";

function loadGames() {
  try {
    return JSON.parse(fs.readFileSync(FILE, "utf8"));
  } catch {
    return {};
  }
}

client.once("ready", () => {
  console.log(`Bot B מחובר בתור ${client.user.tag}`);
});

client.on("messageCreate", async message => {
  if (message.author.bot) return;

  if (!message.content.startsWith("$predict ")) return;

  const link = message.content.slice("$predict ".length).trim();

  const match = link.match(
    /^https?:\/\/discord\.com\/channels\/(\d+)\/(\d+)\/(\d+)$/
  );

  if (!match) {
    return message.reply(
      "❌ קישור Discord לא תקין.\n\n" +
      "דוגמה:\n" +
      "`$predict https://discord.com/channels/SERVER/CHANNEL/MESSAGE`"
    );
  }

  const [, guildId, channelId, messageId] = match;

  const games = loadGames();
  const game = games[messageId];

  if (!game) {
    return message.reply(
      "❌ לא מצאתי משחק Mines לפי הקישור הזה."
    );
  }

  if (
    game.guildId !== guildId ||
    game.channelId !== channelId
  ) {
    return message.reply(
      "❌ המשחק לא תואם לקישור שסיפקת."
    );
  }

  if (!game.debug) {
    return message.reply(
      "🔒 המשחק הזה אינו משחק Debug."
    );
  }

  const bomb = Number(game.bomb);

  const row = Math.floor(bomb / 5) + 1;
  const column = (bomb % 5) + 1;

  return message.reply(
    `🔮 **PREDICT — DEBUG**\n\n` +
    `💣 פצצה: **${bomb + 1}**\n` +
    `📍 שורה: **${row}**\n` +
    `📍 עמודה: **${column}**`
  );
});

client.login(process.env.BOT_B_TOKEN);