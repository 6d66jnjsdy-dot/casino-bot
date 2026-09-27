const { getUser } = require('../../data');
const { randInt, money } = require('../../utils');

const COOLDOWN_MS = 15_000;
const cooldowns = new Map();

module.exports = {
  name: 'work',
  aliases: [],
  description: 'Work a shift for a guaranteed payout.',
  async execute(message, args, ctx) {
    const last = cooldowns.get(message.author.id) || 0;
    const now = Date.now();
    if (now - last < COOLDOWN_MS) {
      const wait = Math.ceil((COOLDOWN_MS - (now - last)) / 1000);
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.push, description: `You're still tired. Try again in ${wait}s.` })] });
    }
    cooldowns.set(message.author.id, now);

    const user = getUser(ctx.economy, message.author.id);
    const earned = randInt(500, 8000);
    user.cash += earned;
    user.moneyOut += earned;
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.win, description: `You worked hard and got ${money(earned)}!` })]
    });
  }
};
