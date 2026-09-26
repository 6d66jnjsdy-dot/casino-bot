const {
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle
} = require('discord.js');

const { COLORS } = require('../config');

// ==================== DRAW CARD ====================

function drawCard() {
    const values = [
        '2', '3', '4', '5', '6', '7', '8', '9', '10',
        'J', 'Q', 'K', 'A'
    ];

    return values[Math.floor(Math.random() * values.length)];
}

// ==================== HAND VALUE ====================

function calculateHandValue(hand) {
    let value = 0;
    let aces = 0;

    for (const card of hand) {
        if (['J', 'Q', 'K'].includes(card)) {
            value += 10;
        } else if (card === 'A') {
            aces++;
            value += 11;
        } else {
            value += Number(card);
        }
    }

    while (value > 21 && aces > 0) {
        value -= 10;
        aces--;
    }

    return value;
}

// ==================== FORMAT HAND ====================

function formatHand(hand, hideSecond = false) {
    if (hideSecond) {
        return `\` ${hand[0]} \`, \` 🟥 \``;
    }

    return hand
        .map(card => `\` ${card} \``)
        .join(', ');
}

// ==================== BLACKJACK ====================

async function blackjack(message, args, user) {
    let betAmount;

    const raw = String(args[0] || '').toLowerCase();

    if (raw === 'all') {
        betAmount = Math.floor(user.cash);
    } else if (raw === 'half') {
        betAmount = Math.floor(user.cash / 2);
    } else {
        betAmount = Math.floor(Number(raw));
    }

    if (
        !Number.isFinite(betAmount) ||
        betAmount <= 0 ||
        betAmount > user.cash
    ) {
        return message.reply(
            '❌ סכום ההימור אינו תקין או שאין לך מספיק כסף.'
        );
    }

    // הורדת ההימור
    user.cash -= betAmount;

    const playerHand = [drawCard(), drawCard()];
    const dealerHand = [drawCard(), drawCard()];

    // ==================== EMBED ====================

    const buildEmbed = () => {
        const playerValue = calculateHandValue(playerHand);
        const dealerVisibleValue = calculateHandValue([dealerHand[0]]);

        return new EmbedBuilder()
            .setAuthor({
                name: `${message.author.username}'s Game`,
                iconURL: message.author.displayAvatarURL()
            })
            .setTitle('🃏 Blackjack')
            .setColor(0xFEE75C)
            .addFields(
                {
                    name: 'Your Hand',
                    value: formatHand(playerHand),
                    inline: false
                },
                {
                    name: `Value: ${playerValue}`,
                    value: '\u200b',
                    inline: false
                },
                {
                    name: 'Dealer',
                    value: formatHand(dealerHand, true),
                    inline: false
                },
                {
                    name: `Value: ${dealerVisibleValue}`,
                    value: '\u200b',
                    inline: false
                }
            );
    };

    // ==================== BUTTONS ====================

    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
            .setCustomId(
                `bj:hit:${message.author.id}:${betAmount}`
            )
            .setLabel('Hit')
            .setStyle(ButtonStyle.Primary),

        new ButtonBuilder()
            .setCustomId(
                `bj:stand:${message.author.id}:${betAmount}`
            )
            .setLabel('Stand')
            .setStyle(ButtonStyle.Success),

        new ButtonBuilder()
            .setCustomId(
                `bj:double:${message.author.id}:${betAmount}`
            )
            .setLabel('Double')
            .setStyle(ButtonStyle.Danger),

        new ButtonBuilder()
            .setCustomId(
                `bj:split:${message.author.id}:${betAmount}`
            )
            .setLabel('Split')
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(true)
    );

    const gameMessage = await message.reply({
        embeds: [buildEmbed()],
        components: [row]
    });

    gameMessage.gameState = {
        playerHand,
        dealerHand,
        user,
        userId: message.author.id,
        betAmount
    };

    return gameMessage;
}

// ==================== BUTTON HANDLER ====================

