const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money } = require('../../utils');
const { box } = require('../../embeds');

const TICK_MS = 650;
const GROWTH = 1.06; // multiplier growth per tick
const INSTANT_CRASH_CHANCE = 0.03; // 3% chance to crash at 1.00x

function generateCrashPoint() {
  if (Math.random() < INSTANT_CRASH_CHANCE) return 1.0;
  const r = Math.random();
  const raw = 1 / (1 - r);
  const point = Math.max(1.02, Math.floor(raw * 100) / 100);
  return Math.min(point, 1000);
}

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

module.exports = {
  name: 'crash',
  aliases: [],
  description: 'Crash. Cash out before the rocket crashes. Usage: $crash <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$crash <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    user.cash -= amount;
    ctx.saveEconomy(ctx.economy);

    const crashPoint = generateCrashPoint();
    let multiplier = 1.0;
    let cashedOut = false;
    let crashed = false;

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('crash:cashout').setLabel('Cash Out').setStyle(ButtonStyle.Success)
    );

    function renderEmbed() {
      return ctx.embed({
        color: ctx.COLORS.info,
        description: `🚀 **Crash** 🚀\n\n${box(multiplier.toFixed(2) + 'x')}\n\nBet: ${money(amount)}`
      });
    }

    const sent = await message.reply({ embeds: [renderEmbed()], components: [row] });

    const collector = sent.createMessageComponentCollector({ time: 60_000 });
    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) return i.reply({ content: "This isn't your bet.", ephemeral: true });
      if (cashedOut || crashed) return i.deferUpdate();

      cashedOut = true;
      const payout = Math.round(amount * multiplier);
      user.cash += payout;
      ctx.saveEconomy(ctx.economy);

      await i.update({
        embeds: [
          ctx.embed({
            color: ctx.COLORS.win,
            description: `🚀 **Crash** 🚀\n\nYou cashed out at ${box(multiplier.toFixed(2) + 'x')}!\n+ You won ${payout.toLocaleString()} 💸\n\nYou now have ${money(user.cash)}.`
          })
        ],
        components: []
      });
      collector.stop('cashout');
    });

    while (!cashedOut && multiplier < crashPoint) {
      await sleep(TICK_MS);
      if (cashedOut) break;
      multiplier = Math.round(multiplier * GROWTH * 100) / 100;
      if (multiplier >= crashPoint) {
        multiplier = crashPoint;
        crashed = true;
        break;
      }
      await sent.edit({ embeds: [renderEmbed()], components: [row] }).catch(() => {});
    }

    if (crashed && !cashedOut) {
      ctx.saveEconomy(ctx.economy);
      collector.stop('crashed');
      await sent
        .edit({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.loss,
              description: `🚀 **Crash** 🚀\n\n💥 Crashed at ${box(crashPoint.toFixed(2) + 'x')}!\n- You lost ${amount.toLocaleString()}! 💸\n\nYou now have ${money(user.cash)}.`
            })
          ],
          components: []
        })
        .catch(() => {});
    }
  }
};
