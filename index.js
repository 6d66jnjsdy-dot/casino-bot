/* ============================================================
   CASINO BOT
   A Discord economy / casino bot built with discord.js v14.
   All data is stored in-memory and persisted to data.json so
   balances survive restarts.
   ============================================================ */

const fs = require("fs");
const path = require("path");
const express = require("express");
const {
  Client,
  GatewayIntentBits,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  PermissionFlagsBits
} = require("discord.js");

/* ============================================================
   KEEP-ALIVE WEB SERVER (for Render / Railway / etc.)
   ============================================================ */

const app = express();
const PORT = process.env.PORT || 10000;

app.get("/", (req, res) => {
  res.send("Casino Bot is Online 24/7!");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Web server running on port ${PORT}`);
});

/* ============================================================
   DISCORD CLIENT
   ============================================================ */

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

const PREFIX = "$";
const MIN_BET = 175;

const COLOR_WIN = 0x57f287;
const COLOR_LOSE = 0xed4245;
const COLOR_INFO = 0x5865f2;
const COLOR_NEUTRAL = 0x2b2d31;

/* ============================================================
   DATA STORE (persisted to data.json)
   ============================================================ */

const DATA_FILE = path.join(__dirname, "data.json");

let db = {
  currency: "💸",
  casinoRoleId: null,
  users: {}
};

function loadData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const raw = fs.readFileSync(DATA_FILE, "utf8");
      const parsed = JSON.parse(raw);
      db = Object.assign(
        { currency: "💸", casinoRoleId: null, users: {} },
        parsed
      );
    }
  } catch (error) {
    console.error("Failed to load data.json:", error);
  }
}

let saveQueued = false;

function saveData() {
  // Debounce writes slightly so rapid actions don't hammer the disk.
  if (saveQueued) return;
  saveQueued = true;

  setImmediate(() => {
    saveQueued = false;

    try {
      fs.writeFileSync(DATA_FILE, JSON.stringify(db, null, 2));
    } catch (error) {
      console.error("Failed to save data.json:", error);
    }
  });
}

loadData();

/* ============================================================
   HELPERS
   ============================================================ */

function getUser(id) {
  if (!db.users[id]) {
    db.users[id] = { cash: 0, bank: 0, cooldowns: {} };
  }

  if (db.users[id].cooldowns === undefined) {
    db.users[id].cooldowns = {};
  }

  return db.users[id];
}

function money(amount) {
  return Math.floor(amount).toLocaleString("en-US");
}

function random(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min, max) {
  return Math.random() * (max - min) + min;
}

function weightedPick(entries) {
  const total = entries.reduce((sum, e) => sum + e.weight, 0);
  let roll = Math.random() * total;

  for (const entry of entries) {
    if (roll < entry.weight) return entry;
    roll -= entry.weight;
  }

  return entries[entries.length - 1];
}

function shuffle(array) {
  const copy = [...array];

  for (let i = copy.length - 1; i > 0; i--) {
    const j = random(0, i);
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }

  return copy;
}

function hasCasinoAccess(member) {
  if (!member) return false;
  if (member.permissions.has(PermissionFlagsBits.Administrator)) return true;

  if (db.casinoRoleId && member.roles.cache.has(db.casinoRoleId)) {
    return true;
  }

  return false;
}

function embed(description, color = COLOR_NEUTRAL, title = null) {
  const e = new EmbedBuilder().setDescription(description).setColor(color);
  if (title) e.setTitle(title);
  return e;
}

function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map((component) =>
      ButtonBuilder.from(component).setDisabled(true)
    )
  );
}

function validBet(message, args) {
  const user = getUser(message.author.id);
  const bet =
    (args[0] || "").toLowerCase() === "all" ? user.cash : Number(args[0]);

  if (!Number.isFinite(bet) || bet < MIN_BET) {
    message.reply({
      embeds: [
        embed(
          `❌ Minimum bet is **${money(MIN_BET)}** ${db.currency}.`,
          COLOR_LOSE
        )
      ]
    });
    return null;
  }

  if (bet > user.cash) {
    message.reply({
      embeds: [
        embed(
          `❌ You don't have enough cash on hand. (You have **${money(
            user.cash
          )}** ${db.currency} outside your bank.)`,
          COLOR_LOSE
        )
      ]
    });
    return null;
  }

  return Math.floor(bet);
}

function onCooldown(user, key, cooldownMs) {
  const last = user.cooldowns[key] || 0;
  const remaining = last + cooldownMs - Date.now();
  return remaining > 0 ? remaining : 0;
}

function formatDuration(ms) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

/* ============================================================
   READY
   ============================================================ */

client.once("ready", () => {
  console.log(`Logged in as ${client.user.tag}`);
});

/* ============================================================
   MESSAGE ROUTER
   ============================================================ */

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;
  if (!message.content.startsWith(PREFIX)) return;

  const args = message.content.slice(PREFIX.length).trim().split(/\s+/);
  const command = (args.shift() || "").toLowerCase();
  const user = getUser(message.author.id);

  try {
    /* ---------- HELP ---------- */

    if (command === "help") {
      return message.reply({
        embeds: [
          embed(
            [
              "**💰 Economy**",
              "`$work` — earn cash (4 min cooldown)",
              "`$crime` — risk it for more cash (4 min cooldown)",
              "`$rob @user` — try to steal cash from someone (8 min cooldown)",
              "`$bal [@user]` — check a balance",
              "`$deposit`/`$dep` and `$withdraw`/`$with` `<amount|all>` — move money to/from your bank",
              "`$pay @user <amount|all>` — send cash to another player",
              "`$lb` / `$top` — richest players",
              "`$top cash` — players with the most cash out on hand",
              "",
              "**🎰 Games** (minimum bet: " +
                money(MIN_BET) +
                " " +
                db.currency +
                ")",
              "`$bj <amount>` — Blackjack",
              "`$cf <amount>` — Cockfight",
              "`$hl <amount>` — Higher or Lower",
              "`$ht <amount>` — Coinflip",
              "`$mines <amount>` — Mines (3x3, 1 bomb)",
              "`$mt <amount>` — Money Tower",
              "`$gm <amount>` — Goldmine",
              "`$slots <amount>` — Slot Machine",
              "`$roulette <amount> <color/number>` — Roulette",
              "`$dice <amount> <over/under/seven>` — Dice",
              "`$wheel <amount>` — Wheel of Fortune",
              "`$crash <amount>` — Crash",
              "`$info` — full rules & payouts for every game",
              "(any game accepts `all` instead of an amount to bet everything)",
              "",
              "**🛠️ Admin / Casino Role**",
              "`$addmoney cash/bank @user <amount>` — add funds",
              "`$currency <emoji>` — change the server currency emoji",
              "`$casinorole @role` — grant a role full casino-admin access (Administrator only)"
            ].join("\n"),
            COLOR_INFO,
            "🎲 Casino Bot — Commands"
          )
        ]
      });
    }

    /* ---------- BALANCE ---------- */

    if (["bal", "balance"].includes(command)) {
      const target = message.mentions.users.first() || message.author;
      const targetUser = getUser(target.id);
      const total = targetUser.cash + targetUser.bank;

      return message.reply({
        embeds: [
          embed(
            `**${target.username}**'s balance\n\n` +
              `💵 Cash (outside): **${money(targetUser.cash)}** ${
                db.currency
              }\n` +
              `🏦 Bank (inside): **${money(targetUser.bank)}** ${
                db.currency
              }\n` +
              `📊 Total: **${money(total)}** ${db.currency}`,
            COLOR_INFO
          )
        ]
      });
    }

    /* ---------- DEPOSIT / WITHDRAW ---------- */

    if (["deposit", "dep"].includes(command)) {
      const amount = (args[0] || "").toLowerCase() === "all" ? user.cash : Number(args[0]);

      if (!Number.isFinite(amount) || amount <= 0 || amount > user.cash) {
        return message.reply({
          embeds: [
            embed(
              "❌ Usage: `$deposit <amount>` (or `$deposit all`)",
              COLOR_LOSE
            )
          ]
        });
      }

      user.cash -= Math.floor(amount);
      user.bank += Math.floor(amount);
      saveData();

      return message.reply({
        embeds: [
          embed(
            `Successfully deposited **${money(
              amount
            )}** ${db.currency} to your bank account.`,
            COLOR_WIN
          )
        ]
      });
    }

    if (["withdraw", "with", "wd"].includes(command)) {
      const amount = (args[0] || "").toLowerCase() === "all" ? user.bank : Number(args[0]);

      if (!Number.isFinite(amount) || amount <= 0 || amount > user.bank) {
        return message.reply({
          embeds: [
            embed(
              "❌ Usage: `$withdraw <amount>` (or `$withdraw all`)",
              COLOR_LOSE
            )
          ]
        });
      }

      user.bank -= Math.floor(amount);
      user.cash += Math.floor(amount);
      saveData();

      return message.reply({
        embeds: [
          embed(
            `Successfully withdrew **${money(
              amount
            )}** ${db.currency} from your bank account.`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- PAY ---------- */

    if (command === "pay") {
      const target = message.mentions.users.first();
      const amount =
        (args[1] || "").toLowerCase() === "all" ? user.cash : Number(args[1]);

      if (!target || target.id === message.author.id) {
        return message.reply({
          embeds: [
            embed("❌ Usage: `$pay @user <amount>`", COLOR_LOSE)
          ]
        });
      }

      if (!Number.isFinite(amount) || amount <= 0 || amount > user.cash) {
        return message.reply({
          embeds: [
            embed(
              "❌ Enter a valid amount you actually have in cash (or use `all`).",
              COLOR_LOSE
            )
          ]
        });
      }

      const flooredAmount = Math.floor(amount);
      const targetUser = getUser(target.id);

      user.cash -= flooredAmount;
      targetUser.cash += flooredAmount;
      saveData();

      return message.reply({
        embeds: [
          embed(
            `✅ Sent **${money(
              flooredAmount
            )}** ${db.currency} to <@${target.id}>.`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- CURRENCY ---------- */

    if (command === "currency") {
      if (args.length === 0) {
        return message.reply({
          embeds: [
            embed(`Current currency: ${db.currency}`, COLOR_INFO)
          ]
        });
      }

      if (!hasCasinoAccess(message.member)) {
        return message.reply({
          embeds: [
            embed(
              "❌ You don't have permission to change the currency.",
              COLOR_LOSE
            )
          ]
        });
      }

      const newCurrency = args[0];
      db.currency = newCurrency;
      saveData();

      return message.reply({
        embeds: [
          embed(
            `✅ The server currency is now ${newCurrency}`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- CASINO ROLE ---------- */

    if (command === "casinorole") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) {
        return message.reply({
          embeds: [
            embed("❌ You need Administrator permission.", COLOR_LOSE)
          ]
        });
      }

      const role = message.mentions.roles.first();

      if (args[0] === "remove") {
        db.casinoRoleId = null;
        saveData();

        return message.reply({
          embeds: [
            embed("✅ Casino role access has been removed.", COLOR_WIN)
          ]
        });
      }

      if (!role) {
        return message.reply({
          embeds: [
            embed(
              "❌ Usage: `$casinorole @role` (or `$casinorole remove`)",
              COLOR_LOSE
            )
          ]
        });
      }

      db.casinoRoleId = role.id;
      saveData();

      return message.reply({
        embeds: [
          embed(
            `✅ Members with <@&${role.id}> now have full casino-admin access (add money, change currency, etc).`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- ADD MONEY ---------- */

    if (command === "addmoney") {
      if (!hasCasinoAccess(message.member)) {
        return message.reply({
          embeds: [
            embed(
              "❌ You don't have permission to use this command.",
              COLOR_LOSE
            )
          ]
        });
      }

      const location = (args[0] || "").toLowerCase();
      const target = message.mentions.users.first();
      const amount = Number(args[2]);

      if (
        !["bank", "cash"].includes(location) ||
        !target ||
        !Number.isFinite(amount) ||
        amount <= 0
      ) {
        return message.reply({
          embeds: [
            embed(
              "❌ Usage: `$addmoney cash/bank @user <amount>`",
              COLOR_LOSE
            )
          ]
        });
      }

      const targetUser = getUser(target.id);
      const flooredAmount = Math.floor(amount);

      if (location === "bank") {
        targetUser.bank += flooredAmount;
      } else {
        targetUser.cash += flooredAmount;
      }

      saveData();

      return message.reply({
        embeds: [
          embed(
            `✅ Added **${money(
              flooredAmount
            )}** ${db.currency} to <@${target.id}>'s ${location}.`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- LEADERBOARD ---------- */

    if (["lb", "leaderboard", "top"].includes(command)) {
      const isCashTop = (args[0] || "").toLowerCase() === "cash";

      const list = Object.entries(db.users)
        .sort((a, b) => {
          const aVal = isCashTop ? a[1].cash : a[1].cash + a[1].bank;
          const bVal = isCashTop ? b[1].cash : b[1].cash + b[1].bank;
          return bVal - aVal;
        })
        .slice(0, 10);

      const text = list.length
        ? list
            .map(([id, u], i) => {
              const value = isCashTop ? u.cash : u.cash + u.bank;
              return `**${i + 1}.** <@${id}> — **${money(
                value
              )}** ${db.currency}`;
            })
            .join("\n")
        : "No users yet.";

      return message.reply({
        embeds: [
          embed(
            text,
            COLOR_INFO,
            isCashTop
              ? "💵 Top Cash On Hand"
              : "🏆 Leaderboard"
          )
        ]
      });
    }

    /* ---------- WORK ---------- */

    if (command === "work") {
      const cooldownMs = 4 * 60 * 1000;
      const remaining = onCooldown(user, "work", cooldownMs);

      if (remaining > 0) {
        return message.reply({
          embeds: [
            embed(
              `⏳ You can work again in **${formatDuration(
                remaining
              )}**.`,
              COLOR_LOSE
            )
          ]
        });
      }

      const amount = random(4000, 12000);
      user.cash += amount;
      user.cooldowns.work = Date.now();
      saveData();

      return message.reply({
        embeds: [
          embed(
            `You worked hard and got **${money(
              amount
            )}** ${db.currency}!`,
            COLOR_WIN
          )
        ]
      });
    }

    /* ---------- CRIME ---------- */

    if (command === "crime") {
      const cooldownMs = 4 * 60 * 1000;
      const remaining = onCooldown(user, "crime", cooldownMs);

      if (remaining > 0) {
        return message.reply({
          embeds: [
            embed(
              `⏳ You can commit another crime in **${formatDuration(
                remaining
              )}**.`,
              COLOR_LOSE
            )
          ]
        });
      }

      user.cooldowns.crime = Date.now();
      const success = Math.random() < 0.75;

      if (success) {
        const amount = random(6000, 15000);
        user.cash += amount;
        saveData();

        return message.reply({
          embeds: [
            embed(
              `You successfully committed a crime and got **${money(
                amount
              )}** ${db.currency}!`,
              COLOR_WIN
            )
          ]
        });
      }

      const fine = random(1000, 3000);
      user.cash = Math.max(0, user.cash - fine);
      saveData();

      return message.reply({
        embeds: [
          embed(
            `🚨 You got caught and paid a fine of **${money(
              fine
            )}** ${db.currency}!`,
            COLOR_LOSE
          )
        ]
      });
    }

    /* ---------- ROB ---------- */

    if (command === "rob") {
      const cooldownMs = 8 * 60 * 1000;
      const remaining = onCooldown(user, "rob", cooldownMs);

      if (remaining > 0) {
        return message.reply({
          embeds: [
            embed(
              `⏳ You can try to rob someone again in **${formatDuration(
                remaining
              )}**.`,
              COLOR_LOSE
            )
          ]
        });
      }

      const target = message.mentions.users.first();

      if (!target || target.id === message.author.id) {
        return message.reply({
          embeds: [
            embed("❌ Usage: `$rob @user`", COLOR_LOSE)
          ]
        });
      }

      const targetUser = getUser(target.id);

      if (targetUser.cash < 500) {
        return message.reply({
          embeds: [
            embed(
              "❌ That person doesn't have enough cash on hand to rob.",
              COLOR_LOSE
            )
          ]
        });
      }

      user.cooldowns.rob = Date.now();
      const success = Math.random() < 0.45;

      if (success) {
        const stolen = Math.floor(
          targetUser.cash * randomFloat(0.1, 0.3)
        );
        targetUser.cash -= stolen;
        user.cash += stolen;
        saveData();

        return message.reply({
          embeds: [
            embed(
              `🕵️ You robbed <@${target.id}> and got away with **${money(
                stolen
              )}** ${db.currency}!`,
              COLOR_WIN
            )
          ]
        });
      }

      const fine = random(500, 1500);
      user.cash = Math.max(0, user.cash - fine);
      saveData();

      return message.reply({
        embeds: [
          embed(
            `🚔 You got caught trying to rob <@${target.id}> and paid **${money(
              fine
            )}** ${db.currency} in fines!`,
            COLOR_LOSE
          )
        ]
      });
    }

    /* ---------- GAMES ---------- */

    if (["bj", "blackjack"].includes(command)) {
      return blackjack(message, args, user);
    }

    if (["ht", "coinflip"].includes(command)) {
      return coinflip(message, args, user);
    }

    if (["hl", "higherlower"].includes(command)) {
      return higherLower(message, args, user);
    }

    if (["cf", "cockfight", "chickenfight"].includes(command)) {
      return cockfight(message, args, user);
    }

    if (["mines", "mine"].includes(command)) {
      return mines(message, args, user);
    }

    if (["mt", "moneytower"].includes(command)) {
      return moneyTower(message, args, user);
    }

    if (["gm", "goldmine"].includes(command)) {
      return goldmine(message, args, user);
    }

    if (["slots", "slot"].includes(command)) {
      return slots(message, args, user);
    }

    if (["roulette", "rl"].includes(command)) {
      return roulette(message, args, user);
    }

    if (["dice"].includes(command)) {
      return dice(message, args, user);
    }

    if (["wheel"].includes(command)) {
      return wheel(message, args, user);
    }

    if (["crash"].includes(command)) {
      return crash(message, args, user);
    }

    /* ---------- INFO ---------- */

    if (command === "info") {
      return message.reply({ embeds: [buildInfoEmbed()] });
    }
  } catch (error) {
    console.error("Command error:", error);
    message
      .reply({
        embeds: [
          embed(
            "❌ Something went wrong running that command.",
            COLOR_LOSE
          )
        ]
      })
      .catch(() => {});
  }
});

/* ============================================================
   BLACKJACK
   Target: ~51% player win rate, ~20% chance of an instant
   natural blackjack on the deal. This is achieved by biasing
   which cards get drawn after the initial deal, rather than
   rigging results outright — so it still plays like real
   blackjack.
   ============================================================ */

const CARD_VALUES = [
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

const TEN_VALUE_CARDS = ["10", "J", "Q", "K"];

// Real Unicode playing-card glyphs (renders as an actual card face on most
// platforms), ordered A,2,3,4,5,6,7,8,9,10,J,Q,K — matching CARD_VALUES.
const CARD_GLYPHS = {
  "♠": ["🂡", "🂢", "🂣", "🂤", "🂥", "🂦", "🂧", "🂨", "🂩", "🂪", "🂫", "🂭", "🂮"],
  "♥": ["🂱", "🂲", "🂳", "🂴", "🂵", "🂶", "🂷", "🂸", "🂹", "🂺", "🂻", "🂽", "🂾"],
  "♦": ["🃁", "🃂", "🃃", "🃄", "🃅", "🃆", "🃇", "🃈", "🃉", "🃊", "🃋", "🃍", "🃎"],
  "♣": ["🃑", "🃒", "🃓", "🃔", "🃕", "🃖", "🃗", "🃘", "🃙", "🃚", "🃛", "🃝", "🃞"]
};
const SUIT_KEYS = ["♠", "♥", "♦", "♣"];
const CARD_BACK = "🂠";

function rankIndex(value) {
  return CARD_VALUES.findIndex((c) => c[0] === value);
}

function makeCard(value, number) {
  const suit = SUIT_KEYS[random(0, 3)];
  return { value, number, glyph: CARD_GLYPHS[suit][rankIndex(value)] };
}

function drawStandardCard() {
  const [value, number] = CARD_VALUES[random(0, CARD_VALUES.length - 1)];
  return makeCard(value, number);
}

// Slightly favours low/mid cards so the player busts less often.
function drawPlayerCard() {
  const pool = [
    ...CARD_VALUES,
    ["2", 2],
    ["3", 3],
    ["4", 4],
    ["5", 5],
    ["6", 6]
  ];

  const [value, number] = pool[random(0, pool.length - 1)];
  return makeCard(value, number);
}

// Slightly favours high cards so the dealer busts a bit more often.
function drawDealerCard() {
  const pool = [
    ...CARD_VALUES,
    ["8", 8],
    ["9", 9],
    ["10", 10],
    ["J", 10],
    ["Q", 10],
    ["K", 10]
  ];

  const [value, number] = pool[random(0, pool.length - 1)];
  return makeCard(value, number);
}

function handValue(hand) {
  let total = hand.reduce((sum, card) => sum + card.number, 0);
  let aces = hand.filter((card) => card.value === "A").length;

  while (total > 21 && aces > 0) {
    total -= 10;
    aces--;
  }

  return total;
}

function handText(hand) {
  return hand.map((card) => card.glyph).join(" ");
}

function dealPlayerHand() {
  // ~20% chance of an instant natural blackjack.
  if (Math.random() < 0.2) {
    const ten = TEN_VALUE_CARDS[random(0, TEN_VALUE_CARDS.length - 1)];
    const tenCard = CARD_VALUES.find((c) => c[0] === ten);

    const cards = [makeCard("A", 11), makeCard(tenCard[0], tenCard[1])];

    return shuffle(cards);
  }

  return [drawStandardCard(), drawStandardCard()];
}

async function blackjack(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const player = dealPlayerHand();
  const dealer = [drawStandardCard(), drawStandardCard()];

  let totalBet = bet;
  let finished = false;

  const naturalBlackjack = handValue(player) === 21;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`bj:hit:${message.author.id}`)
      .setLabel("Hit")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`bj:stand:${message.author.id}`)
      .setLabel("Stand")
      .setStyle(ButtonStyle.Success),

    new ButtonBuilder()
      .setCustomId(`bj:double:${message.author.id}`)
      .setLabel("Double")
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(user.cash < bet)
  );

  function gameEmbed(showDealer = false) {
    return embed(
      `**Your hand:** ${handText(player)} — **${handValue(player)}**\n` +
        `**Dealer:** ${
          showDealer
            ? `${handText(dealer)} — **${handValue(dealer)}**`
            : `${handText([dealer[0]])} 🂠`
        }\n\n` +
        `Bet: **${money(totalBet)}** ${db.currency}`,
      COLOR_NEUTRAL,
      "🃏 Blackjack 🃏"
    );
  }

  if (naturalBlackjack) {
    const payout = Math.floor(totalBet * 2.5);
    user.cash += payout;
    saveData();

    return message.reply({
      embeds: [
        embed(
          `**Your hand:** ${handText(player)} — **21!**\n` +
            `**Dealer:** ${handText(dealer)} — **${handValue(
              dealer
            )}**\n\n` +
            `🎉 Blackjack!\nPayout: **${money(payout)}** ${db.currency}`,
          COLOR_WIN,
          "🃏 Blackjack 🃏"
        )
      ]
    });
  }

  const gameMessage = await message.reply({
    embeds: [gameEmbed()],
    components: [row]
  });

  const collector = gameMessage.createMessageComponentCollector({
    time: 120000
  });

  async function finish(result, payout, color) {
    if (finished) return;

    finished = true;
    collector.stop();

    if (payout > 0) {
      user.cash += payout;
    }

    saveData();

    await gameMessage.edit({
      embeds: [
        embed(
          `**Your hand:** ${handText(player)} — **${handValue(
            player
          )}**\n` +
            `**Dealer:** ${handText(dealer)} — **${handValue(
              dealer
            )}**\n\n` +
            `${result}` +
            (payout > 0
              ? `\nPayout: **${money(payout)}** ${db.currency}`
              : ""),
          color,
          "🃏 Blackjack 🃏"
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

    const action = interaction.customId.split(":")[1];

    if (action === "double") {
      if (user.cash < bet) {
        return interaction.reply({
          content: "❌ You don't have enough money to double.",
          ephemeral: true
        });
      }

      user.cash -= bet;
      totalBet += bet;
      player.push(drawPlayerCard());
      saveData();

      await interaction.deferUpdate();

      if (handValue(player) > 21) {
        return finish("💥 You busted!", 0, COLOR_LOSE);
      }

      while (handValue(dealer) < 17) {
        dealer.push(drawDealerCard());
      }

      const p = handValue(player);
      const d = handValue(dealer);

      if (d > 21 || p > d) return finish("🎉 You win!", totalBet * 2, COLOR_WIN);
      if (p === d) return finish("🤝 It's a tie!", totalBet, COLOR_INFO);
      return finish("❌ Dealer wins!", 0, COLOR_LOSE);
    }

    if (action === "hit") {
      player.push(drawPlayerCard());

      if (handValue(player) > 21) {
        await interaction.deferUpdate();
        return finish("💥 You busted!", 0, COLOR_LOSE);
      }

      return interaction.update({
        embeds: [gameEmbed()],
        components: [row]
      });
    }

    // stand
    await interaction.deferUpdate();

    while (handValue(dealer) < 17) {
      dealer.push(drawDealerCard());
    }

    const p = handValue(player);
    const d = handValue(dealer);

    if (d > 21 || p > d) return finish("🎉 You win!", totalBet * 2, COLOR_WIN);
    if (p === d) return finish("🤝 It's a tie!", totalBet, COLOR_INFO);
    return finish("❌ Dealer wins!", 0, COLOR_LOSE);
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    user.cash += totalBet;
    saveData();

    await gameMessage
      .edit({
        embeds: [
          embed(
            `⏰ Timed out.\nReturned **${money(
              totalBet
            )}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🃏 Blackjack 🃏"
          )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* ============================================================
   COINFLIP ($ht)
   ============================================================ */

async function coinflip(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`ht:h:${message.author.id}`)
      .setLabel("Head")
      .setStyle(ButtonStyle.Primary),

    new ButtonBuilder()
      .setCustomId(`ht:t:${message.author.id}`)
      .setLabel("Tail")
      .setStyle(ButtonStyle.Success)
  );

  const msg = await message.reply({
    embeds: [
      embed(
        `**Betting Amount:** ${money(bet)} ${db.currency}\n\n` +
          "Choose Head or Tail",
        COLOR_NEUTRAL,
        "🍀 CoinFlip 🍀"
      )
    ],
    components: [row]
  });

  const collector = msg.createMessageComponentCollector({
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
    const choice = interaction.customId.split(":")[1];
    const win = choice === result;

    if (win) {
      user.cash += bet * 2;
    }

    saveData();

    await interaction.update({
      embeds: [
        embed(
          `${result === "h" ? "🪙 Head!" : "🪙 Tail!"}\n\n` +
            (win
              ? `+You won **${money(bet * 2)}** ${db.currency}!`
              : `-You lost **${money(bet)}** ${db.currency}.`),
          win ? COLOR_WIN : COLOR_LOSE,
          "🍀 CoinFlip 🍀"
        )
      ],
      components: [disabledRow(row)]
    });
  });

  collector.on("end", async (collected) => {
    if (collected.size) return;

    user.cash += bet;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🍀 CoinFlip 🍀"
          )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* ============================================================
   HIGHER OR LOWER ($hl)
   "Same" always pays 25x. Higher/Lower multipliers are computed
   from the real odds with a small edge in the player's favor.
   ============================================================ */

function hlMultipliers(current) {
  const higherCount = 100 - current;
  const lowerCount = current - 1;

  const rawHigher = (100 / higherCount) * 1.02;
  const rawLower = (100 / lowerCount) * 1.02;

  const clamp = (n) => Math.min(15, Math.max(1.01, n));

  return {
    higher: Math.round(clamp(rawHigher) * 100) / 100,
    lower: Math.round(clamp(rawLower) * 100) / 100,
    same: 25
  };
}

async function higherLower(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const current = random(2, 99);
  const mult = hlMultipliers(current);

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`hl:hi:${message.author.id}`)
      .setLabel("Higher")
      .setStyle(ButtonStyle.Success),

    new ButtonBuilder()
      .setCustomId(`hl:eq:${message.author.id}`)
      .setLabel("Same")
      .setStyle(ButtonStyle.Secondary),

    new ButtonBuilder()
      .setCustomId(`hl:lo:${message.author.id}`)
      .setLabel("Lower")
      .setStyle(ButtonStyle.Primary)
  );

  const msg = await message.reply({
    embeds: [
      embed(
        `**Betting Amount:** ${money(bet)}\n` +
          `**1:** ${current}\n` +
          `**2:** ❓\n\n` +
          `**Higher:** ${mult.higher}x\n` +
          `**Same:** ${mult.same}x\n` +
          `**Lower:** ${mult.lower}x`,
        COLOR_NEUTRAL,
        "🎲 Higher or Lower 🎲"
      )
    ],
    components: [row]
  });

  const collector = msg.createMessageComponentCollector({
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
    const choice = interaction.customId.split(":")[1];

    const win =
      (choice === "hi" && next > current) ||
      (choice === "lo" && next < current) ||
      (choice === "eq" && next === current);

    const multiplier =
      choice === "hi" ? mult.higher : choice === "lo" ? mult.lower : mult.same;

    const payout = win ? Math.floor(bet * multiplier) : 0;

    if (payout > 0) {
      user.cash += payout;
    }

    saveData();

    await interaction.update({
      embeds: [
        embed(
          `**1:** ${current}\n**2:** ${next}\n\n` +
            (win
              ? `+You won **${money(payout)}** ${db.currency}!`
              : `-You lost **${money(bet)}** ${db.currency}.`),
          win ? COLOR_WIN : COLOR_LOSE,
          "🎲 Higher or Lower 🎲"
        )
      ],
      components: [disabledRow(row)]
    });
  });

  collector.on("end", async (collected) => {
    if (collected.size) return;

    user.cash += bet;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🎲 Higher or Lower 🎲"
          )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* ============================================================
   COCKFIGHT ($cf)
   ============================================================ */

async function cockfight(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  if (user.cfStreak === undefined) user.cfStreak = 55;
  const yours = user.cfStreak;

  const win = Math.random() * 100 < yours;

  if (win) {
    user.cash += bet * 2;
    user.cfStreak = Math.min(82, user.cfStreak + 1);
  } else {
    user.cfStreak = 55;
  }

  saveData();

  return message.reply({
    embeds: [
      embed(
        win
          ? `Your chicken won the fight, you won **${money(
              bet * 2
            )}** ${db.currency}!\n\n` +
              `Your chicken's strength (chance of winning): **${yours}%**\n` +
              `You now have **${money(user.cash)}** ${db.currency}`
          : `Your chicken lost the fight... You lost **${money(
              bet
            )}** ${db.currency}.\n\n` +
              `Your chicken's strength (chance of winning): **${yours}%**`,
        win ? COLOR_WIN : COLOR_LOSE,
        "🐔 Cockfight 🐔"
      )
    ]
  });
}

/* ============================================================
   MINES ($mines) — 3x3 grid, 1 bomb, 8 safe tiles
   ============================================================ */

const MINES_MULTIPLIERS = [1.1, 1.4, 1.8, 2.1, 2.8, 4.2, 6.2, 8.9];

async function mines(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const bomb = random(0, 8);
  const revealed = new Set();
  let finished = false;

  function multiplier() {
    return MINES_MULTIPLIERS[Math.max(0, revealed.size - 1)] || 8.9;
  }

  function tileRows(endGame = false) {
    const result = [];

    for (let r = 0; r < 3; r++) {
      const buttons = [];

      for (let c = 0; c < 3; c++) {
        const index = r * 3 + c;
        const isBomb = index === bomb;
        const isRevealed = revealed.has(index);

        let label = "🔲";
        let style = ButtonStyle.Secondary;

        if (endGame && isBomb) {
          label = "💣";
          style = ButtonStyle.Danger;
        } else if (isRevealed) {
          label = "💎";
          style = ButtonStyle.Success;
        }

        buttons.push(
          new ButtonBuilder()
            .setCustomId(`mn:${message.author.id}:${index}`)
            .setLabel(label)
            .setStyle(style)
            .setDisabled(isRevealed || endGame)
        );
      }

      result.push(new ActionRowBuilder().addComponents(buttons));
    }

    result.push(
      new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId(`mn:${message.author.id}:cash`)
          .setLabel("💰 Cashout")
          .setStyle(ButtonStyle.Success)
          .setDisabled(revealed.size === 0 || endGame)
      )
    );

    return result;
  }

  function gameEmbed() {
    return embed(
      `Pick a tile and avoid the bomb.\n\n` +
        `💎 Safe tiles: **${revealed.size}/8**\n` +
        `Multiplier: **${multiplier()}x**\n` +
        `Current value: **${money(bet * multiplier())}** ${
          db.currency
        }\n\n` +
        `Bet: **${money(bet)}** ${db.currency}`,
      COLOR_NEUTRAL,
      "💣 Mines 💣"
    );
  }

  const msg = await message.reply({
    embeds: [gameEmbed()],
    components: tileRows()
  });

  const collector = msg.createMessageComponentCollector({ time: 120000 });

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (finished) return;

    const parts = interaction.customId.split(":");
    const action = parts[2];

    if (action === "cash") {
      if (!revealed.size) {
        return interaction.reply({
          content: "❌ Reveal a tile first.",
          ephemeral: true
        });
      }

      finished = true;
      collector.stop();

      const payout = Math.floor(bet * multiplier());
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💰 Cashed out!\n\nPayout: **${money(payout)}** ${
              db.currency
            }.`,
            COLOR_WIN,
            "💣 Mines 💣"
          )
        ],
        components: tileRows(true)
      });
    }

    const index = Number(action);

    if (index === bomb) {
      finished = true;
      collector.stop();
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💥 BOOM!\n\nYou lost **${money(bet)}** ${db.currency}.`,
            COLOR_LOSE,
            "💣 Mines 💣"
          )
        ],
        components: tileRows(true)
      });
    }

    revealed.add(index);

    if (revealed.size === 8) {
      finished = true;
      collector.stop();

      const payout = bet * MINES_MULTIPLIERS[MINES_MULTIPLIERS.length - 1];
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💎 All safe tiles found!\n\nPayout: **${money(
              payout
            )}** ${db.currency}.`,
            COLOR_WIN,
            "💣 Mines 💣"
          )
        ],
        components: tileRows(true)
      });
    }

    return interaction.update({
      embeds: [gameEmbed()],
      components: tileRows()
    });
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    user.cash += bet;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out.\nReturned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "💣 Mines 💣"
          )
        ],
        components: tileRows(true)
      })
      .catch(() => {});
  });
}

/* ============================================================
   MONEY TOWER ($mt) — 5 rows, 3 tiles each (1 bomb, 2 safe)
   ============================================================ */

const TOWER_MULTIPLIERS = [1.5, 2.1, 2.3, 3.6, 7.6];

async function moneyTower(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  let level = 0; // 0-4, the row currently being played
  let finished = false;
  const bombPositions = TOWER_MULTIPLIERS.map(() => random(0, 2));

  function currentPayout() {
    if (level === 0) return 0;
    return Math.floor(bet * TOWER_MULTIPLIERS[level - 1]);
  }

  function buildRow(endGame = false) {
    const buttons = ["A", "B", "C"].map((label, col) =>
      new ButtonBuilder()
        .setCustomId(`mt:${message.author.id}:${col}`)
        .setLabel(label)
        .setStyle(ButtonStyle.Secondary)
        .setDisabled(endGame)
    );

    buttons.push(
      new ButtonBuilder()
        .setCustomId(`mt:${message.author.id}:cash`)
        .setLabel("💰 Cashout")
        .setStyle(ButtonStyle.Success)
        .setDisabled(level === 0 || endGame)
    );

    return new ActionRowBuilder().addComponents(buttons);
  }

  function gameEmbed() {
    const nextMultiplier = TOWER_MULTIPLIERS[level];

    return embed(
      `🏗️ Climb the tower! Each row has 1 bomb hidden among 3 tiles.\n\n` +
        `Level: **${level}/5**\n` +
        `Next multiplier: **${nextMultiplier}x**\n` +
        (level > 0
          ? `Current value: **${money(currentPayout())}** ${db.currency}\n`
          : "") +
        `Bet: **${money(bet)}** ${db.currency}`,
      COLOR_NEUTRAL,
      "💰 Money Tower 💰"
    );
  }

  const msg = await message.reply({
    embeds: [gameEmbed()],
    components: [buildRow()]
  });

  const collector = msg.createMessageComponentCollector({ time: 120000 });

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (finished) return;

    const action = interaction.customId.split(":")[2];

    if (action === "cash") {
      if (level === 0) {
        return interaction.reply({
          content: "❌ Clear at least one row first.",
          ephemeral: true
        });
      }

      finished = true;
      collector.stop();

      const payout = currentPayout();
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💰 Cashed out at level ${level}!\n\nPayout: **${money(
              payout
            )}** ${db.currency}.`,
            COLOR_WIN,
            "💰 Money Tower 💰"
          )
        ],
        components: [buildRow(true)]
      });
    }

    const col = Number(action);

    if (col === bombPositions[level]) {
      finished = true;
      collector.stop();
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💥 You hit a bomb on level ${
              level + 1
            }!\n\nYou lost **${money(bet)}** ${db.currency}.`,
            COLOR_LOSE,
            "💰 Money Tower 💰"
          )
        ],
        components: [buildRow(true)]
      });
    }

    level++;

    if (level === TOWER_MULTIPLIERS.length) {
      finished = true;
      collector.stop();

      const payout = Math.floor(bet * TOWER_MULTIPLIERS[level - 1]);
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `🏆 You reached the top of the tower!\n\nPayout: **${money(
              payout
            )}** ${db.currency}.`,
            COLOR_WIN,
            "💰 Money Tower 💰"
          )
        ],
        components: [buildRow(true)]
      });
    }

    return interaction.update({
      embeds: [gameEmbed()],
      components: [buildRow()]
    });
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    const payout = level > 0 ? currentPayout() : bet;
    user.cash += payout;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out.\nReturned **${money(payout)}** ${
              db.currency
            }.`,
            COLOR_NEUTRAL,
            "💰 Money Tower 💰"
          )
        ],
        components: [buildRow(true)]
      })
      .catch(() => {});
  });
}

/* ============================================================
   GOLDMINE ($gm) — 24 tiles, 12 bombs, fixed treasure counts,
   plus a map tile that reveals 3 random safe tiles for free.
   ============================================================ */

const GOLDMINE_SIZE = 24;
const GOLDMINE_BOMBS = 12;

// Exact counts (not random weights) — totals 12 non-bomb tiles.
const GOLDMINE_TREASURE_COUNTS = [
  { key: "rock", emoji: "🪨", mult: 1.2, count: 4 },
  { key: "coin", emoji: "🪙", mult: 2.5, count: 3 },
  { key: "diamond", emoji: "💎", mult: 3.5, count: 2 },
  { key: "moneybag", emoji: "💰", mult: 6.5, count: 1 },
  { key: "lantern", emoji: "🏮", mult: 20, count: 1 }
];

function buildGoldmineBoard() {
  const indices = shuffle([...Array(GOLDMINE_SIZE).keys()]);
  const board = new Array(GOLDMINE_SIZE);
  let cursor = 0;

  const bombTiles = indices.slice(cursor, cursor + GOLDMINE_BOMBS);
  cursor += GOLDMINE_BOMBS;
  for (const i of bombTiles) board[i] = { type: "bomb" };

  for (const def of GOLDMINE_TREASURE_COUNTS) {
    const tiles = indices.slice(cursor, cursor + def.count);
    cursor += def.count;
    for (const i of tiles) board[i] = { type: "treasure", ...def };
  }

  const mapTile = indices[cursor];
  board[mapTile] = { type: "map" };

  return board;
}

async function goldmine(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const board = buildGoldmineBoard();
  const revealed = new Set();
  let currentMultiplier = 1;
  let finished = false;

  function tileLabel(index, endGame) {
    const tile = board[index];
    const isRevealed = revealed.has(index);

    if (endGame && tile.type === "bomb") return "💣";
    if (!isRevealed) return "🔲";
    if (tile.type === "map") return "🗺️";
    return tile.emoji;
  }

  function tileStyle(index, endGame) {
    const tile = board[index];
    const isRevealed = revealed.has(index);

    if (endGame && tile.type === "bomb") return ButtonStyle.Danger;
    if (isRevealed) return ButtonStyle.Success;
    return ButtonStyle.Secondary;
  }

  function buildRows(endGame = false) {
    const rows = [];
    let index = 0;

    for (let r = 0; r < 5; r++) {
      const isLastRow = r === 4;
      const countThisRow = isLastRow ? GOLDMINE_SIZE - index : 5;
      const buttons = [];

      for (let c = 0; c < countThisRow; c++) {
        const i = index;
        index++;

        buttons.push(
          new ButtonBuilder()
            .setCustomId(`gm:${message.author.id}:${i}`)
            .setLabel(tileLabel(i, endGame))
            .setStyle(tileStyle(i, endGame))
            .setDisabled(revealed.has(i) || endGame)
        );
      }

      if (isLastRow) {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`gm:${message.author.id}:cash`)
            .setLabel("💰 Cashout")
            .setStyle(ButtonStyle.Success)
            .setDisabled(revealed.size === 0 || endGame)
        );
      }

      rows.push(new ActionRowBuilder().addComponents(buttons));
    }

    return rows;
  }

  function gameEmbed() {
    return embed(
      `⛏️ Dig for treasure! Avoid the bombs.\n\n` +
        `🪨 x1.2  🪙 x2.5  💎 x3.5  💰 x6.5  🏮 x20  🗺️ reveals 3 safe tiles\n\n` +
        `Bombs: **${GOLDMINE_BOMBS}/${GOLDMINE_SIZE}**\n` +
        `Tiles found: **${revealed.size}**\n` +
        `Multiplier: **${
          Math.round(currentMultiplier * 100) / 100
        }x**\n` +
        `Current value: **${money(
          bet * currentMultiplier
        )}** ${db.currency}\n\n` +
        `Bet: **${money(bet)}** ${db.currency}`,
      COLOR_NEUTRAL,
      "⛏️ Goldmine ⛏️"
    );
  }

  const msg = await message.reply({
    embeds: [gameEmbed()],
    components: buildRows()
  });

  const collector = msg.createMessageComponentCollector({ time: 150000 });

  function revealTreasureTile(index) {
    revealed.add(index);
    const tile = board[index];
    currentMultiplier *= tile.mult;
  }

  function revealMapBonus() {
    const pool = [...Array(GOLDMINE_SIZE).keys()].filter(
      (i) => !revealed.has(i) && board[i].type !== "bomb"
    );

    const picks = shuffle(pool).slice(0, 3);

    for (const i of picks) {
      if (board[i].type === "treasure") {
        revealTreasureTile(i);
      } else {
        revealed.add(i);
      }
    }
  }

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (finished) return;

    const action = interaction.customId.split(":")[2];

    if (action === "cash") {
      if (!revealed.size) {
        return interaction.reply({
          content: "❌ Reveal a tile first.",
          ephemeral: true
        });
      }

      finished = true;
      collector.stop();

      const payout = Math.floor(bet * currentMultiplier);
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💰 Cashed out!\n\nPayout: **${money(payout)}** ${
              db.currency
            }.`,
            COLOR_WIN,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components: buildRows(true)
      });
    }

    const index = Number(action);
    const tile = board[index];

    if (tile.type === "bomb") {
      finished = true;
      collector.stop();
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `💥 You hit a bomb!\n\nYou lost **${money(
              bet
            )}** ${db.currency}.`,
            COLOR_LOSE,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components: buildRows(true)
      });
    }

    if (tile.type === "map") {
      revealed.add(index);
      revealMapBonus();
    } else {
      revealTreasureTile(index);
    }

    const nonBombRevealed = revealed.size;
    const nonBombTotal = GOLDMINE_SIZE - GOLDMINE_BOMBS;

    if (nonBombRevealed >= nonBombTotal) {
      finished = true;
      collector.stop();

      const payout = Math.floor(bet * currentMultiplier);
      user.cash += payout;
      saveData();

      return interaction.update({
        embeds: [
          embed(
            `⛏️ You cleared the whole mine!\n\nPayout: **${money(
              payout
            )}** ${db.currency}.`,
            COLOR_WIN,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components: buildRows(true)
      });
    }

    return interaction.update({
      embeds: [gameEmbed()],
      components: buildRows()
    });
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    const payout = revealed.size > 0 ? Math.floor(bet * currentMultiplier) : bet;
    user.cash += payout;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out.\nReturned **${money(payout)}** ${
              db.currency
            }.`,
            COLOR_NEUTRAL,
            "⛏️ Goldmine ⛏️"
          )
        ],
        components: buildRows(true)
      })
      .catch(() => {});
  });
}

/* ============================================================
   SLOTS ($slots)
   ============================================================ */

const SLOT_SYMBOLS = [
  { emoji: "🍒", weight: 30, triple: 3 },
  { emoji: "🍋", weight: 25, triple: 4 },
  { emoji: "🍊", weight: 20, triple: 5 },
  { emoji: "🍇", weight: 15, triple: 6 },
  { emoji: "⭐", weight: 8, triple: 10 },
  { emoji: "7️⃣", weight: 2, triple: 20 }
];

function spinReel() {
  return weightedPick(SLOT_SYMBOLS);
}

async function slots(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const reels = [spinReel(), spinReel(), spinReel()];
  const [a, b, c] = reels;

  let multiplier = 0;
  let resultLine;

  if (a.emoji === b.emoji && b.emoji === c.emoji) {
    multiplier = a.triple;
    resultLine = `🎉 Jackpot! Triple ${a.emoji}!`;
  } else if (a.emoji === b.emoji || b.emoji === c.emoji || a.emoji === c.emoji) {
    multiplier = 1.2;
    resultLine = "🙂 Small win — two matching symbols.";
  } else {
    resultLine = "❌ No match.";
  }

  const payout = Math.floor(bet * multiplier);
  if (payout > 0) user.cash += payout;
  saveData();

  return message.reply({
    embeds: [
      embed(
        `[ ${a.emoji} | ${b.emoji} | ${c.emoji} ]\n\n` +
          `${resultLine}\n` +
          (payout > 0
            ? `+You won **${money(payout)}** ${db.currency}!`
            : `-You lost **${money(bet)}** ${db.currency}.`),
        payout > 0 ? COLOR_WIN : COLOR_LOSE,
        "🎰 Slots 🎰"
      )
    ]
  });
}

/* ============================================================
   ROULETTE ($roulette <amount> <red/black/green/number>)
   ============================================================ */

const ROULETTE_RED = new Set([
  1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
]);

function rouletteColor(n) {
  if (n === 0) return "green";
  return ROULETTE_RED.has(n) ? "red" : "black";
}

async function roulette(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  const choiceRaw = (args[1] || "").toLowerCase();
  const isNumberBet = /^\d+$/.test(choiceRaw);

  if (
    !isNumberBet &&
    !["red", "black", "green"].includes(choiceRaw)
  ) {
    // Nothing has been deducted from cash yet at this point.
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$roulette <amount> <red/black/green/0-36>`",
          COLOR_LOSE
        )
      ]
    });
  }

  if (isNumberBet && (Number(choiceRaw) < 0 || Number(choiceRaw) > 36)) {
    return message.reply({
      embeds: [embed("❌ Numbers must be between 0 and 36.", COLOR_LOSE)]
    });
  }

  user.cash -= bet;

  const result = random(0, 36);
  const color = rouletteColor(result);

  let win = false;
  let multiplier = 0;

  if (isNumberBet && Number(choiceRaw) === result) {
    win = true;
    multiplier = 30;
  } else if (!isNumberBet && choiceRaw === color) {
    win = true;
    multiplier = color === "green" ? 14 : 2;
  }

  const payout = win ? Math.floor(bet * multiplier) : 0;
  if (payout > 0) user.cash += payout;
  saveData();

  return message.reply({
    embeds: [
      embed(
        `🎯 Landed on **${result}** (${color})\n\n` +
          (win
            ? `+You won **${money(payout)}** ${db.currency}!`
            : `-You lost **${money(bet)}** ${db.currency}.`),
        win ? COLOR_WIN : COLOR_LOSE,
        "🎡 Roulette 🎡"
      )
    ]
  });
}

/* ============================================================
   DICE ($dice <amount> <over/under/seven>)
   Two dice, sum 2-12.
   ============================================================ */

async function dice(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  const choice = (args[1] || "").toLowerCase();

  if (!["over", "under", "seven"].includes(choice)) {
    // Nothing has been deducted from cash yet at this point.
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$dice <amount> <over/under/seven>` (over = 8-12, under = 2-6, seven = exactly 7)",
          COLOR_LOSE
        )
      ]
    });
  }

  user.cash -= bet;

  const die1 = random(1, 6);
  const die2 = random(1, 6);
  const sum = die1 + die2;

  const win =
    (choice === "over" && sum >= 8) ||
    (choice === "under" && sum <= 6) ||
    (choice === "seven" && sum === 7);

  const multiplier = choice === "seven" ? 5 : 2;
  const payout = win ? Math.floor(bet * multiplier) : 0;
  if (payout > 0) user.cash += payout;
  saveData();

  return message.reply({
    embeds: [
      embed(
        `🎲 You rolled: **${die1} + ${die2} = ${sum}**\n\n` +
          (win
            ? `+You won **${money(payout)}** ${db.currency}!`
            : `-You lost **${money(bet)}** ${db.currency}.`),
        win ? COLOR_WIN : COLOR_LOSE,
        "🎲 Dice 🎲"
      )
    ]
  });
}

