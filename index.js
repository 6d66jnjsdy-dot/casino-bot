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
  currency: "💸",
  casinoRole: null
};

function getUser(id) {
  if (!db.users[id]) {
    db.users[id] = {
      cash: 0
    };
  }

  return db.users[id];
}

function formatMoney(amount) {
  return Math.floor(amount).toLocaleString();
}

function getBet(message, args) {
  const bet = Number(args[0]);

  if (!Number.isFinite(bet) || bet < MIN_BET) {
    message.reply(`❌ Minimum bet is **${MIN_BET}** ${db.currency}.`);
    return null;
  }

  const user = getUser(message.author.id);

  if (bet > user.cash) {
    message.reply(`❌ You don't have enough money.`);
    return null;
  }

  return Math.floor(bet);
}

function spend(user, amount) {
  user.cash -= amount;
}

function add(user, amount) {
  user.cash += amount;
}

function random(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function disabledRow(buttons) {
  return new ActionRowBuilder().addComponents(
    buttons.map((b) => ButtonBuilder.from(b).setDisabled(true))
  );
}

/* =========================
   READY
========================= */

client.once("ready", () => {
  console.log(`Logged in as ${client.user.tag}`);
});

/* =========================
   MESSAGE COMMANDS
========================= */

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;
  if (!message.content.startsWith(PREFIX)) return;

  const args = message.content.slice(PREFIX.length).trim().split(/\s+/);
  const command = (args.shift() || "").toLowerCase();

  const user = getUser(message.author.id);

  /* =========================
     BALANCE
  ========================= */

  if (["bal", "balance"].includes(command)) {
    const embed = new EmbedBuilder()
      .setTitle("💰 Balance")
      .setDescription(
        `You have **${formatMoney(user.cash)}** ${db.currency}`
      );

    return message.reply({ embeds: [embed] });
  }

  /* =========================
     CURRENCY
  ========================= */

  if (command === "currency") {
    return message.reply(`Current currency: ${db.currency}`);
  }

  /* =========================
     ADD MONEY
  ========================= */

  if (command === "addmoney") {
    if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
      return message.reply("❌ You need Administrator permission.");
    }

    let target = message.mentions.users.first();
    let amount;

    if (target) {
      amount = Number(args[1]);
    } else {
      const id = args[0];
      amount = Number(args[1]);

      if (id && /^\d{17,20}$/.test(id)) {
        try {
          target = await client.users.fetch(id);
        } catch {
          target = null;
        }
      }
    }

    if (!target || !Number.isFinite(amount) || amount <= 0) {
      return message.reply(
        `❌ Usage: \`$addmoney @user 1000\``
      );
    }

    const targetUser = getUser(target.id);
    add(targetUser, Math.floor(amount));

    return message.reply(
      `✅ Added **${formatMoney(amount)}** ${db.currency} to <@${target.id}>.`
    );
  }

  /* =========================
     DEPOSIT
  ========================= */

  if (["dep", "deposit"].includes(command)) {
    const amount = Number(args[0]);

    if (!Number.isFinite(amount) || amount <= 0) {
      return message.reply("❌ Enter a valid amount.");
    }

    return message.reply(
      `💰 Deposit system is currently using your casino balance directly.`
    );
  }

  /* =========================
     WITHDRAW
  ========================= */

  if (["with", "withdraw"].includes(command)) {
    const amount = Number(args[0]);

    if (!Number.isFinite(amount) || amount <= 0) {
      return message.reply("❌ Enter a valid amount.");
    }

    if (amount > user.cash) {
      return message.reply("❌ You don't have enough money.");
    }

    user.cash -= Math.floor(amount);

    return message.reply(
      `💸 Withdrawn **${formatMoney(amount)}** ${db.currency}.`
    );
  }

  /* =========================
     LEADERBOARD
  ========================= */

  if (["lb", "leaderboard"].includes(command)) {
    const list = Object.entries(db.users)
      .sort((a, b) => b[1].cash - a[1].cash)
      .slice(0, 10);

    if (!list.length) {
      return message.reply("No users yet.");
    }

    let text = "";

    for (let i = 0; i < list.length; i++) {
      text += `**${i + 1}.** <@${list[i][0]}> — **${formatMoney(
        list[i][1].cash
      )}** ${db.currency}\n`;
    }

    const embed = new EmbedBuilder()
      .setTitle("🏆 Leaderboard")
      .setDescription(text);

    return message.reply({ embeds: [embed] });
  }

  /* =========================
     BLACKJACK
  ========================= */

  if (["bj", "blackjack"].includes(command)) {
    const bet = getBet(message, args);
    if (bet === null) return;

    spend(user, bet);

    const suits = ["♠️", "♥️", "♦️", "♣️"];
    const values = [
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

    function card() {
      const [value, number] =
        values[random(0, values.length - 1)];

      return {
        value,
        number,
        suit: suits[random(0, suits.length - 1)]
      };
    }

    function handValue(hand) {
      let total = hand.reduce((sum, c) => sum + c.number, 0);
      let aces = hand.filter((c) => c.value === "A").length;

      while (total > 21 && aces > 0) {
        total -= 10;
        aces--;
      }

      return total;
    }

    const player = [card(), card()];
    const dealer = [card(), card()];

    function handText(hand) {
      return hand.map((c) => `${c.value}${c.suit}`).join(" ");
    }

    function blackjackEmbed(showDealer = false) {
      const pValue = handValue(player);
      const dealerText = showDealer
        ? `${handText(dealer)} — **${handValue(dealer)}**`
        : `${dealer[0].value}${dealer[0].suit} 🂠`;

      return new EmbedBuilder()
        .setTitle("🃏 Blackjack")
        .setDescription(
          `**Your hand:** ${handText(player)} — **${pValue}**\n` +
          `**Dealer:** ${dealerText}\n\n` +
          `Bet: **${formatMoney(bet)}** ${db.currency}`
        );
    }

    const buttons = new ActionRowBuilder().addComponents(
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

    const gameMessage = await message.reply({
      embeds: [blackjackEmbed()],
      components: [buttons]
    });

    const collector = gameMessage.createMessageComponentCollector({
      time: 120000
    });

    let totalBet = bet;
    let finished = false;

    async function finish(result, payout = 0) {
      if (finished) return;
      finished = true;

      if (payout > 0) {
        add(user, payout);
      }

      collector.stop();

      const finalEmbed = blackjackEmbed(true);

      finalEmbed.setDescription(
        `**Your hand:** ${handText(player)} — **${handValue(player)}**\n` +
        `**Dealer:** ${handText(dealer)} — **${handValue(dealer)}**\n\n` +
        `${result}\n\n` +
        `Bet: **${formatMoney(totalBet)}** ${db.currency}` +
        (payout > 0
          ? `\nPayout: **${formatMoney(payout)}** ${db.currency}`
          : "")
      );

      await gameMessage.edit({
        embeds: [finalEmbed],
        components: [disabledRow(buttons.components)]
      });
    }

    collector.on("collect", async (interaction) => {
      if (interaction.user.id !== message.author.id) {
        return interaction.reply({
          content: "❌ This isn't your game.",
          ephemeral: true
        });
      }

      if (finished) return;

      if (interaction.customId.startsWith("bj_hit_")) {
        player.push(card());

        const value = handValue(player);

        if (value > 21) {
          await interaction.deferUpdate();
          return finish("💥 You busted!", 0);
        }

        if (value === 21) {
          await interaction.deferUpdate();

          while (handValue(dealer) < 17) {
            dealer.push(card());
          }

          const d = handValue(dealer);

          if (d > 21 || value > d) {
            return finish(
              "🎉 You win!",
              totalBet * 2
            );
          }

          if (value === d) {
            return finish(
              "🤝 It's a tie!",
              totalBet
            );
          }

          return finish("❌ Dealer wins!", 0);
        }

        await interaction.update({
          embeds: [blackjackEmbed()],
          components: [buttons]
        });
      }

      if (interaction.customId.startsWith("bj_double_")) {
        if (user.cash < bet) {
          return interaction.reply({
            content: "❌ You don't have enough money to double.",
            ephemeral: true
          });
        }

        spend(user, bet);
        totalBet += bet;
        player.push(card());

        await interaction.deferUpdate();

        if (handValue(player) > 21) {
          return finish("💥 You busted!", 0);
        }

        while (handValue(dealer) < 17) {
          dealer.push(card());
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
      }

      if (interaction.customId.startsWith("bj_stand_")) {
        await interaction.deferUpdate();

        while (handValue(dealer) < 17) {
          dealer.push(card());
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
      }
    });

    collector.on("end", async () => {
      if (!finished) {
        finished = true;
        add(user, totalBet);

        await gameMessage.edit({
          embeds: [
            new EmbedBuilder()
              .setTitle("🃏 Blackjack")
              .setDescription(
                `⏰ Game timed out.\n\nReturned **${formatMoney(
                  totalBet
                )}** ${db.currency}.`
              )
          ],
          components: [disabledRow(buttons.components)]
        }).catch(() => {});
      }
    });

    return;
  }

  /* =========================
     COINFLIP
  ========================= */

  if (["cf", "coinflip", "ht"].includes(command)) {
    const bet = getBet(message, args);
    if (bet === null) return;

    spend(user, bet);

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`cf_heads_${message.author.id}`)
        .setLabel("Heads")
        .setStyle(ButtonStyle.Primary),

      new ButtonBuilder()
        .setCustomId(`cf_tails_${message.author.id}`)
        .setLabel("Tails")
        .setStyle(ButtonStyle.Success)
    );

    const gameMessage = await message.reply({
      embeds: [
        new EmbedBuilder()
          .setTitle("🪙 Coinflip")
          .setDescription(
            `Choose Heads or Tails.\n\nBet: **${formatMoney(
              bet
            )}** ${db.currency}`
          )
      ],
      components: [row]
    });

    const collector = gameMessage.createMessageComponentCollector({
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

      const result =
        Math.random() < 0.5 ? "heads" : "tails";

      const choice = interaction.customId.includes("heads")
        ? "heads"
        : "tails";

      const win = choice === result;

      if (win) add(user, bet * 2);

      await interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle("🪙 Coinflip")
            .setDescription(
              `The coin landed on **${result.toUpperCase()}**.\n\n` +
              (win
                ? `🎉 You won **${formatMoney(
                    bet * 2
                  )}** ${db.currency}!`
                : `❌ You lost **${formatMoney(
                    bet
                  )}** ${db.currency}.`)
            )
        ],
        components: [disabledRow(row.components)]
      });
    });

    collector.on("end", async (collected) => {
      if (collected.size === 0) {
        add(user, bet);

        await gameMessage.edit({
          embeds: [
            new EmbedBuilder()
              .setTitle("🪙 Coinflip")
              .setDescription(
                `⏰ Timed out.\nReturned **${formatMoney(
                  bet
                )}** ${db.currency}.`
              )
          ],
          components: [disabledRow(row.components)]
        }).catch(() => {});
      }
    });

    return;
  }

  /* =========================
     HIGHER / LOWER
  ========================= */

  if (["hl", "higherlower"].includes(command)) {
    const bet = getBet(message, args);
    if (bet === null) return;

    spend(user, bet);

    const current = random(2, 99);

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`hl_higher_${message.author.id}`)
        .setLabel("Higher")
        .setStyle(ButtonStyle.Success),

      new ButtonBuilder()
        .setCustomId(`hl_lower_${message.author.id}`)
        .setLabel("Lower")
        .setStyle(ButtonStyle.Primary),

      new ButtonBuilder()
        .setCustomId(`hl_same_${message.author.id}`)
        .setLabel("Same")
        .setStyle(ButtonStyle.Secondary)
    );

    const gameMessage = await message.reply({
      embeds: [
        new EmbedBuilder()
          .setTitle("📈 Higher or Lower")
          .setDescription(
            `Current number: **${current}**\n\n` +
            `Higher / Lower = **1.5x**\n` +
            `Same = **25x**\n\n` +
            `Bet: **${formatMoney(bet)}** ${db.currency}`
          )
      ],
      components: [row]
    });

    const collector = gameMessage.createMessageComponentCollector({
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

      const choice = interaction.customId.includes("higher")
        ? "higher"
        : interaction.customId.includes("lower")
        ? "lower"
        : "same";

      let win = false;
      let multiplier = 0;

      if (choice === "higher" && next > current) {
        win = true;
        multiplier = 1.5;
      }

      if (choice === "lower" && next < current) {
        win = true;
        multiplier = 1.5;
      }

      if (choice === "same" && next === current) {
        win = true;
        multiplier = 25;
      }

      const payout = win ? Math.floor(bet * multiplier) : 0;

      if (payout) add(user, payout);

      await interaction.update({
        embeds: [
          new EmbedBuilder()
            .setTitle("📈 Higher or Lower")
            .setDescription(
              `Previous: **${current}**\n` +
              `New number: **${next}**\n\n` +
              (win
                ? `🎉 You won **${formatMoney(
                    payout
                  )}** ${db.currency}!`
                : `❌ You lost **${formatMoney(
                    bet
                  )}** ${db.currency}.`)
            )
        ],
        components: [disabledRow(row.components)]
      });
    });

    collector.on("end", async (collected) => {
      if (collected.size === 0) {
        add(user, bet);

        await gameMessage.edit({
          embeds: [
            new EmbedBuilder()
              .setTitle("📈 Higher or Lower")
              .setDescription(
                `⏰ Timed out.\nReturned **${formatMoney(
                  bet
                )}** ${db.currency}.`
              )
          ],
          components: [disabledRow(row.components)]
        }).catch(() => {});
      }
    });

    return;
  }

  /* =========================
     COCKFIGHT
  ========================= */

  if (["cfight", "cockfight", "chickenfight"].includes(command)) {
    const bet = getBet(message, args);
    if (bet === null) return;

    spend(user, bet);

    const yourPower = random(55, 82);
    const enemyPower = random(55, 82);

    const win = yourPower > enemyPower;

    if (win) add(user, bet * 2);

    const embed = new EmbedBuilder()
      .setTitle("🐔 Cockfight")
      .setDescription(
        `Your chicken: **${yourPower}%**\n` +
        `Enemy chicken: **${enemyPower}%**\n\n` +
        (win
          ? `🎉 Your chicken won!\nYou received **${formatMoney(
              bet * 2
            )}** ${db.currency}.`
          : `❌ Your chicken lost!\nYou lost **${formatMoney(
              bet
            )}** ${db.currency}.`)
      );

    return message.reply({ embeds: [embed] });
  }

  /* =========================
     MINES
  ========================= */

  if (command === "mines") {
    const bet = getBet(message, args);
    if (bet === null) return;

    spend(user, bet);

    const bomb = random(0, 8);
    const revealed = new Set();
    let finished = false;

    const multipliers = [
      1.1,
      1.2,
      1.4,
      1.6,
      2.0,
      2.6,
      3.6,
      8.0
    ];

    function buildRows() {
      const rows = [];

      for (let r = 0; r < 3; r++) {
        const buttons = [];

        for (let c = 0; c < 3; c++) {
          const index = r * 3 + c;

          let label = "💠";
          let style = ButtonStyle.Secondary;

          if (revealed.has(index)) {
            label = "💎";
            style = ButtonStyle.Success;
          }

          buttons.push(
            new ButtonBuilder()
              .setCustomId(`mine_${message.author.id}_${index}`)
              .setLabel(label)
              .setStyle(style)
              .setDisabled(revealed.has(index))
          );
        }

        rows.push(new ActionRowBuilder().addComponents(buttons));
      }

      const cashout = new ButtonBuilder()
        .setCustomId(`mine_cashout_${message.author.id}`)
        .setLabel("💰 Cashout")
        .setStyle(ButtonStyle.Success)
        .setDisabled(revealed.size === 0);

      rows.push(new ActionRowBuilder().addComponents(cashout));

      return rows;
    }

    function currentMultiplier() {
      return multipliers[Math.max(0, revealed.size - 1)] || 8;
    }

    function embed() {
      const multi = currentMultiplier();

      return new EmbedBuilder()
        .setTitle("💣 Mines")
        .setDescription(
          `Pick a tile and avoid the bomb.\n\n` +
          `💎 Safe tiles: **${revealed.size}/8**\n` +
          `Multiplier: **${multi}x**\n` +
          `Current value: **${formatMoney(
            bet * multi
          )}** ${db.currency}\n\n` +
          `Bet: **${formatMoney(bet)}** ${db.currency}`
        );
    }

    const gameMessage = await message.reply({
      embeds: [embed()],
      components: buildRows()
    });

    const collector = gameMessage.createMessageComponentCollector({
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

      if (interaction.customId.includes("cashout")) {
        if (revealed.size === 0) {
          return interaction.reply({
            content: "❌ Reveal at least one tile first.",
            ephemeral: true
          });
        }

        finished = true;

        const payout = Math.floor(
          bet * currentMultiplier()
        );

        add(user, payout);
        collector.stop();

        return interaction.update({
          embeds: [
            new EmbedBuilder()
              .setTitle("💣 Mines")
              .setDescription(
                `💰 Cashed out!\n\n` +
                `Safe tiles: **${revealed.size}/8**\n` +
                `Multiplier: **${currentMultiplier()}x**\n` +
                `Payout: **${formatMoney(
                  payout
                )}** ${db.currency}`
              )
          ],
          components: buildRows().map((row) =>
            disabledRow(row.components)
          )
        });
      }

      const index = Number(
        interaction.customId.split("_").pop()
      );

      if (revealed.has(index)) {
        return interaction.deferUpdate();
      }

      if (index === bomb) {
        finished = true;
        collector.stop();

        const finalRows = [];

        for (let r = 0; r < 3; r++) {
          const buttons = [];

          for (let c = 0; c < 3; c++) {
            const i = r * 3 + c;

            buttons.push(
              new ButtonBuilder()
                .setCustomId(`mine_end_${message.author.id}_${i}`)
                .setLabel(i === bomb ? "💣" : "💠")
                .setStyle(
                  i === bomb
                    ? ButtonStyle.Danger
                    : ButtonStyle.Secondary
                )
                .setDisabled(true)
            );
          }

          finalRows.push(
            new ActionRowBuilder().addComponents(buttons)
          );
        }

        finalRows.push(
          new ActionRowBuilder().addComponents(
            new ButtonBuilder()
              .setCustomId(`mine_end_cash_${message.author.id}`)
              .setLabel("Game Over")
              .setStyle(ButtonStyle.Danger)
              .setDisabled(true)
          )
        );

        return interaction.update({
          embeds: [
            new EmbedBuilder()
              .setTitle("💣 Mines")
              .setDescription(
                `💥 BOOM!\n\nYou hit the bomb and lost **${formatMoney(
                  bet
                )}** ${db.currency}.`
              )
          ],
          components: finalRows
        });
      }

      revealed.add(index);

      if (revealed.size === 8) {
        finished = true;
        collector.stop();

        const payout = bet * 8;
        add(user, payout);

        return interaction.update({
          embeds: [
            new EmbedBuilder()
              .setTitle("💣 Mines")
              .setDescription(
                `💎 You cleared every safe tile!\n\n` +
                `🎉 Payout: **${formatMoney(
                  payout
                )}** ${db.currency}.`
              )
          ],
          components: buildRows().map((row) =>
            disabledRow(row.components)
          )
        });
      }

      await interaction.update({
        embeds: [embed()],
        components: buildRows()
      });
    });

    collector.on("end", async () => {
      if (!finished) {
        finished = true;
        add(user, bet);

        await gameMessage.edit({
          embeds: [
            new EmbedBuilder()
              .setTitle("💣 Mines")
              .setDescription(
                `⏰ Game timed out.\nReturned **${formatMoney(
                  bet
                )}** ${db.currency}.`
              )
          ],
          components: buildRows().map((row) =>
            disabledRow(row.components)
          )
        }).catch(() => {});
      }
    });

    return;
  }
});

/* =========================
   TOKEN CHECK
========================= */

if (!process.env.DISCORD_TOKEN) {
  console.error("❌ DISCORD_TOKEN is missing.");
  process.exit(1);
}

client.login(process.env.DISCORD_TOKEN).catch((err) => {
  console.error("❌ Discord login failed:");
  console.error(err);
  process.exit(1);
});