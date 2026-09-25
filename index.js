const {
  Client,
  GatewayIntentBits,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  PermissionFlagsBits
} = require("discord.js");

const express = require("express");

const app = express();
const PORT = process.env.PORT || 10000;

app.get("/", (req, res) => {
  res.send("Casino Bot is Online 24/7!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Web server running on port ${PORT}`);
});

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

const PREFIX = "$";
const MIN_BET = 150;

const db = {
  users: {},
  currency: "💸"
};

function getUser(id) {
  if (!db.users[id]) {
    db.users[id] = { cash: 0 };
  }

  return db.users[id];
}

function money(amount) {
  return Math.floor(amount).toLocaleString();
}

function random(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function validBet(message, args) {
  const bet = Number(args[0]);

  if (!Number.isFinite(bet) || bet < MIN_BET) {
    message.reply(
      `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
    );
    return null;
  }

  const user = getUser(message.author.id);

  if (bet > user.cash) {
    message.reply("❌ You don't have enough money.");
    return null;
  }

  return Math.floor(bet);
}

function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map((component) =>
      ButtonBuilder.from(component).setDisabled(true)
    )
  );
}

client.once("ready", () => {
  console.log(`Logged in as ${client.user.tag}`);
});

/* =========================
   COMMANDS
========================= */

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;
  if (!message.content.startsWith(PREFIX)) return;

  const args = message.content
    .slice(PREFIX.length)
    .trim()
    .split(/\s+/);

  const command = (args.shift() || "").toLowerCase();
  const user = getUser(message.author.id);

  /* BALANCE */

  if (["bal", "balance"].includes(command)) {
    return message.reply({
      embeds: [
        new EmbedBuilder()
          .setTitle("💰 Balance")
          .setDescription(
            `You have **${money(user.cash)}** ${db.currency}`
          )
      ]
    });
  }

  /* CURRENCY */

  if (command === "currency") {
    return message.reply(
      `Current currency: ${db.currency}`
    );
  }

  /* ADD MONEY */

  if (command === "addmoney") {
    if (
      !message.member.permissions.has(
        PermissionFlagsBits.Administrator
      )
    ) {
      return message.reply(
        "❌ You need Administrator permission."
      );
    }

    const target = message.mentions.users.first();
    const amount = Number(args[1]);

    if (
      !target ||
      !Number.isFinite(amount) ||
      amount <= 0
    ) {
      return message.reply(
        "❌ Usage: `$addmoney @user 1000`"
      );
    }

    getUser(target.id).cash += Math.floor(amount);

    return message.reply(
      `✅ Added **${money(amount)}** ${db.currency} to <@${target.id}>.`
    );
  }

  /* LEADERBOARD */

  if (["lb", "leaderboard"].includes(command)) {
    const list = Object.entries(db.users)
      .sort((a, b) => b[1].cash - a[1].cash)
      .slice(0, 10);

    const text = list.length
      ? list
          .map(
            ([id, u], i) =>
              `**${i + 1}.** <@${id}> — **${money(
                u.cash
              )}** ${db.currency}`
          )
          .join("\n")
      : "No users yet.";

    return message.reply({
      embeds: [
        new EmbedBuilder()
          .setTitle("🏆 Leaderboard")
          .setDescription(text)
      ]
    });
  }

  /* GAMES */

  if (["bj", "blackjack"].includes(command)) {
    return blackjack(message, args, user);
  }

  if (["ht", "coinflip"].includes(command)) {
    return coinflip(message, args, user);
  }

  if (["hl", "higherlower"].includes(command)) {
    return higherLower(message, args, user);
  }

  if (
    ["cfight", "cockfight", "chickenfight"].includes(command)
  ) {
    return cockfight(message, args, user);
  }

  if (command === "mines") {
    return mines(message, args, user);
  }
});

/* =========================
   BLACKJACK
========================= */

async function blackjack(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const cards = [
    ["A", 11],
    ["2", 2],
    ["3", 3],
    ["4", 4],
    ["5", 5],
    ["6", 6],
    ["7", 7],
    ["8", 8],
    ["9", 9],
    ["10", 10],
    ["J", 10],
    ["Q", 10],
    ["K", 10]
  ];

  const suits = ["♠️", "♥️", "♦️", "♣️"];

  function draw() {
    const [value, number] =
      cards[random(0, cards.length - 1)];

    return {
      value,
      number,
      suit: suits[random(0, 3)]
    };
  }

  function handValue(hand) {
    let total = hand.reduce(
      (sum, card) => sum + card.number,
      0
    );

    let aces = hand.filter(
      (card) => card.value === "A"
    ).length;

    while (total > 21 && aces > 0) {
      total -= 10;
      aces--;
    }

    return total;
  }

  function handText(hand) {
    return hand
      .map((card) => `${card.value}${card.suit}`)
      .join(" ");
  }

  const player = [draw(), draw()];
  const dealer = [draw(), draw()];

  let totalBet = bet;
  let finished = false;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`bj_hit_${message.author.id}`)
      .setLabel("Hit")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`bj_stand_${message.author.id}`)
      .setLabel("Stand")
      .setStyle(ButtonStyle.Success),

    new ButtonBuilder()
      .setCustomId(`bj_double_${message.author.id}`)
      .setLabel("Double")
      .setStyle(ButtonStyle.Secondary)
  );

  function gameEmbed(showDealer = false) {
    return new EmbedBuilder()
      .setTitle("🃏 Blackjack")
      .setDescription(
        `**Your hand:** ${handText(player)} — **${handValue(
          player
        )}**\n` +
          `**Dealer:** ${
            showDealer
              ? `${handText(dealer)} — **${handValue(
                  dealer
                )}**`
              : `${handText([dealer[0]])} 🂠`
          }\n\n` +
          `Bet: **${money(totalBet)}** ${db.currency}`
      );
  }

  const gameMessage = await message.reply({
    embeds: [gameEmbed()],
    components: [row]
  });

  const collector =
    gameMessage.createMessageComponentCollector({
      time: 120000
    });

  async function finish(result, payout) {
    if (finished) return;

    finished = true;
    collector.stop();

    if (payout > 0) {
      user.cash += payout;
    }

    await gameMessage.edit({
      embeds: [
        new EmbedBuilder()
          .setTitle("🃏 Blackjack")
          .setDescription(
            `**Your hand:** ${handText(
              player
            )} — **${handValue(player)}**\n` +
              `**Dealer:** ${handText(
                dealer
              )} — **${handValue(dealer)}**\n\n` +
              `${result}` +
              (payout > 0
                ? `\nPayout: **${money(
                    payout
                  )}** ${db.currency}`
                : "")
          )
      ],
      components: [disabledRow(row)]
    });
  }

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (interaction.customId.includes("double")) {
      if (user.cash < bet) {
        return interaction.reply({
          content:
            "❌ You don't have enough money to double.",
          ephemeral: true
        });
      }

      user.cash -= bet;
      totalBet += bet;
      player.push(draw());

      await interaction.deferUpdate();

      if (handValue(player) > 21) {
        return finish("💥 You busted!", 0);
      }

      while (handValue(dealer) < 17) {
        dealer.push(draw());
      }

      const p = handValue(player);
      const d = handValue(dealer);

      if (d > 21 || p > d) {
        return finish(
          "🎉 You win!",
          totalBet * 2
        );
      }

      if (p === d) {
        return finish(
          "🤝 It's a tie!",
          totalBet
        );
      }

      return finish("❌ Dealer wins!", 0);
    }

    if (interaction.customId.includes("hit")) {
      player.push(draw());

      if (handValue(player) > 21) {
        await interaction.deferUpdate();
        return finish("💥 You busted!", 0);
      }

      return interaction.update({
        embeds: [gameEmbed()],
        components: [row]
      });
    }

    await interaction.deferUpdate();

    while (handValue(dealer) < 17) {
      dealer.push(draw());
    }

    const p = handValue(player);
    const d = handValue(dealer);

    if (d > 21 || p > d) {
      return finish("🎉 You win!", totalBet * 2);
    }

    if (p === d) {
      return finish("🤝 It's a tie!", totalBet);
    }

    return finish("❌ Dealer wins!", 0);
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    user.cash += totalBet;

    await gameMessage
      .edit({
        embeds: [
          new EmbedBuilder()
            .setTitle("🃏 Blackjack")
            .setDescription(
              `⏰ Timed out.\nReturned **${money(
                totalBet
              )}** ${db.currency}.`
            )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* =========================
   COINFLIP
========================= */

async function coinflip(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`cf_h_${message.author.id}`)
      .setLabel("Heads")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`cf_t_${message.author.id}`)
      .setLabel("Tails")
      .setStyle(ButtonStyle.Success)
  );

  const msg = await message.reply({
    embeds: [
      new EmbedBuilder()
        .setTitle("🪙 Coinflip")
        .setDescription(
          `Choose Heads or Tails.\n\nBet: **${money(
            bet
          )}** ${db.currency}`
        )
    ],
    components: [row]
  });

  const collector =
    msg.createMessageComponentCollector({
      time: 60000,
      max: 1
    });

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    const result = Math.random() < 0.5 ? "h" : "t";
    const win =
      interaction.customId.includes(`_${result}_`);

    if (win) {
      user.cash += bet * 2;
    }

    await interaction.update({
      embeds: [
        new EmbedBuilder()
          .setTitle("🪙 Coinflip")
          .setDescription(
            `${result === "h" ? "Heads" : "Tails"}!\n\n` +
              (win
                ? `🎉 Won **${money(
                    bet * 2
                  )}** ${db.currency}!`
                : `❌ Lost **${money(
                    bet
                  )}** ${db.currency}.`)
          )
      ],
      components: [disabledRow(row)]
    });
  });

  collector.on("end", async (collected) => {
    if (collected.size) return;

    user.cash += bet;

    await msg
      .edit({
        embeds: [
          new EmbedBuilder()
            .setTitle("🪙 Coinflip")
            .setDescription(
              `⏰ Timed out. Returned **${money(
                bet
              )}** ${db.currency}.`
            )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* =========================
   HIGHER LOWER
========================= */

async function higherLower(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const current = random(2, 99);

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`hl_hi_${message.author.id}`)
      .setLabel("Higher")
      .setStyle(ButtonStyle.Success),

    new ButtonBuilder()
      .setCustomId(`hl_lo_${message.author.id}`)
      .setLabel("Lower")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`hl_eq_${message.author.id}`)
      .setLabel("Same")
      .setStyle(ButtonStyle.Secondary)
  );

  const msg = await message.reply({
    embeds: [
      new EmbedBuilder()
        .setTitle("📈 Higher or Lower")
        .setDescription(
          `Current number: **${current}**\n\n` +
            `Higher / Lower = **1.5x**\n` +
            `Same = **25x**\n\n` +
            `Bet: **${money(bet)}** ${db.currency}`
        )
    ],
    components: [row]
  });

  const collector =
    msg.createMessageComponentCollector({
      time: 60000,
      max: 1
    });

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    const next = random(1, 100);

    const choice = interaction.customId.includes("_hi_")
      ? "hi"
      : interaction.customId.includes("_lo_")
      ? "lo"
      : "eq";

    const win =
      (choice === "hi" && next > current) ||
      (choice === "lo" && next < current) ||
      (choice === "eq" && next === current);

    const payout = win
      ? Math.floor(bet * (choice === "eq" ? 25 : 1.5))
      : 0;

    if (payout) {
      user.cash += payout;
    }

    await interaction.update({
      embeds: [
        new EmbedBuilder()
          .setTitle("📈 Higher or Lower")
          .setDescription(
            `Previous: **${current}**\n` +
              `New: **${next}**\n\n` +
              (win
                ? `🎉 Won **${money(
                    payout
                  )}** ${db.currency}!`
                : `❌ Lost **${money(
                    bet
                  )}** ${db.currency}.`)
          )
      ],
      components: [disabledRow(row)]
    });
  });

  collector.on("end", async (collected) => {
    if (collected.size) return;

    user.cash += bet;

    await msg
      .edit({
        embeds: [
          new EmbedBuilder()
            .setTitle("📈 Higher or Lower")
            .setDescription(
              `⏰ Timed out. Returned **${money(
                bet
              )}** ${db.currency}.`
            )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* =========================
   COCKFIGHT
========================= */

async function cockfight(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const yours = random(55, 82);
  const enemy = random(55, 82);
  const win = yours > enemy;

  if (win) {
    user.cash += bet * 2;
  }

  return message.reply({
    embeds: [
      new EmbedBuilder()
        .setTitle("🐔 Cockfight")
        .setDescription(
          `Your chicken: **${yours}%**\n` +
            `Enemy chicken: **${enemy}%**\n\n` +
            (win
              ? `🎉 Your chicken won!\nReceived **${money(
                  bet * 2
                )}** ${db.currency}.`
              : `❌ Your chicken lost!\nLost **${money(
                  bet
                )}** ${db.currency}.`)
        )
    ]
  });
}

/* =========================
   MINES
========================= */

async function mines(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const bomb = random(0, 8);
  const safe = new Set();

  let finished = false;

  const multipliers = [
    1.1,
    1.2,
    1.4,
    1.6,
    2,
    2.6,
    3.6,
    8
  ];

  function multiplier() {
    return (
      multipliers[Math.max(0, safe.size - 1)] || 8
    );
  }

  function rows() {
    const result = [];

    for (let r = 0; r < 3; r++) {
      const buttons = [];

      for (let c = 0; c < 3; c++) {
        const index = r * 3 + c;

        buttons.push(
          new ButtonBuilder()
            .setCustomId(
              `mine_${message.author.id}_${index}`
            )
            .setLabel(safe.has(index) ? "💎" : "💠")
            .setStyle(
              safe.has(index)
                ? ButtonStyle.Success
                : ButtonStyle.Secondary
            )
            .setDisabled(safe.has(index))
        );
      }

      result.push(
        new ActionRowBuilder().addComponents(buttons)
      );
    }

    result.push(
      new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId(
            `mine_cash_${message.author.id}`
          )
          .setLabel("💰 Cashout")
          .setStyle(ButtonStyle.Success)
          .setDisabled(safe.size === 0)
      )
    );

    return result;
  }

  function embed() {
    return new EmbedBuilder()
      .setTitle("💣 Mines")
      .setDescription(
        `Pick a tile and avoid the bomb.\n\n` +
          `💎 Safe tiles: **${safe.size}/8**\n` +
          `Multiplier: **${multiplier()}x**\n` +
          `Current value: **${money(
            bet * multiplier()
          )}** ${db.currency}\n\n` +
          `Bet: **${money(bet)}** ${db.currency}`
      );
  }

  const msg = await message.reply({
    embeds: [embed()],
    components: rows()
  });

  const collector =
    msg.createMessageComponentCollector({
      time: 120000
    });

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (finished) return;

    if (interaction.customId.includes("mine_cash")) {
      if (!safe.size) {
        return interaction.reply({
          content: "❌ Reveal a tile first.",
          ephemeral: true
        });
      }

      finished = true;
      collector.stop();

      const payout = Math.floor(
        bet * multiplier()
      );

      user.cash += payout;

      return interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle("💣 Mines")
            .setDescription(
              `💰 Cashed out!\n\n` +
                `Payout: **${money(
                  payout
                )}** ${db.currency}.`
            )
        ],
        components: rows().map(disabledRow)
      });
    }

    const index = Number(
      interaction.customId.split("_").pop()
    );

    if (index === bomb) {
      finished = true;
      collector.stop();

      const endRows = [];

      for (let r = 0; r < 3; r++) {
        const buttons = [];

        for (let c = 0; c < 3; c++) {
          const i = r * 3 + c;

          buttons.push(
            new ButtonBuilder()
              .setCustomId(
                `mine_end_${message.author.id}_${i}`
              )
              .setLabel(i === bomb ? "💣" : "💠")
              .setStyle(
                i === bomb
                  ? ButtonStyle.Danger
                  : ButtonStyle.Secondary
              )
              .setDisabled(true)
          );
        }

        endRows.push(
          new ActionRowBuilder().addComponents(buttons)
        );
      }

      return interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle("💣 Mines")
            .setDescription(
              `💥 BOOM!\n\nYou lost **${money(
                bet
              )}** ${db.currency}.`
            )
        ],
        components: endRows
      });
    }

    safe.add(index);

    if (safe.size === 8) {
      finished = true;
      collector.stop();

      const payout = bet * 8;
      user.cash += payout;

      return interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle("💣 Mines")
            .setDescription(
              `💎 All safe tiles!\n\n` +
                `Payout: **${money(
                  payout
                )}** ${db.currency}.`
            )
        ],
        components: rows().map(disabledRow)
      });
    }

    return interaction.update({
      embeds: [embed()],
      components: rows()
    });
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    user.cash += bet;

    await msg
      .edit({
        embeds: [
          new EmbedBuilder()
            .setTitle("💣 Mines")
            .setDescription(
              `⏰ Timed out.\nReturned **${money(
                bet
              )}** ${db.currency}.`
            )
        ],
        components: rows().map(disabledRow)
      })
      .catch(() => {});
  });
}

/* =========================
   LOGIN
========================= */

if (!process.env.DISCORD_TOKEN) {
  console.error("❌ DISCORD_TOKEN is missing.");
} else {
  client.login(process.env.DISCORD_TOKEN).catch((error) => {
    console.error("❌ Discord login failed:");
    console.error(error);
  });
}