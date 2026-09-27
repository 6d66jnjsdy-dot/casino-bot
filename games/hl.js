const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money, randInt } = require('../../utils');
const { box: codeBox } = require('../../embeds');

const MULT = { higher: 2.1, same: 15, lower: 1.9 };

module.exports = {
  name: 'hl',
  aliases: ['higherlower'],
  description: 'Higher or Lower (numbers 1-10). Usage: $hl <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$hl <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    const first = randInt(1, 10);

    const embed = ctx.embed({
      color: ctx.COLORS.info,
      description:
        `🎲 **Higher or Lower** 🎲\n\n` +
        `**Betting Amount:** ${codeBox(amount)}\n` +
        `**1**: ${codeBox(first)}\n` +
        `**2**: ${codeBox('?')}\n\n` +
        `**Higher:** ${codeBox(MULT.higher + 'x')}\n` +
        `**Same:** ${codeBox(MULT.same + 'x')}\n` +
        `**Lower:** ${codeBox(MULT.lower + 'x')}`
    });

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('hl:higher').setLabel('Higher').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('hl:same').setLabel('Same').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('hl:lower').setLabel('Lower').setStyle(ButtonStyle.Primary)
    );

    const sent = await message.reply({ embeds: [embed], components: [row] });

    const collector = sent.createMessageComponentCollector({ time: 30_000, max: 1 });
    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) return i.reply({ content: "This isn't your bet.", ephemeral: true });
      if (amount > user.cash) {
        return i.update({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You no longer have ${money(amount)}.` })], components: [] });
      }

      const choice = i.customId.split(':')[1]; // higher | same | lower
      const second = randInt(1, 10);
      let outcome;
      if (second > first) outcome = 'higher';
      else if (second < first) outcome = 'lower';
      else outcome = 'same';

      const won = choice === outcome;
      user.cash -= amount;

      let body;
      if (won) {
        const payout = Math.round(amount * MULT[choice]);
        user.cash += payout;
        body = `**Game Over**\n\nYou won ${money(payout)}!\n**Your Choice:** ${codeBox(choice)}\n\n**1**: ${codeBox(first)}\n**2**: ${codeBox(second)}\n\n**Balance:** ${money(user.cash)}`;
      } else {
        body = `**Game Over**\n\nYou lost ${money(amount)}.\n**Your Choice:** ${codeBox(choice)}\n\n**1**: ${codeBox(first)}\n**2**: ${codeBox(second)}\n\n**Balance:** ${money(user.cash)}`;
      }
      ctx.saveEconomy(ctx.economy);

      await i.update({ embeds: [ctx.embed({ color: won ? ctx.COLORS.win : ctx.COLORS.loss, description: body })], components: [] });
    });

    collector.on('end', (collected) => {
      if (collected.size === 0) sent.edit({ components: [] }).catch(() => {});
    });
  }
};
