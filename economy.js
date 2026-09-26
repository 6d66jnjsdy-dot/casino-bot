const {
  db,
  getUser,
  saveData
} = require("./database");

const {
  COLORS,
  money,
  random,
  formatDuration,
  onCooldown,
  embed
} = require("./helpers");

/* ============================================================
   BALANCE
   ============================================================ */

async function balance(message) {
  const target =
    message.mentions.users.first() ||
    message.author;

  const user =
    getUser(target.id);

  const total =
    user.cash + user.bank;

  return message.reply({
    embeds: [
      embed(
        `**${target.username}**\n\n` +
        `💵 Cash: **${money(user.cash)}** ${db.currency}\n` +
        `🏦 Bank: **${money(user.bank)}** ${db.currency}\n` +
        `📊 Total: **${money(total)}** ${db.currency}`,
        COLORS.INFO,
        "💰 Balance"
      )
    ]
  });
}

/* ============================================================
   DEPOSIT
   ============================================================ */

async function deposit(
  message,
  args
) {
  const user =
    getUser(message.author.id);

  const raw =
    (args[0] || "")
      .toLowerCase();

  let amount =
    raw === "all"
      ? user.cash
      : raw === "half"
        ? Math.floor(
            user.cash / 2
          )
        : Number(raw);

  if (
    !Number.isFinite(amount) ||
    amount <= 0 ||
    amount > user.cash
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$deposit <amount|half|all>`",
          COLORS.LOSE
        )
      ]
    });
  }

  amount =
    Math.floor(amount);

  user.cash -= amount;
  user.bank += amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🏦 Deposited **${money(amount)}** ${db.currency}.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   WITHDRAW
   ============================================================ */

async function withdraw(
  message,
  args
) {
  const user =
    getUser(message.author.id);

  const raw =
    (args[0] || "")
      .toLowerCase();

  let amount =
    raw === "all"
      ? user.bank
      : raw === "half"
        ? Math.floor(
            user.bank / 2
          )
        : Number(raw);

  if (
    !Number.isFinite(amount) ||
    amount <= 0 ||
    amount > user.bank
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$withdraw <amount|half|all>`",
          COLORS.LOSE
        )
      ]
    });
  }

  amount =
    Math.floor(amount);

  user.bank -= amount;
  user.cash += amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `💵 Withdrew **${money(amount)}** ${db.currency}.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   PAY
   ============================================================ */

async function pay(
  message,
  args
) {
  const sender =
    getUser(message.author.id);

  const target =
    message.mentions.users.first();

  const raw =
    (args[1] || "")
      .toLowerCase();

  let amount =
    raw === "all"
      ? sender.cash
      : raw === "half"
        ? Math.floor(
            sender.cash / 2
          )
        : Number(raw);

  if (
    !target ||
    target.bot ||
    target.id ===
      message.author.id ||
    !Number.isFinite(amount) ||
    amount <= 0 ||
    amount > sender.cash
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$pay @user <amount|half|all>`",
          COLORS.LOSE
        )
      ]
    });
  }

  amount =
    Math.floor(amount);

  sender.cash -= amount;

  getUser(target.id).cash +=
    amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `✅ Sent **${money(amount)}** ${db.currency} to <@${target.id}>.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   WORK
   ============================================================ */

async function work(message) {
  const user =
    getUser(message.author.id);

  const left =
    onCooldown(
      user,
      "work",
      4 * 60 * 1000
    );

  if (left) {
    return message.reply({
      embeds: [
        embed(
          `⏳ Work again in **${formatDuration(left)}**.`,
          COLORS.LOSE
        )
      ]
    });
  }

  const amount =
    random(
      4000,
      12000
    );

  user.cash += amount;

  user.cooldowns.work =
    Date.now();

  saveData();

  return message.reply({
    embeds: [
      embed(
        `💼 You earned **${money(amount)}** ${db.currency}!`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   CRIME
   ============================================================ */

async function crime(message) {
  const user =
    getUser(message.author.id);

  const left =
    onCooldown(
      user,
      "crime",
      4 * 60 * 1000
    );

  if (left) {
    return message.reply({
      embeds: [
        embed(
          `⏳ Crime again in **${formatDuration(left)}**.`,
          COLORS.LOSE
        )
      ]
    });
  }

  user.cooldowns.crime =
    Date.now();

  /*
   * 12% chance to get caught.
   * No money is removed when caught.
   */
  const caught =
    Math.random() < 0.12;

  if (caught) {
    saveData();

    return message.reply({
      embeds: [
        embed(
          "🚔 You got caught trying to commit a crime.\n\nNo money was lost.",
          COLORS.LOSE
        )
      ]
    });
  }

  const amount =
    random(
      6000,
      15000
    );

  user.cash += amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🚨 Crime succeeded: **${money(amount)}** ${db.currency}!`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   ROB
   ============================================================ */

