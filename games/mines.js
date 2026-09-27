const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money } = require('../../utils');
const GRID_SIZE = 9; // 3x3
const MULTIPLIERS = [1.1, 1.4, 1.7, 2, 2.7, 4, 6.5, 8.7]; // one per safe diamond found
const DIAMOND = '💎';
const BOMB = '💣';
const HIDDEN = '‎';
module.exports = {
  name: 'mines',
  aliases: [],
  description: 'Mines (3x3, 1 bomb). Usage: $mines <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);
    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$mines <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }
    user.cash -= amount;
    ctx.saveEconomy(ctx.economy);
    const bombIndex = Math.floor(Math.random() * GRID_SIZE);
    const revealed = new Set();
    let finished = false;
    function currentMultiplier() {
      return revealed.size === 0 ? 1 : MULTIPLIERS[revealed.size - 1];
    }
    function buildRows(showAll = false) {
      const rows = [];
      for (let r = 0; r < 3; r++) {
        const row = new ActionRowBuilder();
        for (let c = 0; c < 3; c++) {
          const idx = r * 3 + c;
          const btn = new ButtonBuilder().setCustomId(`mines:${idx}`);
          if (showAll) {
            if (idx === bombIndex) {
              btn.setLabel(BOMB).setStyle(ButtonStyle.Danger);
            } else if (revealed.has(idx)) {
              btn.setLabel(DIAMOND).setStyle(ButtonStyle.Success);
            } else {
              btn.setLabel(HIDDEN).setStyle(ButtonStyle.Secondary);
            }
            btn.setDisabled(true);
          } else if (revealed.has(idx)) {
            btn.setLabel(DIAMOND).setStyle(ButtonStyle.Success).setDisabled(true);
          } else {
            btn.setLabel(HIDDEN).setStyle(ButtonStyle.Secondary);
          }
          row.addComponents(btn);
        }
        rows.push(row);
      }
      const profit = Math.round(amount * currentMultiplier()) - amount;
      const controlRow = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId('mines:cashout')
          .setLabel('Cashout')
          .setStyle(ButtonStyle.Success)
          .setDisabled(showAll || revealed.size === 0),
        new ButtonBuilder()
          .setCustomId('mines:profit')
          .setLabel(`Profit: ${profit.toLocaleString()} 💸`)
          .setStyle(ButtonStyle.Primary)
          .setDisabled(true)
      );
      rows.push(controlRow);
      return rows;
    }
    const embed = ctx.embed({ color: ctx.COLORS.info, description: `${message.author.username}'s Game` });
    const sent = await message.reply({ embeds: [embed], components: buildRows() });
    const collector = sent.createMessageComponentCollector({ time: 90_000 });
    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) return i.reply({ content: "This isn't your game.", ephemeral: true });
      if (finished) return i.deferUpdate();
      if (i.customId === 'mines:cashout') {
        finished = true;
        const payout = Math.round(amount * currentMultiplier());
        user.cash += payout;
        ctx.saveEconomy(ctx.economy);
        collector.stop('cashout');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.win,
              description: `**Result**\n\n+ You won and got ${payout.toLocaleString()} 💸!\n\nYou now have: ${money(user.cash)}`
            })
          ],
          components: buildRows(true)
        });
      }
      const idx = Number(i.customId.split(':')[1]);
      if (revealed.has(idx)) return i.deferUpdate();
      if (idx === bombIndex) {
        finished = true;
        ctx.saveEconomy(ctx.economy);
        collector.stop('bomb');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.loss,
              description: `**Result**\n\n- You Lost ${amount.toLocaleString()}! 💸\n\nYou now have ${money(user.cash)}.`
            })
          ],
          components: buildRows(true)
        });
      }
      revealed.add(idx);
      if (revealed.size === GRID_SIZE - 1) {
        // every non-bomb tile revealed -> auto cashout at max multiplier
        finished = true;
        const payout = Math.round(amount * currentMultiplier());
        user.cash += payout;
        ctx.saveEconomy(ctx.economy);
        collector.stop('cleared');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.win,
              description: `**Result**\n\n+ You won and got ${payout.toLocaleString()} 💸!\n\nYou now have: ${money(user.cash)}`
            })
          ],
          components: buildRows(true)
        });
      }
      await i.update({ embeds: [embed], components: buildRows() });
    });
    collector.on('end', (_collected, reason) => {
      if (!finished) {
        finished = true;
        ctx.saveEconomy(ctx.economy);
        sent.edit({ components: buildRows(true) }).catch(() => {});
      }
    });
  }
};