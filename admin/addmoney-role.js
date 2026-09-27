const { getUser } = require('../../data');
const { money } = require('../../utils');
const { isCasinoStaff } = require('../../permissions');

module.exports = {
  name: 'addmoney-role',
  aliases: ['addmoneyrole'],
  description: 'Casino staff only. Usage: $addmoney-role <bank|cash> @role <amount>',
  async execute(message, args, ctx) {
    if (!isCasinoStaff(message.member, ctx.config)) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'You need the Casino Staff role (or Administrator) to use this command.' })] });
    }

    const type = (args[0] || '').toLowerCase();
    const role = message.mentions.roles.first();
    const amount = Number(String(args[2] || '').replace(/,/g, ''));

    if (!['bank', 'cash'].includes(type) || !role || !Number.isFinite(amount) || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Usage: `$addmoney-role <bank|cash> @role <amount>`' })] });
    }

    // Make sure we have the full member list cached for this role.
    await message.guild.members.fetch().catch(() => {});
    const members = role.members;

    let count = 0;
    for (const [, member] of members) {
      const target = getUser(ctx.economy, member.id);
      target[type] += Math.floor(amount);
      if (type === 'cash') target.moneyOut += Math.floor(amount);
      count += 1;
    }
    ctx.saveEconomy(ctx.economy);

    await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.win, description: `Added ${money(Math.floor(amount))} ${type} to ${count} member(s) of ${role}.` })]
    });
  }
};
