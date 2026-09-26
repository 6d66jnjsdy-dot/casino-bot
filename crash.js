const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const {
  db,
  getUser,
  saveData
} = require("../database");

const {
  COLORS,
  money,
  embed
} = require("../helpers");

const activeGames = new Map();

/* ============================================================
   CRASH
   ============================================================ */

function createRow(userId) {
  return [
    new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`crash:cashout:${userId}`)
        .setLabel("CASH OUT")
        .setEmoji("💰")
        .setStyle(ButtonStyle.Success)
    )
  ];
}

/* ============================================================
   START GAME
   ============================================================ */

async function crash(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Crash game.",
          COLORS.LOSE,
          "💥 Crash"
        )
      ]
    });
  }

  const user = getUser(userId);

  if (
    !Number.isFinite(bet) ||
    bet <= 0
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Invalid bet.",
          COLORS.LOSE
        )
      ]
    });
  }

  if (user.cash < bet) {
    return message.reply({
      embeds: [
        embed(
          `❌ You only have **${money(
            user.cash
          )}** ${db.currency} in cash.`,
          COLORS.LOSE
        )
      ]
    });
  }

  user.cash -= bet;

  /*
   * Crash point.
   * Minimum crash is 1.00x.
   */
  const crashPoint =
    Math.max(
      1.00,
      1 +
        Math.random() *
          Math.random() *
          9
    );

  const game = {
    userId,
    bet,
    multiplier: 1.00,
    crashPoint,
    finished: false,
    interval: null,
    message: null
  };

  activeGames.set(userId, game);

  saveData();

  const sent = await message.reply({
    embeds: [
      embed(
        `💥 **CRASH**\n\n` +
        `📈 Multiplier: **1.00x**\n` +
        `💵 Bet: **${money(
          bet
        )}** ${db.currency}\n\n` +
        `💰 Cash out before the crash!`,
        COLORS.ACTIVE,
        "💥 Crash"
      )
    ],
    components: createRow(userId)
  });

  game.message = sent;

  /*
   * Increase multiplier every second.
   */
  game.interval = setInterval(
    async () => {
      if (
        game.finished ||
        !activeGames.has(userId)
      ) {
        clearInterval(game.interval);
        return;
      }

      game.multiplier =
        Number(
          (
            game.multiplier +
            0.15
          ).toFixed(2)
        );

      /*
       * Crash.
       */
      if (
        game.multiplier >=
        game.crashPoint
      ) {
        game.finished = true;

        clearInterval(game.interval);

        activeGames.delete(userId);

        saveData();

        try {
          await game.message.edit({
            embeds: [
              embed(
                `💥 **CRASHED!**\n\n` +
                `📉 Crashed at: **${game.crashPoint.toFixed(
                  2
                )}x**\n` +
                `💵 Lost: **${money(
                  game.bet
                )}** ${db.currency}\n` +
                `💳 Cash: **${money(
                  user.cash
                )}** ${db.currency}`,
                COLORS.LOSE,
                "💥 CRASH!"
              )
            ],
            components: []
          });
        } catch {}
        
        return;
      }

      /*
       * Update live multiplier.
       */
      try {
        await game.message.edit({
          embeds: [
            embed(
              `💥 **CRASH**\n\n` +
              `📈 Multiplier: **${game.multiplier.toFixed(
                2
              )}x**\n` +
              `💵 Bet: **${money(
                game.bet
              )}** ${db.currency}\n` +
              `💰 Current value: **${money(
                Math.floor(
                  game.bet *
                    game.multiplier
                )
              )}** ${db.currency}\n\n` +
              `Cash out before it crashes!`,
              COLORS.ACTIVE,
              "💥 Crash"
            )
          ],
          components: createRow(
            userId
          )
        });
      } catch {
        clearInterval(game.interval);
        activeGames.delete(userId);
      }
    },
    1000
  );
}

/* ============================================================
   CASH OUT
   ============================================================ */

async function handleCashout(
  interaction,
  game
) {
  const user = getUser(
    game.userId
  );

  if (game.finished) {
    return;
  }

  game.finished = true;

  clearInterval(
    game.interval
  );

  activeGames.delete(
    game.userId
  );

  const payout =
    Math.floor(
      game.bet *
        game.multiplier
    );

  user.cash += payout;

  saveData();

  await interaction.update({
    embeds: [
      embed(
        `💰 **CASHED OUT!**\n\n` +
        `📈 Multiplier: **${game.multiplier.toFixed(
          2
        )}x**\n` +
        `💵 Bet: **${money(
          game.bet
        )}** ${db.currency}\n` +
        `💰 Payout: **${money(
          payout
        )}** ${db.currency}\n` +
        `💳 Cash: **${money(
          user.cash
        )}** ${db.currency}`,
        COLORS.WIN,
        "💰 CASHED OUT!"
      )
    ],
    components: []
  });
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleCrashButton(interaction) {
  const customId =
    interaction.customId;

  if (
    !customId.startsWith(
      "crash:"
    )
  ) {
    return false;
  }

  const parts =
    customId.split(":");

  const action = parts[1];
  const userId = parts[2];

  if (
    interaction.user.id !==
    userId
  ) {
    await interaction.reply({
      content:
        "❌ This Crash game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game =
    activeGames.get(
      userId
    );

  if (!game) {
    await interaction.reply({
      content:
        "❌ This Crash game has already ended.",
      ephemeral: true
    });

    return true;
  }

  if (
    action === "cashout"
  ) {
    await handleCashout(
      interaction,
      game
    );
  }

  return true;
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  crash,
  handleCrashButton
};
