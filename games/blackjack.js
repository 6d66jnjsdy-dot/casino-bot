const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const { saveData } = require("../database");
const { embed, money } = require("../helpers");

const games = new Map();

function createDeck() {
  const suits = ["♠", "♥", "♦", "♣"];
  const ranks = [
    "A", "2", "3", "4", "5", "6", "7",
    "8", "9", "10", "J", "Q", "K"
  ];

  const deck = [];

  for (const suit of suits) {
    for (const rank of ranks) {
      deck.push({
        r: rank,
        s: suit
      });
    }
  }

  // Fisher-Yates shuffle
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }

  return deck;
}

function cardValue(card) {
  if (card.r === "A") return 11;
  if (["K", "Q", "J"].includes(card.r)) return 10;
  return Number(card.r);
}

function handValue(hand) {
  let total = 0;
  let aces = 0;

  for (const card of hand) {
    total += cardValue(card);

    if (card.r === "A") {
      aces++;
    }
  }

  while (total > 21 && aces > 0) {
    total -= 10;
    aces--;
  }

  return total;
}

function handText(hand) {
  return hand.map(card => `${card.r}${card.s}`).join(" ");
}

function gameRow(userId, disabled = false) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`bj:hit:${userId}`)
      .setLabel("HIT")
      .setStyle(ButtonStyle.Primary)
      .setDisabled(disabled),

    new ButtonBuilder()
      .setCustomId(`bj:stand:${userId}`)
      .setLabel("STAND")
      .setStyle(ButtonStyle.Success)
      .setDisabled(disabled)
  );
}

function gameEmbed(game) {
  const playerTotal = handValue(game.player);
  const dealerVisible = game.dealer[0];

  return embed(
    [
      `**You:** ${handText(game.player)} (**${playerTotal}**)`,
      `**Dealer:** ${dealerVisible.r}${dealerVisible.s} 🂠`,
      "",
      `💰 Bet: **${money(game.bet)}**`
    ].join("\n"),
    0x1c1c1c,
    "🃏 Blackjack"
  );
}

async function blackjack(message, args, user) {
  const bet = Number(args[0]);

  if (
    !Number.isFinite(bet) ||
    !Number.isInteger(bet) ||
    bet < 175 ||
    bet > user.cash
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Invalid bet.\nMinimum bet: **175**.",
          0xe74c3c,
          "🃏 Blackjack"
        )
      ]
    });
  }

  if (games.has(message.author.id)) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Blackjack game.",
          0xe74c3c,
          "🃏 Blackjack"
        )
      ]
    });
  }

  const deck = createDeck();

  const player = [
    deck.pop(),
    deck.pop()
  ];

  const dealer = [
    deck.pop(),
    deck.pop()
  ];

  // Remove bet immediately.
  user.cash -= bet;
  saveData();

  const game = {
    userId: message.author.id,
    user,
    bet,
    deck,
    player,
    dealer,
    message: null,
    finished: false
  };

  games.set(message.author.id, game);

  // Natural Blackjack
  if (handValue(player) === 21) {
    const payout = Math.floor(bet * 2.5);

    user.cash += payout;
    game.finished = true;

    saveData();
    games.delete(message.author.id);

    return message.reply({
      embeds: [
        embed(
          [
            "🃏 **BLACKJACK!**",
            "",
            `You: ${handText(player)} (**21**)`,
            `Dealer: ${handText(dealer)} (**${handValue(dealer)}**)`,
            "",
            `💰 Payout: **${money(payout)}**`
          ].join("\n"),
          0x2ecc71,
          "🃏 Blackjack"
        )
      ],
      components: []
    });
  }

  const msg = await message.reply({
    embeds: [gameEmbed(game)],
    components: [gameRow(message.author.id)]
  });

  game.message = msg;

  // Auto-timeout after 2 minutes.
  setTimeout(async () => {
    const active = games.get(message.author.id);

    if (!active || active.finished) return;

    active.finished = true;
    games.delete(message.author.id);

    await msg.edit({
      embeds: [
        embed(
          [
            "⏰ **Blackjack expired.**",
            "",
            `You lost **${money(bet)}**.`,
            "",
            `You: ${handText(player)} (${handValue(player)})`,
            `Dealer: ${handText(dealer)} (${handValue(dealer)})`
          ].join("\n"),
          0xe74c3c,
          "🃏 Blackjack"
        )
      ],
      components: []
    }).catch(() => {});
  }, 120000);
}