async function handleBlackjackButton(interaction) {
    const parts = interaction.customId.split(':');

    const prefix = parts[0];
    const action = parts[1];
    const userId = parts[2];

    if (prefix !== 'bj') {
        return;
    }

    const message = interaction.message;
    const gameState = message.gameState;

    if (!gameState) {
        return interaction.reply({
            content: '❌ משחק זה פג תוקף.',
            ephemeral: true
        });
    }

    if (interaction.user.id !== gameState.userId) {
        return interaction.reply({
            content: '❌ זה לא המשחק שלך!',
            ephemeral: true
        });
    }

    const {
        playerHand,
        dealerHand,
        user
    } = gameState;

    let betAmount = gameState.betAmount;

    await interaction.deferUpdate();

    // ==================== FINISH GAME ====================

    const finishGame = async (status) => {
        let payout = 0;

        if (status === 'win') {
            payout = betAmount * 2;
        } else if (status === 'win_21') {
            payout = Math.floor(betAmount * 2.3);
        } else if (status === 'tie') {
            payout = betAmount;
        }

        user.cash += payout;

        let color = 0xED4245;

        if (status === 'win' || status === 'win_21') {
            color = 0x57F287;
        } else if (status === 'tie') {
            color = 0xE67E22;
        }

        let title = '🃏 Blackjack';

        if (status === 'win_21') {
            title = '🃏 Blackjack (💥 21 מושלם!)';
        }

        const endEmbed = new EmbedBuilder()
            .setAuthor({
                name: `${interaction.user.username}'s Game`,
                iconURL: interaction.user.displayAvatarURL()
            })
            .setTitle(title)
            .setColor(color)
            .addFields(
                {
                    name: 'Your Hand',
                    value: playerHand
                        .map(card => `\` ${card} \``)
                        .join(', '),
                    inline: false
                },
                {
                    name: `Value: ${calculateHandValue(playerHand)}`,
                    value: '\u200b',
                    inline: false
                },
                {
                    name: 'Dealer',
                    value: dealerHand
                        .map(card => `\` ${card} \``)
                        .join(', '),
                    inline: false
                },
                {
                    name: `Value: ${calculateHandValue(dealerHand)}`,
                    value: '\u200b',
                    inline: false
                }
            );

        await interaction.editReply({
            embeds: [endEmbed],
            components: []
        });

        delete message.gameState;
    };

    // ==================== HIT ====================

    if (action === 'hit') {
        playerHand.push(drawCard());

        const playerValue = calculateHandValue(playerHand);

        if (playerValue > 21) {
            return finishGame('lose');
        }

        if (playerValue === 21) {
            return finishGame('win_21');
        }
    }

    // ==================== DOUBLE ====================

    if (action === 'double') {
        if (user.cash < betAmount) {
            return interaction.followUp({
                content: '❌ אין לך מספיק כסף בקופה כדי לבצע Double!',
                ephemeral: true
            });
        }

        user.cash -= betAmount;

        betAmount *= 2;
        gameState.betAmount = betAmount;

        playerHand.push(drawCard());

        const playerValue = calculateHandValue(playerHand);

        if (playerValue > 21) {
            return finishGame('lose');
        }

        let dealerValue = calculateHandValue(dealerHand);

        while (dealerValue < 17) {
            dealerHand.push(drawCard());
            dealerValue = calculateHandValue(dealerHand);
        }

        if (dealerValue > 21 || playerValue > dealerValue) {
            return finishGame(
                playerValue === 21 ? 'win_21' : 'win'
            );
        }

        if (playerValue < dealerValue) {
            return finishGame('lose');
        }

        return finishGame('tie');
    }

    // ==================== STAND ====================

    if (action === 'stand') {
        let dealerValue = calculateHandValue(dealerHand);

        while (dealerValue < 17) {
            dealerHand.push(drawCard());
            dealerValue = calculateHandValue(dealerHand);
        }

        const playerValue = calculateHandValue(playerHand);

        if (dealerValue > 21 || playerValue > dealerValue) {
            return finishGame(
                playerValue === 21 ? 'win_21' : 'win'
            );
        }

        if (playerValue < dealerValue) {
            return finishGame('lose');
        }

        return finishGame('tie');
    }

    // ==================== UPDATE GAME ====================

    const playerValue = calculateHandValue(playerHand);

    const updateEmbed = new EmbedBuilder()
        .setAuthor({
            name: `${interaction.user.username}'s Game`,
            iconURL: interaction.user.displayAvatarURL()
        })
        .setTitle('🃏 Blackjack')
        .setColor(0xFEE75C)
        .addFields(
            {
                name: 'Your Hand',
                value: playerHand
                    .map(card => `\` ${card} \``)
                    .join(', '),
                inline: false
            },
            {
                name: `Value: ${playerValue}`,
                value: '\u200b',
                inline: false
            },
            {
                name: 'Dealer',
                value: formatHand(dealerHand, true),
                inline: false
            },
            {
                name: `Value: ${calculateHandValue([dealerHand[0]])}`,
                value: '\u200b',
                inline: false
            }
        );

    await interaction.editReply({
        embeds: [updateEmbed]
    });
}

// ==================== EXPORTS ====================

module.exports = {
    blackjack,
    handleBlackjackButton
};