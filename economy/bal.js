const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { box } = require('../../embeds');
const { money } = require('../../utils');
const { buildTopEmbed } = require('./top');

module.exports = {
  name: 'bal',
  aliases: ['balance'],
  description: 'Shows your cash, bank, and total money.',
  async execute(message, args, ctx) {
    const target = message.mentions.users.first() || message.author;
    const user = getUser(ctx.economy, target.id);
    const total = user.cash + user.bank;

    const embed = ctx
      .embed({
        color: ctx.COLORS.info,
        description:
          `Use the ${box('top')} command to view your rank.\n\n` +
          `• **Money Out:** ${money(user.cash)}\n` +
          `• **Bank Money:** ${money(user.bank)}\n` +
          `• **Total Money:** ${money(total)}`
      })
      .setAuthor({ name: target.username, iconURL: target.displayAvatarURL() });

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId(`top:total:0`).setLabel('Top').setStyle(ButtonStyle.Primary)
    );

    const sent = await message.reply({ embeds: [embed], components: [row] });

    const collector = sent.createMessageComponentCollector({ time: 60_000 });
    collector.on('collect', async (i) => {
      if (i.customId === 'noop') return i.deferUpdate();
      const [, sortKey, page] = i.customId.split(':');
      const { embed: topEmbed, row: topRow, pageRow } = buildTopEmbed(ctx, sortKey, Number(page));
      await i.update({ embeds: [topEmbed], components: [topRow, pageRow] });
    });
  }
};