/* ============================================================
   WHEEL OF FORTUNE ($wheel)
   ============================================================ */

const WHEEL_SEGMENTS = [
  { mult: 0, weight: 38, label: "💀 Bust" },
  { mult: 1.2, weight: 25, label: "🙂 1.2x" },
  { mult: 1.5, weight: 17, label: "😀 1.5x" },
  { mult: 2, weight: 12, label: "😃 2x" },
  { mult: 5, weight: 6, label: "🤑 5x" },
  { mult: 10, weight: 2, label: "🏆 10x" }
];

async function wheel(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;

  const result = weightedPick(WHEEL_SEGMENTS);
  const payout = Math.floor(bet * result.mult);
  if (payout > 0) user.cash += payout;
  saveData();

  return message.reply({
    embeds: [
      embed(
        `🎡 The wheel lands on... **${result.label}**\n\n` +
          (payout > 0
            ? `+You won **${money(payout)}** ${db.currency}!`
            : `-You lost **${money(bet)}** ${db.currency}.`),
        payout > 0 ? COLOR_WIN : COLOR_LOSE,
        "🎡 Wheel of Fortune 🎡"
      )
    ]
  });
}

/* ============================================================
   CRASH ($crash) — multiplier climbs every tick, cash out
   before it crashes or lose everything.
   ============================================================ */

