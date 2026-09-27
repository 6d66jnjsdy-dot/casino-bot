const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money, chance } = require('../../utils');
const COLS = 5;
const ROWS = 4;
const TOTAL = COLS * ROWS;
const BOMB_COUNT = 12;
const TILE = {
  BOMB: { key: 'bomb', emoji: '💣', mult: 0 },
  DIAMOND: { key: 'diamond', emoji: '💎', mult: 2.5 },
  ROCK: { key: 'rock', emoji: '🪨', mult: 1.1 },
  COIN: { key: 'coin', emoji: '🪙', mult: 2 },
  BAG: { key: 'bag', emoji: '💰', mult: 5 },
  JAR: { key: 'jar', emoji: '🏺', mult: 27.5 },
  HIDDEN: { key: 'hidden', emoji: '‎', mult: null }
};
function buildBoard() {
  const special = chance(100 / 7) ? TILE.JAR : TILE.BAG;
  const pool = [
    TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB,
    TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB, TILE.BOMB,
    TILE.COIN, TILE.COIN,
    TILE.DIAMOND, TILE.DIAMOND,
    TILE.ROCK, TILE.ROCK, TILE.ROCK,
    special
  ];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool;
}
module.exports = {
  name: 'gm',
  aliases: ['goldmines'],
  description: 'Gold Mines (5x4 grid, 12 bombs). Usage: $gm <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);
    if (!amount || amount <= 0) {
      return message.reply({
        embeds: [
          ctx.embed({
            color: ctx.COLORS.loss,
            description: 'Enter a valid amount, `all`, or `half`. Usage: `$gm <amount>`'
          })
        ]
      });
    }
    if (amount > user.cash) {
      return message.reply({
        embeds: [
          ctx.embed({
            color: ctx.COLORS.loss,
            description: `You only have ${money(user.cash)}.`
          })
        ]
      });
    }
    user.cash -= amount;
    ctx.saveEconomy(ctx.economy);
    const board = buildBoard();
    const revealed = new Set();
    let multiplier = 1;
    let finished = false;
    let dug = 0;
    function buildRows(showAll = false) {
      const rows = [];
      for (let r = 0; r < ROWS; r++) {
        const row = new ActionRowBuilder();
        for (let c = 0; c < COLS; c++) {
          const idx = r * COLS + c;
          const tile = board[idx];
          const btn = new ButtonBuilder()
            .setCustomId(`gm:${idx}`);
          if (showAll) {
            btn
              .setLabel(tile.emoji)
              .setDisabled(true)
              .setStyle(
                tile.key === 'bomb'
                  ? ButtonStyle.Danger
                  : revealed.has(idx)
                    ? ButtonStyle.Success
                    : ButtonStyle.Secondary
              );
          } else if (revealed.has(idx)) {
            btn
              .setLabel(tile.emoji)
              .setStyle(ButtonStyle.Success)
              .setDisabled(true);
          } else {
            btn
              .setLabel(TILE.HIDDEN.emoji)
              .setStyle(ButtonStyle.Secondary);
          }
          row.addComponents(btn);
        }
        rows.push(row);
      }
      const profit = Math.round(amount * multiplier) - amount;
      const controlRow = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId('gm:cashout')
          .setLabel('Cashout')
          .setStyle(ButtonStyle.Success)
          .setDisabled(showAll || dug === 0),
        new ButtonBuilder()
          .setCustomId('gm:profit')
          .setLabel(`Profit: ${profit.toLocaleString()} 💸`)
          .setStyle(ButtonStyle.Primary)
          .setDisabled(true)
      );
      rows.push(controlRow);
      return rows;
    }
    const embed = ctx.embed({
      color: ctx.COLORS.info,
      description: `${message.author.username}'s Game`
    });
    const sent = await message.reply({
      embeds: [embed],
      components: buildRows()
    });
    const collector = sent.createMessageComponentCollector({
      time: 90_000
    });
    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) {
        return i.reply({
          content: "This isn't your game.",
          ephemeral: true
        });
      }
      if (finished) return i.deferUpdate();
      if (i.customId === 'gm:cashout') {
        finished = true;
        const payout = Math.round(amount * multiplier);
        user.cash += payout;
        ctx.saveEconomy(ctx.economy);
        collector.stop('cashout');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.win,
              description:
                `+You won and got ${payout.toLocaleString()} 💸\n\n` +
                `You dug ${dug} tiles ⛏️\n` +
                `You now have: ${money(user.cash)}`
            })
          ],
          components: buildRows(true)
        });
      }
      const idx = Number(i.customId.split(':')[1]);
      if (revealed.has(idx)) {
        return i.deferUpdate();
      }
      const tile = board[idx];
      if (tile.key === 'bomb') {
        finished = true;
        ctx.saveEconomy(ctx.economy);
        collector.stop('bomb');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.loss,
              description:
                `- You lost ${amount.toLocaleString()}! 💸\n\n` +
                `You dug ${dug} tiles ⛏️\n` +
                `You now have: ${money(user.cash)}`
            })
          ],
          components: buildRows(true)
        });
      }
      revealed.add(idx);
      dug += 1;
      multiplier *= tile.mult;
      if (dug === TOTAL - BOMB_COUNT) {
        finished = true;
        const payout = Math.round(amount * multiplier);
        user.cash += payout;
        ctx.saveEconomy(ctx.economy);
        collector.stop('cleared');
        return i.update({
          embeds: [
            ctx.embed({
              color: ctx.COLORS.win,
              description:
                `+You won and got ${payout.toLocaleString()} 💸\n\n` +
                `You dug ${dug} tiles ⛏️\n` +
                `You now have: ${money(user.cash)}`
            })
          ],
          components: buildRows(true)
        });
      }
      await i.update({
        embeds: [embed],
        components: buildRows()
      });
    });
    collector.on('end', () => {
      if (!finished) {
        finished = true;
        ctx.saveEconomy(ctx.economy);
        sent.edit({
          components: buildRows(true)
        }).catch(() => {});
      }
    });
  }
};