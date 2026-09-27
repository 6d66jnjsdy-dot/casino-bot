const { getUser } = require('../../data');
const { parseAmount, money, chance } = require('../../utils');

const BASE_CHANCE = 50;
const MAX_CHANCE = 85;

module.exports = {
  name: 'cf',
  aliases: ['chickenfight'],
  description: 'Chicken Fight. Win chance rises with your streak, up to 85%. Usage: $cf <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$cf <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    const winChance = Math.min(BASE_CHANCE + user.cfStreak, MAX_CHANCE);
    const won = chance(winChance);

    user.cash -= amount;
    let description;
    if (won) {
      user.cash += amount * 2;
      user.cfStreak += 1;
      description =
        `Your chicken won the fight, you won ${money(amount)}!\n\n` +
        `**Your chicken's strength (chance of winning):** ${winChance}%\n` +
        `You now have ${money(user.cash)}`;
    } else {
      user.cfStreak = 0;
      description =
        `Your chicken lost the fight... You lost ${money(amount)}.\n\n` +
        `**Your chicken's strength (chance of winning):** ${winChance}%\n` +
        `You now have ${money(user.cash)}`;
    }
    ctx.saveEconomy(ctx.economy);

    await message.reply({ embeds: [ctx.embed({ color: won ? ctx.COLORS.win : ctx.COLORS.loss, description })] });
  }
};