function rollCrashPoint() {
  // Slightly player-favoured crash-point distribution, floored at 1.02x.
  const r = Math.random();
  const point = 0.98 / (1 - r * 0.94);
  return Math.max(1.02, Math.round(point * 100) / 100);
}

async function crash(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  user.cash -= bet;
  saveData();

  const crashPoint = rollCrashPoint();
  let multiplier = 1;
  let finished = false;

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`cr:cash:${message.author.id}`)
      .setLabel("💰 Cashout")
      .setStyle(ButtonStyle.Success)
  );

  function gameEmbed() {
    return embed(
      `📈 Multiplier: **${multiplier.toFixed(2)}x**\n` +
        `Current value: **${money(bet * multiplier)}** ${db.currency}\n\n` +
        `Bet: **${money(bet)}** ${db.currency}\n\n` +
        `Cash out before it crashes!`,
      COLOR_NEUTRAL,
      "🚀 Crash 🚀"
    );
  }

  const msg = await message.reply({
    embeds: [gameEmbed()],
    components: [row]
  });

  const collector = msg.createMessageComponentCollector({ time: 30000 });

  const interval = setInterval(async () => {
    if (finished) return;

    multiplier = Math.round(multiplier * 1.15 * 100) / 100;

    if (multiplier >= crashPoint) {
      finished = true;
      clearInterval(interval);
      collector.stop();
      saveData();

      await msg
        .edit({
          embeds: [
            embed(
              `💥 Crashed at **${crashPoint.toFixed(
                2
              )}x**!\n\nYou lost **${money(bet)}** ${db.currency}.`,
              COLOR_LOSE,
              "🚀 Crash 🚀"
            )
          ],
          components: [disabledRow(row)]
        })
        .catch(() => {});
      return;
    }

    await msg.edit({ embeds: [gameEmbed()], components: [row] }).catch(() => {});
  }, 1500);

  collector.on("collect", async (interaction) => {
    if (interaction.user.id !== message.author.id) {
      return interaction.reply({
        content: "❌ This isn't your game.",
        ephemeral: true
      });
    }

    if (finished) return;

    finished = true;
    clearInterval(interval);
    collector.stop();

    const payout = Math.floor(bet * multiplier);
    user.cash += payout;
    saveData();

    await interaction.update({
      embeds: [
        embed(
          `💰 Cashed out at **${multiplier.toFixed(
            2
          )}x**!\n\nPayout: **${money(payout)}** ${db.currency}.`,
          COLOR_WIN,
          "🚀 Crash 🚀"
        )
      ],
      components: [disabledRow(row)]
    });
  });

  collector.on("end", async () => {
    if (finished) return;

    finished = true;
    clearInterval(interval);
    user.cash += bet;
    saveData();

    await msg
      .edit({
        embeds: [
          embed(
            `⏰ Timed out.\nReturned **${money(bet)}** ${db.currency}.`,
            COLOR_NEUTRAL,
            "🚀 Crash 🚀"
          )
        ],
        components: [disabledRow(row)]
      })
      .catch(() => {});
  });
}

