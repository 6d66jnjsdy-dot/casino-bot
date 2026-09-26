const {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle
} = require("discord.js");

const {
  db,
  getUser,
  saveData
} = require("../database");

const {
  COLORS,
  money,
  random,
  shuffle,
  embed
} = require("../helpers");

/* ============================================================
   BLACKJACK
   ============================================================ */

const activeGames = new Map();

const SUITS = ["♠️", "♥️", "♦️", "♣️"];

const RANKS = [
  "A",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "J",
  "Q",
  "K"
];

/* ============================================================
   DECK
   ============================================================ */

function createDeck() {
  const deck = [];

  for (const suit of SUITS) {
    for (const rank of RANKS) {
      deck.push({
        rank,
        suit
      });
    }
  }

  return shuffle(deck);
}

/* ============================================================
   CARD VALUE
   ============================================================ */

function cardValue(card) {
  if (
    ["J", "Q", "K"].includes(
      card.rank
    )
  ) {
    return 10;
  }

  if (card.rank === "A") {
    return 11;
  }

  return Number(card.rank);
}

/* ============================================================
   HAND VALUE
   ============================================================ */

function handValue(hand) {
  let total = 0;
  let aces = 0;

  for (const card of hand) {
    total += cardValue(card);

    if (card.rank === "A") {
      aces++;
    }
  }

  while (
    total > 21 &&
    aces > 0
  ) {
    total -= 10;
    aces--;
  }

  return total;
}

/* ============================================================
   CARD DISPLAY
   ============================================================ */

function cardText(card) {
  return `┌─────┐
│ ${String(card.rank).padEnd(2, " ")} ${card.suit} │
└─────┘`;
}

function hiddenCardText() {
  return `┌─────┐
│  ❓ │
└─────┘`;
}

function handText(hand) {
  return hand
    .map(cardText)
    .join("\n");
}

/* ============================================================
   BLACKJACK BUTTONS
   ============================================================ */

function gameRow(userId) {
  return new ActionRowBuilder()
    .addComponents(
      new ButtonBuilder()
        .setCustomId(
          `bj:hit:${userId}`
        )
        .setLabel("Hit")
        .setEmoji("🃏")
        .setStyle(
          ButtonStyle.Primary
        ),

      new ButtonBuilder()
        .setCustomId(
          `bj:stand:${userId}`
        )
        .setLabel("Stand")
        .setEmoji("✋")
        .setStyle(
          ButtonStyle.Success
        )
    );
}

/* ============================================================
   GAME EMBED
   ============================================================ */

function gameEmbed(
  game,
  revealDealer = false
) {
  const playerTotal =
    handValue(game.player);

  const dealerTotal =
    revealDealer
      ? handValue(
          game.dealer
        )
      : cardValue(
          game.dealer[0]
        );

  const dealerCards =
    revealDealer
      ? handText(
          game.dealer
        )
      : [
          cardText(
            game.dealer[0]
          ),
          hiddenCardText()
        ].join("\n");

  return embed(
    `👤 **Player**\n` +
      `${handText(
        game.player
      )}\n` +
      `**Value:** ${playerTotal}\n\n` +

      `🤖 **Dealer**\n` +
      `${dealerCards}\n` +
      `**Value:** ${
        revealDealer
          ? dealerTotal
          : `${dealerTotal}+`
      }\n\n` +
      `💵 Bet: **${money(
        game.bet
      )}** ${db.currency}`,
    COLORS.ACTIVE,
    "♠️ Blackjack"
  );
}

/* ============================================================
   START GAME
   ============================================================ */

async function blackjack(
  message,
  bet
) {
  const userId =
    message.author.id;

  if (
    activeGames.has(userId)
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ You already have an active Blackjack game.",
          COLORS.LOSE
        )
      ]
    });
  }

  const user =
    getUser(userId);

  if (
    !Number.isFinite(bet) ||
    bet <= 0
  ) {
    return message.reply({
      embeds: [
        embed(
          "❌ Invalid bet.",
          COLORS.LOSE
        )
      ]
    });
  }

  if (
    user.cash < bet
  ) {
    return message.reply({
      embeds: [
        embed(
          `❌ You only have **${money(
            user.cash
          )}** ${db.currency} in cash.`,
          COLORS.LOSE
        )
      ]
    });
  }

  user.cash -= bet;

  const deck =
    createDeck();

  const game = {
    userId,
    bet,
    deck,
    player: [
      deck.pop(),
      deck.pop()
    ],
    dealer: [
      deck.pop(),
      deck.pop()
    ],
    message: null,
    finished: false
  };

  activeGames.set(
    userId,
    game
  );

  saveData();

  /*
   * Natural blackjack.
   */
  const playerBJ =
    handValue(
      game.player
    ) === 21;

  const dealerBJ =
    handValue(
      game.dealer
    ) === 21;

  if (
    playerBJ ||
    dealerBJ
  ) {
    return finishBlackjack(
      game,
      message,
      playerBJ &&
        !dealerBJ
        ? "blackjack"
        : dealerBJ &&
            !playerBJ
          ? "dealer"
          : "push"
    );
  }

  const sent =
    await message.reply({
      embeds: [
        gameEmbed(game)
      ],
      components: [
        gameRow(userId)
      ]
    });

  game.message = sent;
}

/* ============================================================
   HIT
   ============================================================ */