async function rob(
  message
) {
  const user =
    getUser(message.author.id);

  const left =
    onCooldown(
      user,
      "rob",
      8 * 60 * 1000
    );

  if (left) {
    return message.reply({
      embeds: [
        embed(
          `⏳ Rob again in **${formatDuration(left)}**.`,
          COLORS.LOSE
        )
      ]
    });
  }

  const target =
    message.mentions.users.first();

  if (
    !target ||
    target.bot ||
    target.id ===
      message.author.id
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$rob @user`",
          COLORS.LOSE
        )
      ]
    });
  }

  const targetUser =
    getUser(target.id);

  user.cooldowns.rob =
    Date.now();

  /*
   * Target has no cash:
   * 12% catch chance.
   *
   * Target has cash:
   * 20% catch chance.
   *
   * Getting caught does NOT remove money.
   */
  const catchChance =
    targetUser.cash <= 0
      ? 0.12
      : 0.20;

  if (
    Math.random() <
    catchChance
  ) {
    saveData();

    return message.reply({
      embeds: [
        embed(
          `🚔 You got caught trying to rob <@${target.id}>.\n\nNo money was lost.`,
          COLORS.LOSE
        )
      ]
    });
  }

  if (
    targetUser.cash <= 0
  ) {
    saveData();

    return message.reply({
      embeds: [
        embed(
          `❌ <@${target.id}> has no money to rob.`,
          COLORS.LOSE
        )
      ]
    });
  }

  const amount =
    Math.max(
      1,
      Math.floor(
        targetUser.cash *
          (
            Math.random() *
              0.20 +
            0.10
          )
      )
    );

  targetUser.cash -= amount;
  user.cash += amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🕵️ You robbed <@${target.id}> and stole **${money(amount)}** ${db.currency}.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   LEADERBOARD
   ============================================================ */

async function leaderboard(
  message,
  args
) {
  const cashOnly =
    (args[0] || "")
      .toLowerCase() ===
    "cash";

  const list =
    Object.entries(db.users)
      .sort((a, b) =>
        cashOnly
          ? b[1].cash -
            a[1].cash
          : (
              b[1].cash +
              b[1].bank
            ) -
            (
              a[1].cash +
              a[1].bank
            )
      )
      .slice(0, 10);

  const text =
    list.length
      ? list
          .map(
            ([id, user], index) =>
              `**${index + 1}.** <@${id}> — **${money(
                cashOnly
                  ? user.cash
                  : user.cash +
                    user.bank
              )}** ${db.currency}`
          )
          .join("\n")
      : "No users yet.";

  return message.reply({
    embeds: [
      embed(
        text,
        COLORS.INFO,
        cashOnly
          ? "💵 Top Cash"
          : "🏆 Leaderboard"
      )
    ]
  });
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  balance,
  deposit,
  withdraw,
  pay,
  work,
  crime,
  rob,
  leaderboard
};
