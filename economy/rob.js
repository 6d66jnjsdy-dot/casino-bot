const { getUser } = require('../../data');
const { resolveUserId, chance, randInt, money } = require('../../utils');

const CAUGHT_CHANCE = 15; // %
const COOLDOWN_MS = 25_000;
const cooldowns = new Map();

module.exports = {
  name: 'rob',
  aliases: [],
  description: 'Try to rob another player\'s cash. 15% chance to get caught and fail. Usage: $rob @user',
  async execute(message, args, ctx) {
    const targetId = resolveUserId(message, args[0]);
    if (!targetId || targetId === message.author.id) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Mention a valid player to rob. Usage: `$rob @user`' })] });
    }

    const last = cooldowns.get(message.author.id) || 0;
    const now = Date.now();
    if (now - last < COOLDOWN_MS) {
      const wait = Math.ceil((COOLDOWN_MS - (now - last)) / 1000);
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.push, description: `Cops are watching you. Try again in ${wait}s.` })] });
    }
    cooldowns.set(message.author.id, now);

    const target = getUser(ctx.economy, targetId);
    if (target.cash <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.push, description: `<@${targetId}> has no cash on hand to rob.` })] });
    }

    if (chance(CAUGHT_CHANCE)) {
      await message.reply({
        embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You got caught trying to rob <@${targetId}> and lost 0 💸.` })]
      });
      return;
    }

    const robber = getUser(ctx.economy, message.author.id);
    const pct = randInt(10, 30) / 100;
    const stolen = Math.max(1, Math.floor(target.cash * pct));

    target.cash -= stolen;
    robber.cash += stolen;
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.win, description: `You successfully robbed <@${targetId}> and got ${money(stolen)}!` })]
    });
  }
};