async function finishGame(game, result) {
  if (!game || game.finished) return;

  game.finished = true;

  const {
    user,
    bet,
    player,
    dealer,
    message
  } = game;

  // Dealer draws until at least 17.
  while (handValue(dealer) < 17) {
    const card = game.deck.pop();

    if (!card) break;

    dealer.push(card);
  }

  const playerTotal = handValue(player);
  const dealerTotal = handValue(dealer);

  let payout = 0;
  let text = "";

  if (result === "bust") {
    payout = 0;

    text = [
      "💥 **BUST!**",
      "",
      `You had **${playerTotal}**.`,
      `You lost **${money(bet)}**.`
    ].join("\n");
  } else if (playerTotal > 21) {
    payout = 0;

    text = `💥 **Bust!** You lost **${money(bet)}**.`;
  } else if (dealerTotal > 21) {
    payout = bet * 2;

    text = `🎉 **Dealer busts!** You win **${money(payout)}**.`;
  } else if (playerTotal > dealerTotal) {
    payout = bet * 2;

    text = `🎉 **You win!** You receive **${money(payout)}**.`;
  } else if (playerTotal === dealerTotal) {
    payout = bet;

    text = `🤝 **Push!** Your **${money(bet)}** bet was returned.`;
  } else {
    payout = 0;

    text = `❌ **Dealer wins.** You lost **${money(bet)}**.`;
  }

  if (payout > 0) {
    user.cash += payout;
  }

  saveData();
  games.delete(game.userId);

  await message.edit({
    embeds: [
      embed(
        [
          text,
          "",
          `**You:** ${handText(player)} (**${playerTotal}**)`,
          `**Dealer:** ${handText(dealer)} (**${dealerTotal}**)`
        ].join("\n"),
        payout > 0 ? 0x2ecc71 : 0xe74c3c,
        "🃏 Blackjack"
      )
    ],
    components: []
  }).catch(() => {});
}

async function handleBlackjackButton(interaction) {
  const parts = interaction.customId.split(":");

  if (parts.length !== 3) return;

  const action = parts[1];
  const userId = parts[2];

  const game = games.get(userId);

  if (!game) {
    return interaction.reply({
      content: "❌ This Blackjack game has already ended.",
      ephemeral: true
    });
  }

  if (interaction.user.id !== userId) {
    return interaction.reply({
      content: "❌ This isn't your game.",
      ephemeral: true
    });
  }

  if (game.finished) {
    return interaction.reply({
      content: "❌ This game has already ended.",
      ephemeral: true
    });
  }

  // HIT
  if (action === "hit") {
    const card = game.deck.pop();

    if (!card) {
      return interaction.reply({
        content: "❌ No cards left in the deck.",
        ephemeral: true
      });
    }

    game.player.push(card);

    const total = handValue(game.player);

    // Bust
    if (total > 21) {
      await interaction.update({
        embeds: [
          embed(
            [
              "💥 **BUST!**",
              "",
              `You drew **${card.r}${card.s}**.`,
              `Your total: **${total}**`,
              "",
              `You lost **${money(game.bet)}**.`
            ].join("\n"),
            0xe74c3c,
            "🃏 Blackjack"
          )
        ],
        components: []
      });

      game.finished = true;
      games.delete(userId);
      saveData();

      return;
    }

    // Exactly 21 → automatically stand.
    if (total === 21) {
      await interaction.deferUpdate();
      return finishGame(game, "stand");
    }

    return interaction.update({
      embeds: [gameEmbed(game)],
      components: [gameRow(userId)]
    });
  }

  // STAND
  if (action === "stand") {
    await interaction.deferUpdate();

    return finishGame(game, "stand");
  }
}

module.exports = {
  blackjack,
  handleBlackjackButton
};