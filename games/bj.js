const { ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { getUser } = require('../../data');
const { parseAmount, money } = require('../../utils');
const { box } = require('../../embeds');

const SUITS = ['♠', '♥', '♦', '♣'];
const RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];

function freshDeck() {
  const deck = [];
  for (const s of SUITS) for (const r of RANKS) deck.push({ r, s });
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
}

function cardValue(card) {
  if (card.r === 'A') return 11;
  if (['J', 'Q', 'K'].includes(card.r)) return 10;
  return Number(card.r);
}

function handValue(hand) {
  let total = hand.reduce((s, c) => s + cardValue(c), 0);
  let aces = hand.filter((c) => c.r === 'A').length;
  while (total > 21 && aces > 0) {
    total -= 10;
    aces -= 1;
  }
  return total;
}

function isBlackjack(hand) {
  return hand.length === 2 && handValue(hand) === 21;
}

function renderHand(hand) {
  return hand.map((c) => box(`${c.r}${c.s}`)).join(', ');
}

function dealerPlay(deck, dealer) {
  while (handValue(dealer) < 17) dealer.push(deck.pop());
  return dealer;
}

module.exports = {
  name: 'bj',
  aliases: ['blackjack'],
  description: 'Blackjack. Usage: $bj <amount|all|half>',
  async execute(message, args, ctx) {
    const user = getUser(ctx.economy, message.author.id);
    const amount = parseAmount(args[0], user.cash);

    if (!amount || amount <= 0) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Enter a valid amount, `all`, or `half`. Usage: `$bj <amount>`' })] });
    }
    if (amount > user.cash) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: `You only have ${money(user.cash)}.` })] });
    }

    user.cash -= amount;
    ctx.saveEconomy(ctx.economy);

    const deck = freshDeck();
    const player = [deck.pop(), deck.pop()];
    const dealer = [deck.pop(), deck.pop()];

    let bet = amount;
    let finished = false;
    let doubled = false;

    function buildEmbed({ reveal = false, title = 'Blackjack', extra = '' } = {}) {
      const playerVal = handValue(player);
      const dealerCards = reveal ? dealer : [dealer[0], { r: '?', s: '' }];
      const dealerVal = reveal ? handValue(dealer) : cardValue(dealer[0]);
      return ctx.embed({
        color: ctx.COLORS.info,
        description:
          `${message.author.username}'s Game\n\n` +
          `🂠 **${title}** 🂠\n${extra}\n` +
          `**Your Hand**\n${renderHand(player)}\n\n` +
          `Value: **${playerVal}**\n` +
          `**Dealer**\n${dealerCards.map((c) => (c.r === '?' ? box('🂠') : box(`${c.r}${c.s}`))).join(', ')}\n\n` +
          `Value: **${dealerVal}**`
      });
    }

    function buildRow(disableAll = false, canSplit = false, canDouble = true) {
      return new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('bj:hit').setLabel('Hit').setStyle(ButtonStyle.Primary).setDisabled(disableAll),
        new ButtonBuilder().setCustomId('bj:stand').setLabel('Stand').setStyle(ButtonStyle.Success).setDisabled(disableAll),
        new ButtonBuilder().setCustomId('bj:double').setLabel('Double').setStyle(ButtonStyle.Danger).setDisabled(disableAll || !canDouble || user.cash < bet),
        new ButtonBuilder().setCustomId('bj:split').setLabel('Split').setStyle(ButtonStyle.Secondary).setDisabled(disableAll || !canSplit)
      );
    }

    // Natural blackjack check
    if (isBlackjack(player)) {
      const dealerBJ = isBlackjack(dealer);
      let result;
      if (dealerBJ) {
        user.cash += bet; // push
        result = `Push! +0 💸`;
      } else {
        const payout = Math.round(bet * 2.5); // 3:2 profit + original bet back
        user.cash += payout;
        result = `Blackjack! You Won! +${(payout - bet).toLocaleString()} 💸`;
      }
      ctx.saveEconomy(ctx.economy);
      return message.reply({
        embeds: [buildEmbed({ reveal: true, title: 'Blackjack', extra: `\n${result}\n` })]
      });
    }

    const canSplitInitially = player[0].r === player[1].r || (cardValue(player[0]) === 10 && cardValue(player[1]) === 10);
    const sent = await message.reply({ embeds: [buildEmbed()], components: [buildRow(false, canSplitInitially, true)] });

    const collector = sent.createMessageComponentCollector({ time: 90_000 });

    async function resolve(i, extraText) {
      finished = true;
      ctx.saveEconomy(ctx.economy);
      const playerVal = handValue(player);
      const dealerVal = handValue(dealer);
      let color = ctx.COLORS.push;
      if (extraText.includes('Won')) color = ctx.COLORS.win;
      if (extraText.includes('Lost')) color = ctx.COLORS.loss;
      await i.update({
        embeds: [buildEmbed({ reveal: true, title: 'Blackjack', extra: `\n${extraText}\n` })],
        components: [buildRow(true, false, false)]
      });
      collector.stop('resolved');
    }

    collector.on('collect', async (i) => {
      if (i.user.id !== message.author.id) return i.reply({ content: "This isn't your game.", ephemeral: true });
      if (finished) return i.deferUpdate();

      if (i.customId === 'bj:hit') {
        player.push(deck.pop());
        const val = handValue(player);
        if (val > 21) {
          return resolve(i, `You Lost! -${bet.toLocaleString()} 💸`);
        }
        return i.update({ embeds: [buildEmbed()], components: [buildRow(false, false, false)] });
      }

      if (i.customId === 'bj:double') {
        if (user.cash < bet) return i.deferUpdate();
        user.cash -= bet;
        bet *= 2;
        doubled = true;
        player.push(deck.pop());
        const val = handValue(player);
        if (val > 21) {
          return resolve(i, `You Lost! -${bet.toLocaleString()} 💸`);
        }
        dealerPlay(deck, dealer);
        return finishAgainstDealer(i);
      }

      if (i.customId === 'bj:stand') {
        dealerPlay(deck, dealer);
        return finishAgainstDealer(i);
      }

      if (i.customId === 'bj:split') {
        // Simplified split: play two independent hands one after another with the same bet each.
        if (cardValue(player[0]) !== cardValue(player[1])) return i.deferUpdate();
        finished = true; // stop the normal collector; run a small sub-game
        collector.stop('split');
        await runSplit(i);
      }
    });

    async function finishAgainstDealer(i) {
      const playerVal = handValue(player);
      const dealerVal = handValue(dealer);
      let text;
      if (dealerVal > 21 || playerVal > dealerVal) {
        const payout = bet * 2;
        user.cash += payout;
        text = `You Won! +${bet.toLocaleString()} 💸`;
      } else if (playerVal === dealerVal) {
        user.cash += bet;
        text = `Push! +0 💸`;
      } else {
        text = `You Lost! -${bet.toLocaleString()} 💸`;
      }
      await resolve(i, text);
    }

    async function runSplit(i) {
      const extraBet = bet; // additional bet for the second hand
      if (user.cash < extraBet) {
        await i.update({ embeds: [buildEmbed({ extra: '\nNot enough cash to split.\n' })], components: [buildRow(true, false, false)] });
        return;
      }
      user.cash -= extraBet;
      ctx.saveEconomy(ctx.economy);

      const hands = [
        [player[0], deck.pop()],
        [player[1], deck.pop()]
      ];

      let totalPayout = 0;
      let summaryLines = [];

      for (let h = 0; h < hands.length; h++) {
        // auto-play simple strategy is avoided; give the player Hit/Stand for each split hand
        // via a short synchronous prompt loop reusing the same message.
        let handDone = false;
        while (!handDone) {
          const val = handValue(hands[h]);
          if (val >= 21) { handDone = true; break; }
          const rowSplit = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('bjsplit:hit').setLabel('Hit').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('bjsplit:stand').setLabel('Stand').setStyle(ButtonStyle.Success)
          );
          await i.update({
            embeds: [
              ctx.embed({
                color: ctx.COLORS.info,
                description:
                  `${message.author.username}'s Game — Split Hand ${h + 1}/2\n\n` +
                  `**Hand ${h + 1}**\n${renderHand(hands[h])}\n\nValue: **${val}**`
              })
            ],
            components: [rowSplit]
          }).catch(() => {});

          try {
            const btn = await sent.awaitMessageComponent({ time: 60_000, filter: (b) => b.user.id === message.author.id });
            i = btn;
            if (btn.customId === 'bjsplit:hit') {
              hands[h].push(deck.pop());
            } else {
              handDone = true;
            }
          } catch {
            handDone = true;
          }
        }
      }

      dealerPlay(deck, dealer);
      const dealerVal = handValue(dealer);

      for (let h = 0; h < hands.length; h++) {
        const val = handValue(hands[h]);
        if (val > 21) {
          summaryLines.push(`Hand ${h + 1}: ${renderHand(hands[h])} (${val}) — Lost -${bet.toLocaleString()} 💸`);
        } else if (dealerVal > 21 || val > dealerVal) {
          user.cash += bet * 2;
          summaryLines.push(`Hand ${h + 1}: ${renderHand(hands[h])} (${val}) — Won +${bet.toLocaleString()} 💸`);
        } else if (val === dealerVal) {
          user.cash += bet;
          summaryLines.push(`Hand ${h + 1}: ${renderHand(hands[h])} (${val}) — Push +0 💸`);
        } else {
          summaryLines.push(`Hand ${h + 1}: ${renderHand(hands[h])} (${val}) — Lost -${bet.toLocaleString()} 💸`);
        }
      }

      ctx.saveEconomy(ctx.economy);
      await i.update({
        embeds: [
          ctx.embed({
            color: ctx.COLORS.info,
            description:
              `${message.author.username}'s Game — Split Results\n\n` +
              `${summaryLines.join('\n')}\n\n` +
              `**Dealer**\n${renderHand(dealer)}\n\nValue: **${dealerVal}**\n\n` +
              `You now have ${money(user.cash)}.`
          })
        ],
        components: []
      }).catch(() => {});
    }

    collector.on('end', (_collected, reason) => {
      if (!finished && reason !== 'resolved' && reason !== 'split') {
        finished = true;
        ctx.saveEconomy(ctx.economy);
        sent.edit({ components: [] }).catch(() => {});
      }
    });
  }
};
