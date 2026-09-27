const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { fmt } = require('../../utils');

const PAGE_SIZE = 10;
const SORT_LABELS = { bank: 'Bank', total: 'Total', cash: 'Cash' };

function sortValue(user, sortKey) {
  if (sortKey === 'bank') return user.bank;
  if (sortKey === 'cash') return user.cash;
  return user.cash + user.bank; // total
}

function buildTopEmbed(ctx, sortKey = 'total', page = 0) {
  const entries = Object.entries(ctx.economy.users)
    .map(([id, u]) => ({ id, value: sortValue(u, sortKey) }))
    .sort((a, b) => b.value - a.value);

  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const safePage = Math.min(Math.max(page, 0), totalPages - 1);
  const slice = entries.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const lines = slice.map((e, idx) => {
    const rank = safePage * PAGE_SIZE + idx + 1;
    return `${rank}. <@${e.id}> • ${fmt(e.value)} 💸`;
  });

  const embed = ctx
    .embed({
      color: ctx.COLORS.info,
      description: `**Top ${SORT_LABELS[sortKey]} Users**\n\n${lines.join('\n') || '_No players yet._'}`
    });

  const tabRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`top:bank:0`)
      .setLabel('Bank')
      .setStyle(sortKey === 'bank' ? ButtonStyle.Primary : ButtonStyle.Secondary),
    new ButtonBuilder()
      .setCustomId(`top:total:0`)
      .setLabel('Total')
      .setStyle(sortKey === 'total' ? ButtonStyle.Primary : ButtonStyle.Secondary),
    new ButtonBuilder()
      .setCustomId(`top:cash:0`)
      .setLabel('Cash')
      .setStyle(sortKey === 'cash' ? ButtonStyle.Primary : ButtonStyle.Secondary),
    new ButtonBuilder().setCustomId(`top:${sortKey}:${safePage}`).setLabel('🔄').setStyle(ButtonStyle.Secondary)
  );

  const pageRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`top:${sortKey}:${safePage - 1}`)
      .setLabel('Previous Page')
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(safePage <= 0),
    new ButtonBuilder().setCustomId('noop').setLabel(`Page • ${safePage + 1}/${totalPages}`).setStyle(ButtonStyle.Secondary).setDisabled(true),
    new ButtonBuilder()
      .setCustomId(`top:${sortKey}:${safePage + 1}`)
      .setLabel('Next Page')
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(safePage >= totalPages - 1)
  );

  return { embed, row: tabRow, pageRow };
}

module.exports = {
  name: 'top',
  aliases: ['lb'],
  description: 'Shows the server leaderboard.',
  buildTopEmbed,
  async execute(message, args, ctx) {
    const { embed, row, pageRow } = buildTopEmbed(ctx, 'total', 0);
    const sent = await message.reply({ embeds: [embed], components: [row, pageRow] });

    const collector = sent.createMessageComponentCollector({ time: 120_000 });
    collector.on('collect', async (i) => {
      if (i.customId === 'noop') return i.deferUpdate();
      const [, sortKey, page] = i.customId.split(':');
      const result = buildTopEmbed(ctx, sortKey, Number(page));
      await i.update({ embeds: [result.embed], components: [result.row, result.pageRow] });
    });
  }
};