/* ============================================================
   $INFO — full rules for every game
   ============================================================ */

function buildInfoEmbed() {
  const lines = [
    `**🃏 Blackjack — \`$bj <amount>\`**`,
    `~20% instant blackjack (2.5x). Otherwise Hit/Stand/Double, win pays 2x.`,
    "",
    `**🐔 Cockfight — \`$cf <amount>\`**`,
    `Your win chance starts at 55% and climbs +1% per win (up to 82%). A loss resets it to 55%. Win pays 2x.`,
    "",
    `**🎲 Higher or Lower — \`$hl <amount>\`**`,
    `Guess higher, lower, or the same on a 1–100 roll. Same always pays 25x; Higher/Lower scale with the odds.`,
    "",
    `**🍀 CoinFlip — \`$ht <amount>\`**`,
    `50/50, pays 2x.`,
    "",
    `**💣 Mines — \`$mines <amount>\`**`,
    `3x3 grid, 1 bomb. Multipliers: 1.1x, 1.4x, 1.8x, 2.1x, 2.8x, 4.2x, 6.2x, 8.9x. Cash out anytime.`,
    "",
    `**💰 Money Tower — \`$mt <amount>\`**`,
    `5 levels, 3 tiles each (1 bomb). Level payouts: 1.5x, 2.1x, 2.3x, 3.6x, 7.6x.`,
    "",
    `**⛏️ Goldmine — \`$gm <amount>\`**`,
    `24 tiles, 12 bombs. 🪨 x1.2, 🪙 x2.5, 💎 x3.5, 💰 x6.5, 🏮 x20. One 🗺️ reveals 3 free safe tiles. Multipliers compound.`,
    "",
    `**🎰 Slots — \`$slots <amount>\`**`,
    `3 reels. Triple 7️⃣ 20x, ⭐ 10x, 🍇 6x, 🍊 5x, 🍋 4x, 🍒 3x. Any 2 matching pays 1.2x.`,
    "",
    `**🎡 Roulette — \`$roulette <amount> <red/black/green/0-36>\`**`,
    `Color bets pay 2x (green pays 14x); an exact number pays 30x.`,
    "",
    `**🎲 Dice — \`$dice <amount> <over/under/seven>\`**`,
    `Two dice. Over (8-12) or Under (2-6) pays 2x; exactly Seven pays 5x.`,
    "",
    `**🎡 Wheel of Fortune — \`$wheel <amount>\`**`,
    `Spin for 0x, 1.2x, 1.5x, 2x, 5x or a rare 10x jackpot.`,
    "",
    `**🚀 Crash — \`$crash <amount>\`**`,
    `A multiplier climbs every 1.5s — hit Cashout before it crashes or lose your bet.`,
    "",
    `_Every game accepts \`all\` instead of an amount to bet all your cash. Minimum bet: ${money(
      MIN_BET
    )} ${db.currency}._`
  ];

  return embed(lines.join("\n"), COLOR_INFO, "📖 Casino Bot — Game Rules");
}

/* ============================================================
   LOGIN
   ============================================================ */

if (!process.env.DISCORD_TOKEN) {
  console.error("❌ DISCORD_TOKEN is missing.");
} else {
  client.login(process.env.DISCORD_TOKEN).catch((error) => {
    console.error("❌ Discord login failed:");
    console.error(error);
  });
}
