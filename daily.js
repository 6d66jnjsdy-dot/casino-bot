const {
  db,
  getUser,
  saveData
} = require("./database");

const {
  COLORS,
  weightedPick,
  formatDuration,
  embed,
  disabledRow,
  sendSecretDM,
  logEvent
} = require("./helpers");

/* ============================================================
   DAILY PRIZES
   ============================================================ */

const DAILY_PRIZES = [
  {
    amount: 1750000,
    weight: 45,
    label: "1,750,000"
  },
  {
    amount: 25000000,
    weight: 30,
    label: "25,000,000"
  },
  {
    amount: 65000000,
    weight: 15,
    label: "65,000,000"
  },
  {
    amount: 100000000,
    weight: 5,
    label: "100,000,000 JACKPOT"
  }
];

/* ============================================================
   DAILY
   ============================================================ */

async function daily(
  message
) {
  const user =
    getUser(message.author.id);

  const last =
    db.daily[
      message.author.id
    ] || 0;

  const cooldown =
    24 * 60 * 60 * 1000;

  const left =
    cooldown -
    (
      Date.now() -
      last
    );

  if (left > 0) {
    return message.reply({
      embeds: [
        embed(
          `⏳ Your Daily wheel is ready again in **${formatDuration(left)}**.`,
          COLORS.LOSE,
          "☀️ Daily ☀️"
        )
      ]
    });
  }

  const row =
    new (require("discord.js")
      .ActionRowBuilder)()
      .addComponents(
        new (require("discord.js")
          .ButtonBuilder)()
          .setCustomId(
            `daily:spin:${message.author.id}`
          )
          .setLabel("☀️ SPIN")
          .setStyle(
            require("discord.js")
              .ButtonStyle
              .Primary
          )
      );

  const msg =
    await message.reply({
      embeds: [
        embed(
          `☀️ **DAILY WHEEL** ☀️\n\n` +
          `🎁 1,750,000 — 45%\n` +
          `🎁 25,000,000 — 30%\n` +
          `🎁 65,000,000 — 15%\n` +
          `🏆 100,000,000 JACKPOT — 5%\n\n` +
          `Press **SPIN**. You get one spin every 24 hours.`,
          COLORS.PURPLE,
          "☀️ Daily ☀️"
        )
      ],
      components: [row]
    });

  let finished = false;

  const collector =
    msg.createMessageComponentCollector({
      time: 30000,
      max: 1
    });

  collector.on(
    "collect",
    async interaction => {
      if (
        interaction.user.id !==
        message.author.id
      ) {
        return interaction.reply({
          content:
            "❌ This isn't your wheel.",
          ephemeral: true
        });
      }

      if (finished) {
        return;
      }

      finished = true;

      /*
       * Pick the prize only when the user
       * actually spins.
       */
      const result =
        weightedPick(
          DAILY_PRIZES
        );

      await interaction.deferUpdate();

      for (
        let n = 0;
        n < 8;
        n++
      ) {
        await new Promise(
          resolve =>
            setTimeout(
              resolve,
              120
            )
        );

        await msg.edit({
          embeds: [
            embed(
              `☀️ **DAILY WHEEL**\n\n` +
              `🔄 ${
                [
                  "1,750,000",
                  "25,000,000",
                  "65,000,000",
                  "100,000,000 JACKPOT"
                ][n % 4]
              }\n\n🎡 Spinning...`,
              COLORS.PURPLE,
              "☀️ Daily ☀️"
            )
          ],
          components: []
        }).catch(() => {});
      }

      user.cash +=
        result.amount;

      /*
       * Cooldown starts only after
       * a successful spin.
       */
      db.daily[
        message.author.id
      ] = Date.now();

      saveData();

      await logEvent(
        message.guild,
        `☀️ Daily result for <@${message.author.id}>: **${result.label}** ${db.currency}.`,
        COLORS.WIN
      );

      await sendSecretDM(
        `☀️ Daily result: **${message.author.tag}** won **${result.label}**.`
      );

      await msg.edit({
        embeds: [
          embed(
            `🎉 **THE WHEEL STOPPED!**\n\n` +
            `🏆 Prize: **${result.label}** ${db.currency}\n\n` +
            `Your new cash: **${money(
              user.cash
            )}** ${db.currency}.`,
            COLORS.WIN,
            "☀️ Daily ☀️"
          )
        ],
        components: []
      }).catch(() => {});
    }
  );

  collector.on(
    "end",
    async collection => {
      if (
        collection.size ||
        finished
      ) {
        return;
      }

      /*
       * User did not spin.
       * No cooldown is consumed.
       */
      await msg.edit({
        embeds: [
          embed(
            "⏰ Daily spin expired. Use `$daily` again when you're ready.",
            COLORS.NEUTRAL,
            "☀️ Daily ☀️"
          )
        ],
        components: [
          disabledRow(row)
        ]
      }).catch(() => {});
    }
  );
}

/* ============================================================
   EXPORT
   ============================================================ */

module.exports = {
  daily,
  DAILY_PRIZES
};