async function hit(
  interaction
) {
  const userId =
    interaction.user.id;

  const game =
    activeGames.get(
      userId
    );

  if (!game) {
    return interaction.reply({
      content:
        "❌ You don't have an active Blackjack game.",
      ephemeral: true
    });
  }

  if (
    game.finished
  ) {
    return;
  }

  game.player.push(
    game.deck.pop()
  );

  const value =
    handValue(
      game.player
    );

  if (value > 21) {
    await interaction.update({
      embeds: [
        gameEmbed(
          game,
          true
        )
      ],
      components: []
    });

    return finishBlackjack(
      game,
      null,
      "bust"
    );
  }

  if (value === 21) {
    await interaction.update({
      embeds: [
        gameEmbed(
          game,
          false
        )
      ],
      components: []
    });

    return dealerTurn(
      game
    );
  }

  return interaction.update({
    embeds: [
      gameEmbed(game)
    ],
    components: [
      gameRow(userId)
    ]
  });
}

/* ============================================================
   STAND
   ============================================================ */

async function stand(
  interaction
) {
  const userId =
    interaction.user.id;

  const game =
    activeGames.get(
      userId
    );

  if (!game) {
    return interaction.reply({
      content:
        "❌ You don't have an active Blackjack game.",
      ephemeral: true
    });
  }

  if (
    game.finished
  ) {
    return;
  }

  await interaction.update({
    embeds: [
      gameEmbed(
        game,
        true
      )
    ],
    components: []
  });

  return dealerTurn(
    game
  );
}

/* ============================================================
   DEALER TURN
   ============================================================ */

async function dealerTurn(
  game
) {
  if (
    game.finished
  ) {
    return;
  }

  while (
    handValue(
      game.dealer
    ) < 17
  ) {
    game.dealer.push(
      game.deck.pop()
    );
  }

  const playerValue =
    handValue(
      game.player
    );

  const dealerValue =
    handValue(
      game.dealer
    );

  let result;

  if (
    dealerValue > 21
  ) {
    result = "win";
  } else if (
    playerValue >
    dealerValue
  ) {
    result = "win";
  } else if (
    playerValue <
    dealerValue
  ) {
    result = "lose";
  } else {
    result = "push";
  }

  return finishBlackjack(
    game,
    null,
    result
  );
}

/* ============================================================
   FINISH GAME
   ============================================================ */

async function finishBlackjack(
  game,
  originalMessage,
  result
) {
  if (
    game.finished
  ) {
    return;
  }

  game.finished = true;

  const user =
    getUser(
      game.userId
    );

  let payout = 0;
  let color = COLORS.LOSE;
  let title = "♠️ Blackjack";

  if (
    result === "blackjack"
  ) {
    /*
     * Natural blackjack pays 2.5x total.
     */
    payout =
      Math.floor(
        game.bet * 2.5
      );

    user.cash += payout;

    color = COLORS.WIN;
    title =
      "♠️ BLACKJACK!";
  }

  else if (
    result === "win"
  ) {
    /*
     * Normal win pays 2x total.
     */
    payout =
      game.bet * 2;

    user.cash += payout;

    color = COLORS.WIN;
    title =
      "♠️ YOU WIN!";
  }

  else if (
    result === "push"
  ) {
    /*
     * Return original bet.
     */
    payout =
      game.bet;

    user.cash += payout;

    color = COLORS.INFO;
    title =
      "♠️ PUSH";
  }

  else {
    /*
     * Bust / loss:
     * bet was already removed.
     */
    payout = 0;

    color = COLORS.LOSE;

    title =
      result === "bust"
        ? "💥 BUST!"
        : "♠️ DEALER WINS";
  }

  saveData();

  activeGames.delete(
    game.userId
  );

  const description =
    `👤 **Player**\n` +
    `${handText(
      game.player
    )}\n` +
    `**Value:** ${handValue(
      game.player
    )}\n\n` +

    `🤖 **Dealer**\n` +
    `${handText(
      game.dealer
    )}\n` +
    `**Value:** ${handValue(
      game.dealer
    )}\n\n` +

    `💵 Bet: **${money(
      game.bet
    )}** ${db.currency}\n` +
    `💰 Payout: **${money(
      payout
    )}** ${db.currency}\n` +
    `💳 Cash: **${money(
      user.cash
    )}** ${db.currency}`;

  const finalEmbed =
    embed(
      description,
      color,
      title
    );

  if (
    game.message
  ) {
    await game.message
      .edit({
        embeds: [
          finalEmbed
        ],
        components: []
      })
      .catch(() => {});
  }

  if (
    originalMessage
  ) {
    await originalMessage
      .edit({
        embeds: [
          finalEmbed
        ],
        components: []
      })
      .catch(() => {});
  }
}

/* ============================================================
   BUTTON HANDLER
   ============================================================ */

async function handleBlackjackButton(
  interaction
) {
  const customId =
    interaction.customId;

  if (
    !customId.startsWith(
      "bj:"
    )
  ) {
    return false;
  }

  const parts =
    customId.split(":");

  const action =
    parts[1];

  const userId =
    parts[2];

  if (
    interaction.user.id !==
    userId
  ) {
    await interaction.reply({
      content:
        "❌ This Blackjack game belongs to another player.",
      ephemeral: true
    });

    return true;
  }

  if (
    action === "hit"
  ) {
    await hit(
      interaction
    );

    return true;
  }

  if (
    action === "stand"
  ) {
    await stand(
      interaction
    );

    return true;
  }

  return false;
}

/* ============================================================
   EXPORTS
   ============================================================ */

module.exports = {
  blackjack,
  handleBlackjackButton,
  createDeck,
  handValue,
  cardValue
};
