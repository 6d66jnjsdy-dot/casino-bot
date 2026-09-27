require("dotenv").config();

const {
  Client,
  GatewayIntentBits,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  EmbedBuilder
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

if (!fs.existsSync(FILE)) {
  fs.writeFileSync(FILE, "{}");
}

function loadGames() {
  try {
    return JSON.parse(fs.readFileSync(FILE, "utf8"));
  } catch {
    return {};
  }
}

function saveGames(games) {
  fs.writeFileSync(FILE, JSON.stringify(games, null, 2));
}

const games = loadGames();

function createBoard(game) {
  const rows = [];

  for (let r = 0; r < 5; r++) {
    const row = new ActionRowBuilder();

    for (let c = 0; c < 5; c++) {
      const index = r * 5 + c;

      let label = "⬜";

      if (game.revealed.includes(index)) {
        label = index === game.bomb ? "💣" : "💎";
      }

      row.addComponents(
        new ButtonBuilder()
          .setCustomId(`mine:${game.messageId}:${index}`)
          .setLabel(label)
          .setStyle(ButtonStyle.Secondary)
      );
    }

    rows.push(row);
  }

  return rows;
}

client.once("ready", () => {
  console.log(`Bot מחובר בתור ${client.user.tag}`);
});

client.on("messageCreate", async message => {
  if (message.author.bot) return;

  // =========================
  // MINES DEBUG
  // =========================

  if (message.content === "$mines-debug") {
    const game = {
      userId: message.author.id,
      guildId: message.guildId,
      channelId: message.channelId,
      bomb: Math.floor(Math.random() * 25),
      revealed: [],
      debug: true
    };

    const msg = await message.channel.send({
      embeds: [
        new EmbedBuilder()
          .setTitle("💣 Mines — DEBUG")
          .setDescription("בחר משבצת כדי להתחיל.")
      ],
      components: createBoard({
        ...game,
        messageId: "pending"
      })
    });

    game.messageId = msg.id;

    games[msg.id] = game;
    saveGames(games);

    await msg.edit({
      components: createBoard(game)
    });

    return;
  }

  // =========================
  // MINES רגיל
  // =========================

  if (message.content === "$mines") {
    const game = {
      userId: message.author.id,
      guildId: message.guildId,
      channelId: message.channelId,
      bomb: Math.floor(Math.random() * 25),
      revealed: [],
      debug: false
    };

    const msg = await message.channel.send({
      embeds: [
        new EmbedBuilder()
          .setTitle("💣 Mines")
          .setDescription("בחר משבצת כדי להתחיל.")
      ],
      components: createBoard({
        ...game,
        messageId: "pending"
      })
    });

    game.messageId = msg.id;

    games[msg.id] = game;
    saveGames(games);

    await msg.edit({
      components: createBoard(game)
    });

    return;
  }

  // =========================
  // PREDICT
  // =========================

  if (message.content.startsWith("$predict ")) {
    const link = message.content
      .slice("$predict ".length)
      .trim();

    const match = link.match(
      /^https?:\/\/discord\.com\/channels\/(\d+)\/(\d+)\/(\d+)$/
    );

    if (!match) {
      return message.reply(
        "❌ קישור Discord לא תקין.\n\n" +
        "`$predict https://discord.com/channels/SERVER/CHANNEL/MESSAGE`"
      );
    }

    const [, guildId, channelId, messageId] = match;

    const game = games[messageId];

    if (!game) {
      return message.reply(
        "❌ לא מצאתי משחק Mines לפי הקישור."
      );
    }

    if (
      game.guildId !== guildId ||
      game.channelId !== channelId
    ) {
      return message.reply(
        "❌ המשחק לא תואם לקישור."
      );
    }

    if (!game.debug) {
      return message.reply(
        "🔒 `$predict` זמין רק למשחקי Debug."
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
  }
});

// =========================
// BUTTONS
// =========================

client.on("interactionCreate", async interaction => {
  if (!interaction.isButton()) return;
  if (!interaction.customId.startsWith("mine:")) return;

  const [, messageId, indexText] =
    interaction.customId.split(":");

  const index = Number(indexText);
  const game = games[messageId];

  if (!game) {
    return interaction.reply({
      content: "❌ המשחק לא נמצא.",
      ephemeral: true
    });
  }

  if (interaction.user.id !== game.userId) {
    return interaction.reply({
      content: "❌ זה לא המשחק שלך.",
      ephemeral: true
    });
  }

  if (game.revealed.includes(index)) {
    return interaction.reply({
      content: "⬜ כבר פתחת את המשבצת הזאת.",
      ephemeral: true
    });
  }

  game.revealed.push(index);

  if (index === game.bomb) {
    await interaction.update({
      embeds: [
        new EmbedBuilder()
          .setTitle("💥 BOOM!")
          .setDescription("מצאת את הפצצה!")
      ],
      components: createBoard(game)
    });

    saveGames(games);
    return;
  }

  await interaction.update({
    embeds: [
      new EmbedBuilder()
        .setTitle("💣 Mines")
        .setDescription("💎 בטוח! המשך לשחק.")
    ],
    components: createBoard(game)
  });

  saveGames(games);
});

client.login(process.env.BOT_TOKEN);