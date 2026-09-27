const { getUser } = require('../../data');
const { resolveUserId, money } = require('../../utils');
const { isCasinoStaff } = require('../../permissions');

module.exports = {
  name: 'removemoney',
  aliases: [],
  description: 'Casino staff only. Usage: $removemoney <bank|cash> @user <amount>',
  async execute(message, args, ctx) {
    if (!isCasinoStaff(message.member, ctx.config)) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'You need the Casino Staff role (or Administrator) to use this command.' })] });
    }

    const type = (args[0] || '').toLowerCase();
    if (!['bank', 'cash'].includes(type)) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Usage: `$removemoney <bank|cash> @user <amount>`' })] });
    }

    const targetId = resolveUserId(message, args[1]);
    const amount = Number(String(args[2] || '').replace(/,/g, ''));
    if (!targetId || !Number.isFinite(amount) || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Usage: `$removemoney <bank|cash> @user <amount>`' })] });
    }

    const target = getUser(ctx.economy, targetId);
    target[type] = Math.max(0, target[type] - Math.floor(amount));
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.win, description: `Removed ${money(Math.floor(amount))} from <@${targetId}>'s ${type}.` })]
    });
  }
};
