const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const {
  getUser,
  saveData
} = require("../database");

const {
  money,
  embed
} = require("../helpers");

const activeGames = new Map();

function createDeck() {
  const suits = ["♠️", "♥️", "♦️", "♣️"];
  const ranks = [
    "A", "2", "3", "4", "5", "6", "7",
    "8", "9", "10", "J", "Q", "K"
  ];

  const deck = [];

  for (const suit of suits) {
    for (const rank of ranks) {
      deck.push({ rank, suit });
    }
  }

  return deck.sort(() => Math.random() - 0.5);
}

function cardValue(card) {
  if (["J", "Q", "K"].includes(card.rank)) {
    return 10;
  }

  if (card.rank === "A") {
    return 11;
  }

  return Number(card.rank);
}

function handValue(hand) {
  let total = 0;
  let aces = 0;

  for (const card of hand) {
    total += cardValue(card);

    if (card.rank === "A") {
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
  return hand
    .map(card => `${card.rank}${card.suit}`)
    .join("  ");
}

function createButtons(userId, disabled = false) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`bj:hit:${userId}`)
      .setLabel("Hit")
      .setStyle(ButtonStyle.Primary)
      .setDisabled(disabled),

    new ButtonBuilder()
      .setCustomId(`bj:stand:${userId}`)
      .setLabel("Stand")
      .setStyle(ButtonStyle.Secondary)
      .setDisabled(disabled)
  );
}

async function blackjack(message, bet) {
  const userId = message.author.id;

  if (activeGames.has(userId)) {
    return message.reply(
      "❌ You already have an active Blackjack game."
    );
  }

  const user = getUser(userId);

  if (user.cash < bet) {
    return message.reply(
      `❌ You don't have enough ${money()}.`
    );
  }

  user.cash -= bet;
  saveData();

  const deck = createDeck();

  const player = [
    deck.pop(),
    deck.pop()
  ];

  const dealer = [
    deck.pop(),
    deck.pop()
  ];

  const game = {
    userId,
    bet,
    deck,
    player,
    dealer,
    message: null
  };

  activeGames.set(userId, game);

  const playerValue = handValue(player);

  if (playerValue === 21) {
    user.cash += Math.floor(bet * 2.5);

    activeGames.delete(userId);
    saveData();

    return message.reply({
      embeds: [
        embed(
          "🃏 BLACKJACK",
          `Your hand:\n${handText(player)}\n\n` +
          `Dealer:\n${dealer[0].rank}${dealer[0].suit}  ❓\n\n` +
          `🎉 **BLACKJACK!**\n` +
          `💰 Payout: **${money(Math.floor(bet * 2.5))}**`
        )
      ]
    });
  }

  const sent = await message.reply({
    embeds: [
      embed(
        "🃏 BLACKJACK",
        `Your hand:\n${handText(player)}\n` +
        `**Value:** ${playerValue}\n\n` +
        `Dealer:\n${dealer[0].rank}${dealer[0].suit}  ❓`
      )
    ],
    components: [
      createButtons(userId)
    ]
  });

  game.message = sent;
}

async function finishBlackjack(game, message, result, payout = 0) {
  const user = getUser(game.userId);

  if (payout > 0) {
    user.cash += payout;
  }

  activeGames.delete(game.userId);
  saveData();

  let dealerText = handText(game.dealer);
  let resultText = "";

  if (result === "win") {
    resultText = `🎉 **You won!**\n💰 Payout: **${money(payout)}**`;
  } else if (result === "push") {
    resultText = `🤝 **Push!**\n💰 Your bet was returned.`;
  } else {
    resultText = `💀 **You lost.**`;
  }

  await message.edit({
    embeds: [
      embed(
        "🃏 BLACKJACK — RESULT",
        `Your hand:\n${handText(game.player)}\n` +
        `**Value:** ${handValue(game.player)}\n\n` +
        `Dealer:\n${dealerText}\n` +
        `**Value:** ${handValue(game.dealer)}\n\n` +
        resultText
      )
    ],
    components: [
      createButtons(game.userId, true)
    ]
  });
}

async function handleBlackjackButton(interaction) {
  if (!interaction.isButton()) {
    return false;
  }

  if (!interaction.customId.startsWith("bj:")) {
    return false;
  }

  const [, actionType, userId] =
    interaction.customId.split(":");

  if (interaction.user.id !== userId) {
    await interaction.reply({
      content: "❌ This game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  const game = activeGames.get(userId);

  if (!game) {
    await interaction.reply({
      content: "❌ This Blackjack game is no longer active.",
      ephemeral: true
    });

    return true;
  }

  await interaction.deferUpdate();

  // אם נבחר Hit או שהגענו ל-21 בעקבות פגיעה
  if (actionType === "hit") {
    const card = game.deck.pop();
    game.player.push(card);

    const value = handValue(game.player);

    if (value > 21) {
      await finishBlackjack(
        game,
        interaction.message,
        "lose"
      );
      return true;
    }

    if (value === 21) {
      // עובר אוטומטית لل-Stand אם הגענו ל-21
      // נריץ את הלוגיקה של stand ישירות
      while (handValue(game.dealer) < 17) {
        game.dealer.push(game.deck.pop());
      }

      const playerValue = handValue(game.player);
      const dealerValue = handValue(game.dealer);

      if (dealerValue > 21 || playerValue > dealerValue) {
        await finishBlackjack(game, interaction.message, "win", game.bet * 2);
        return true;
      }
      if (playerValue === dealerValue) {
        await finishBlackjack(game, interaction.message, "push", game.bet);
        return true;
      }
      await finishBlackjack(game, interaction.message, "lose");
      return true;
    }

    await interaction.message.edit({
      embeds: [
        embed(
          "🃏 BLACKJACK",
          `Your hand:\n${handText(game.player)}\n` +
          `**Value:** ${value}\n\n` +
          `Dealer:\n${game.dealer[0].rank}${game.dealer[0].suit}  ❓`
        )
      ],
      components: [
        createButtons(userId)
      ]
    });

    return true;
  }

  if (actionType === "stand") {
    while (
      handValue(game.dealer) < 17
    ) {
      game.dealer.push(
        game.deck.pop()
      );
    }

    const playerValue =
      handValue(game.player);

    const dealerValue =
      handValue(game.dealer);

    if (
      dealerValue > 21 ||
      playerValue > dealerValue
    ) {
      await finishBlackjack(
        game,
        interaction.message,
        "win",
        game.bet * 2
      );

      return true;
    }

    if (
      playerValue === dealerValue
    ) {
      await finishBlackjack(
        game,
        interaction.message,
        "push",
        game.bet
      );

      return true;
    }

    await finishBlackjack(
      game,
      interaction.message,
      "lose"
    );

    return true;
  }

  return true;
}

module.exports = {
  blackjack,
  handleBlackjackButton,
  createDeck,
  handValue,
  cardValue
};
