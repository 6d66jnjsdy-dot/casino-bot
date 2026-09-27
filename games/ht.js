const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money } = require('../../utils');
const { box: codeBox } = require('../../embeds');

module.exports = {
  name: 'ht',
  aliases: ['cointoss', 'coinflip'],
  description: 'Coin flip. Usage: $ht <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$ht <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    const embed = ctx.embed({
      color: ctx.COLORS.info,
      description: `🪙 **Higher or Tail** 🪙\n\n**Betting Amount:** ${codeBox(amount)}`
    });

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('ht:head').setLabel('Head').setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId('ht:tail').setLabel('Tail').setStyle(ButtonStyle.Primary)
    );

    const sent = await message.reply({ embeds: [embed], components: [row] });

    const collector = sent.createMessageComponentCollector({ time: 30_000, max: 1 });
    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) {
        return i.reply({ content: "This isn't your bet.", ephemeral: true });
      }

      const choice = i.customId.split(':')[1]; // head | tail
      if (amount > user.cash) {
        return i.update({
          embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You no longer have ${money(amount)}.` })],
          components: []
        });
      }

      const result = Math.random() < 0.5 ? 'head' : 'tail';
      const won = choice === result;

      user.cash -= amount;
      let resultLines;
      if (won) {
        const payout = amount * 2;
        user.cash += payout;
        resultLines =
          `You chose **${cap(choice)}**, the coin landed on **${cap(result)}**.\n` +
          `${codeBox(`+ You Won ${amount.toLocaleString()}! 💸`)}\n\n` +
          `You now have ${money(user.cash)}.`;
      } else {
        resultLines =
          `You chose **${cap(choice)}**, the coin landed on **${cap(result)}**.\n` +
          `${codeBox(`- You Lost ${amount.toLocaleString()}! 💸`)}\n\n` +
          `You now have ${money(user.cash)}.`;
      }
      ctx.saveEconomy(ctx.economy);

      await i.update({
        embeds: [ctx.embed({ color: won ? ctx.COLORS.win : ctx.COLORS.loss, description: `Result\n\n${resultLines}` })],
        components: []
      });
    });

    collector.on('end', (collected) => {
      if (collected.size === 0) {
        sent.edit({ components: [] }).catch(() => {});
      }
    });
  }
};

function cap(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
