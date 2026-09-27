const { isServerAdmin } = require('../../permissions');

module.exports = {
  name: 'casino-role',
  aliases: ['casinorole'],
  description: 'Server Administrator only. Sets which role counts as Casino Staff. Usage: $casino-role @role',
  async execute(message, args, ctx) {
    if (!isServerAdmin(message.member)) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Only server Administrators can set the Casino Staff role.' })] });
    }

    const role = message.mentions.roles.first();
    if (!role) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Usage: `$casino-role @role`' })] });
    }

    ctx.config.casinoRoleId = role.id;
    ctx.saveConfig(ctx.config);

    await message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.win, description: `${role} is now the Casino Staff role. Members with it can use \`$addmoney\`, \`$removemoney\`, and \`$addmoney-role\`.` })] });
  }
};
