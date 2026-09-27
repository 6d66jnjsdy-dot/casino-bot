const { getUser } = require('../../data');
const { parseAmount, money, pickWeighted } = require('../../utils');
const { box } = require('../../embeds');

const SYMBOLS = [
  { s: '7️⃣', weight: 2, triple: 10 },
  { s: '💎', weight: 4, triple: 7 },
  { s: '⭐', weight: 6, triple: 5 },
  { s: '🔔', weight: 10, triple: 4 },
  { s: '🍊', weight: 14, triple: 3 },
  { s: '🍋', weight: 18, triple: 2.5 },
  { s: '🍒', weight: 22, triple: 2 }
];

const PAIR_MULT = 1.2;

function spin() {
  return [roll(), roll(), roll()];
}
function roll() {
  return pickWeighted(SYMBOLS.map((x) => ({ value: x.s, weight: x.weight })));
}
function payoutFor(reels, amount) {
  const [a, b, c] = reels;
  if (a === b && b === c) {
    const sym = SYMBOLS.find((x) => x.s === a);
    return Math.round(amount * sym.triple);
  }
  if (a === b || b === c || a === c) {
    return Math.round(amount * PAIR_MULT);
  }
  return 0;
}

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

module.exports = {
  name: 'slots',
  aliases: ['slot'],
  description: 'Slot machine. Usage: $slots <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$slots <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    user.cash -= amount;
    ctx.saveEconomy(ctx.economy);

    const sent = await message.reply({
      embeds: [ctx.embed({ color: ctx.COLORS.info, description: `🎰 **Slots** 🎰\n\n${box('🔄 | 🔄 | 🔄')}\n\nSpinning...` })]
    });

    const finalReels = spin();

    // quick spin animation
    for (let frame = 0; frame < 4; frame++) {
      await sleep(400);
      const showReels = [0, 1, 2].map((i) => (frame >= 2 + i ? finalReels[i] : roll()));
      await sent
        .edit({ embeds: [ctx.embed({ color: ctx.COLORS.info, description: `🎰 **Slots** 🎰\n\n${box(showReels.join(' | '))}\n\nSpinning...` })] })
        .catch(() => {});
    }

    const payout = payoutFor(finalReels, amount);
    const won = payout > 0;
    if (won) user.cash += payout;
    ctx.saveEconomy(ctx.economy);

    const resultLine = won
      ? `+ You won ${payout.toLocaleString()} 💸!`
      : `- You lost ${amount.toLocaleString()}! 💸`;

    await sent.edit({
      embeds: [
        ctx.embed({
          color: won ? ctx.COLORS.win : ctx.COLORS.loss,
          description: `🎰 **Slots** 🎰\n\n${box(finalReels.join(' | '))}\n\n${resultLine}\n\nYou now have ${money(user.cash)}.`
        })
      ]
    });
  }
};
