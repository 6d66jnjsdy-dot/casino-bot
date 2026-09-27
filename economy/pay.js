const { getUser } = require('../../data');
const { parseAmount, resolveUserId, money } = require('../../utils');

module.exports = {
  name: 'pay',
  aliases: [],
  description: 'Pay another player from your cash. Usage: $pay @user <amount|all|half>',
  async execute(message, args, ctx) {
    const targetId = resolveUserId(message, args[0]);
    if (!targetId || targetId === message.author.id) {
      return message.reply({
        embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Mention a valid player to pay. Usage: `$pay @user <amount|all|half>`' })]
      });
    }

    const sender = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[1], sender.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`.' })] });
    }
    if (amount > sender.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(sender.cash)}.` })] });
    }

    const receiver = getUser(ctx.economy, targetId);
    sender.cash -= amount;
    receiver.cash += amount;
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [
        ctx.embed({
          color: ctx.COLORS.win,
          description: `Successfully paid ${money(amount)} to <@${targetId}>.`
        })
      ]
    });
  }
};
