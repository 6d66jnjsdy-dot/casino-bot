const { getUser } = require('../../data');
const { randInt, money } = require('../../utils');

const COOLDOWN_MS = 20_000;
const cooldowns = new Map();

module.exports = {
  name: 'crime',
  aliases: [],
  description: 'Commit a crime for a bigger (guaranteed) payout than $work.',
  async execute(message, args, ctx) {
    const last = cooldowns.get(message.author.id) || 0;
    const now = Date.now();
    if (now - last < COOLDOWN_MS) {
      const wait = Math.ceil((COOLDOWN_MS - (now - last)) / 1000);
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.push, description: `Lay low for a bit. Try again in ${wait}s.` })] });
    }
    cooldowns.set(message.author.id, now);

    const user = getUser(ctx.economy, message.author.id);
    const earned = randInt(1000, 9000);
    user.cash += earned;
    user.moneyOut += earned;
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.win, description: `You successfully committed a crime and got ${money(earned)}!` })]
    });
  }
};
