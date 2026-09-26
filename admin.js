const {
  db,
  getUser,
  saveData
} = require("./database");

const {
  COLORS,
  money,
  embed,
  normalizeCommand
} = require("./helpers");

/* ============================================================
   ADMIN CHECK
   ============================================================ */

function isAdmin(message) {
  return !!(
    message.member &&
    message.member.permissions.has("Administrator")
  );
}

function deny(message) {
  return message.reply({
    embeds: [
      embed(
        "❌ You don't have permission to use this command.",
        COLORS.LOSE,
        "🔒 Access Denied"
      )
    ]
  });
}

/* ============================================================
   CASINO ROLE
   ============================================================ */

async function casinoRole(message, args) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const role =
    message.mentions.roles.first();

  if (!role) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$casinorole @role`",
          COLORS.LOSE
        )
      ]
    });
  }

  db.casinoRoleId = role.id;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🎰 Casino role set to <@&${role.id}>.`,
        COLORS.WIN,
        "🎰 Casino Role"
      )
    ]
  });
}

/* ============================================================
   GAME ROOMS
   ============================================================ */

async function roomGame(message) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const channelId =
    message.channel.id;

  if (
    db.gameChannels.includes(
      channelId
    )
  ) {
    db.gameChannels =
      db.gameChannels.filter(
        id => id !== channelId
      );

    saveData();

    return message.reply({
      embeds: [
        embed(
          "🚫 This channel is no longer a casino game room.",
          COLORS.LOSE
        )
      ]
    });
  }

  db.gameChannels.push(
    channelId
  );

  saveData();

  return message.reply({
    embeds: [
      embed(
        "✅ This channel is now a casino game room.",
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   LOG CHANNEL
   ============================================================ */

async function logChannel(message) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  db.logChannelId =
    message.channel.id;

  saveData();

  return message.reply({
    embeds: [
      embed(
        "🧾 This channel is now the casino log channel.",
        COLORS.WIN,
        "🧾 Logs"
      )
    ]
  });
}

/* ============================================================
   CURRENCY
   ============================================================ */

async function currency(message, args) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const value =
    args.join(" ").trim();

  if (!value) {
    return message.reply({
      embeds: [
        embed(
          `💸 Current currency: **${db.currency}**`,
          COLORS.INFO
        )
      ]
    });
  }

  db.currency = value;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `✅ Currency changed to **${value}**.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   PREDICT
   ============================================================ */

async function predict(message) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const user =
    message.mentions.users.first();

  if (!user) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$predict @user`",
          COLORS.LOSE
        )
      ]
    });
  }

  if (
    db.predictors.includes(
      user.id
    )
  ) {
    db.predictors =
      db.predictors.filter(
        id => id !== user.id
      );

    saveData();

    return message.reply({
      embeds: [
        embed(
          `🔮 <@${user.id}> was removed from prediction DMs.`,
          COLORS.LOSE
        )
      ]
    });
  }

  db.predictors.push(
    user.id
  );

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🔮 <@${user.id}> will now receive casino prediction DMs.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   ADD MONEY
   ============================================================ */

async function addMoney(
  message,
  args
) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const target =
    message.mentions.users.first();

  const amount =
    Math.floor(
      Number(
        args.find(
          value =>
            !value.startsWith("<@")
        )
      )
    );

  if (
    !target ||
    target.bot ||
    !Number.isFinite(amount) ||
    amount <= 0
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$addmoney @user <amount>`",
          COLORS.LOSE
        )
      ]
    });
  }

  const user =
    getUser(target.id);

  user.cash += amount;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `💰 Added **${money(amount)}** ${db.currency} to <@${target.id}>.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   REMOVE MONEY
   ============================================================ */

async function removeMoney(
  message,
  args
) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const target =
    message.mentions.users.first();

  const amount =
    Math.floor(
      Number(
        args.find(
          value =>
            !value.startsWith("<@")
        )
      )
    );

  if (
    !target ||
    target.bot ||
    !Number.isFinite(amount) ||
    amount <= 0
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$remove-money @user <amount>`",
          COLORS.LOSE
        )
      ]
    });
  }

  const user =
    getUser(target.id);

  const removed =
    Math.min(
      amount,
      user.cash
    );

  user.cash -= removed;

  saveData();

  return message.reply({
    embeds: [
      embed(
        `💸 Removed **${money(removed)}** ${db.currency} from <@${target.id}>.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   RESET ECONOMY
   ============================================================ */

async function resetEconomy(message) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  for (
    const id of Object.keys(
      db.users
    )
  ) {
    db.users[id].cash = 0;
    db.users[id].bank = 0;
    db.users[id].cooldowns = {};
  }

  db.daily = {};

  saveData();

  return message.reply({
    embeds: [
      embed(
        "⚠️ The entire casino economy has been reset.",
        COLORS.LOSE,
        "💥 Economy Reset"
      )
    ]
  });
}

/* ============================================================
   DISABLE COMMAND
   ============================================================ */

async function disable(
  message,
  args
) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const command =
    normalizeCommand(
      args[0]
    );

  if (!command) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$disable <command>`",
          COLORS.LOSE
        )
      ]
    });
  }

  if (
    db.disabledCommands.includes(
      command
    )
  ) {
    return message.reply({
      embeds: [
        embed(
          `⚠️ \`$${command}\` is already disabled.`,
          COLORS.INFO
        )
      ]
    });
  }

  db.disabledCommands.push(
    command
  );

  saveData();

  return message.reply({
    embeds: [
      embed(
        `🚫 Command \`$${command}\` has been disabled.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   UNDISABLE COMMAND
   ============================================================ */

async function undisable(
  message,
  args
) {
  if (!isAdmin(message)) {
    return deny(message);
  }

  const command =
    normalizeCommand(
      args[0]
    );

  if (!command) {
    return message.reply({
      embeds: [
        embed(
          "❌ Usage: `$undisable <command>`",
          COLORS.LOSE
        )
      ]
    });
  }

  if (
    !db.disabledCommands.includes(
      command
    )
  ) {
    return message.reply({
      embeds: [
        embed(
          `⚠️ \`$${command}\` is not disabled.`,
          COLORS.INFO
        )
      ]
    });
  }

  db.disabledCommands =
    db.disabledCommands.filter(
      cmd =>
        cmd !== command
    );

  saveData();

  return message.reply({
    embeds: [
      embed(
        `✅ Command \`$${command}\` has been enabled again.`,
        COLORS.WIN
      )
    ]
  });
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  casinoRole,
  roomGame,
  logChannel,
  currency,
  predict,
  addMoney,
  removeMoney,
  resetEconomy,
  disable,
  undisable
};
