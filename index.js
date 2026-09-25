const {
    Client,
    GatewayIntentBits,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle,
    PermissionFlagsBits
} = require('discord.js');

const express = require('express');

// ==========================================
// 1. Render Web Server
// ==========================================
const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
    res.send('Casino Bot is Online 24/7!');
});

app.listen(port, () => {
    console.log(`Web server listening on port ${port}`);
});

// ==========================================
// 2. Discord Client
// ==========================================
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

// ==========================================
// 3. Temporary Database
// ==========================================
const db = {
    users: {},
    currency: '💸',
    casinoRole: null
};

function getUserData(userId) {
    if (!db.users[userId]) {
        db.users[userId] = {
            cash: 1000,
            bank: 0
        };
    }

    return db.users[userId];
}

function hasManagerPermission(message) {
    if (!message.member) return false;

    if (
        message.member.permissions.has(
            PermissionFlagsBits.Administrator
        )
    ) {
        return true;
    }

    if (
        db.casinoRole &&
        message.member.roles.cache.has(db.casinoRole)
    ) {
        return true;
    }

    return false;
}

// ==========================================
// Blackjack
// ==========================================
function createDeck() {
    const suits = ['♠️', '♥️', '♦️', '♣️'];

    const values = [
        { name: '2', value: 2 },
        { name: '3', value: 3 },
        { name: '4', value: 4 },
        { name: '5', value: 5 },
        { name: '6', value: 6 },
        { name: '7', value: 7 },
        { name: '8', value: 8 },
        { name: '9', value: 9 },
        { name: '10', value: 10 },
        { name: 'J', value: 10 },
        { name: 'Q', value: 10 },
        { name: 'K', value: 10 },
        { name: 'A', value: 11 }
    ];

    const deck = [];

    for (const suit of suits) {
        for (const val of values) {
            deck.push({
                ...val,
                suit
            });
        }
    }

    for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
    }

    return deck;
}

function calculateHand(hand) {
    let value = hand.reduce(
        (sum, card) => sum + card.value,
        0
    );

    let aces = hand.filter(
        card => card.name === 'A'
    ).length;

    while (value > 21 && aces > 0) {
        value -= 10;
        aces--;
    }

    return value;
}

// ==========================================
// Commands
// ==========================================
const PREFIX = '$';
const minBet = 150;

client.on('messageCreate', async (message) => {
    if (
        message.author.bot ||
        !message.content.startsWith(PREFIX)
    ) {
        return;
    }

    const args = message.content
        .slice(PREFIX.length)
        .trim()
        .split(/ +/);

    const command = args.shift()?.toLowerCase();
    const userId = message.author.id;

    // ==========================================
    // Currency
    // ==========================================
    if (command === 'currency') {
        if (!hasManagerPermission(message)) {
            return message.reply(
                "❌ You don't have permission to use this command."
            );
        }

        const newEmoji = args[0];

        if (!newEmoji) {
            return message.reply(
                `Usage: ${PREFIX}currency [emoji]`
            );
        }

        db.currency = newEmoji;

        return message.reply(
            `✅ Currency icon has been changed to ${db.currency} across the whole bot!`
        );
    }

    // ==========================================
    // Casino Role
    // ==========================================
    if (command === 'casino') {
        if (
            !message.member.permissions.has(
                PermissionFlagsBits.Administrator
            )
        ) {
            return message.reply(
                "❌ Only Server Admins can set the Casino Role."
            );
        }

        if (args[0] === 'role') {
            const role =
                message.mentions.roles.first() ||
                message.guild.roles.cache.get(args[1]);

            if (!role) {
                return message.reply(
                    `Usage: ${PREFIX}casino role [@Role or RoleID]`
                );
            }

            db.casinoRole = role.id;

            return message.reply(
                `✅ Casino management access granted to role: **${role.name}**`
            );
        }
    }

    // ==========================================
    // Add Money
    // ==========================================
    if (command === 'addmoney') {
        if (!hasManagerPermission(message)) {
            return message.reply("❌ Access Denied.");
        }

        const type = args[0]?.toLowerCase();

        const target =
            message.mentions.users.first() ||
            message.guild.members.cache.get(args[1])?.user;

        const amount = parseInt(args[2]);

        if (
            !['cash', 'bank'].includes(type) ||
            !target ||
            isNaN(amount) ||
            amount <= 0
        ) {
            return message.reply(
                `Usage: ${PREFIX}addmoney [cash/bank] [@user] [amount]`
            );
        }

        const targetData = getUserData(target.id);

        if (type === 'cash') {
            targetData.cash += amount;
        } else {
            targetData.bank += amount;
        }

        return message.reply(
            `✅ Successfully added **${amount.toLocaleString()}** ${db.currency} to ${target.username}'s ${type}.`
        );
    }

    // ==========================================
    // Deposit
    // ==========================================
    if (
        command === 'dep' ||
        command === 'deposit'
    ) {
        const user = getUserData(userId);

        let amount = args[0];

        if (amount === 'all') {
            amount = user.cash;
        } else {
            amount = parseInt(amount);
        }

        if (
            isNaN(amount) ||
            amount <= 0 ||
            user.cash < amount
        ) {
            return message.reply(
                "Invalid amount or insufficient cash."
            );
        }

        user.cash -= amount;
        user.bank += amount;

        const embed = new EmbedBuilder()
            .setAuthor({
                name: message.author.username,
                iconURL: message.author.displayAvatarURL()
            })
            .setColor('#2ecc71')
            .setDescription(
                `Successfully deposited **${amount.toLocaleString()}** ${db.currency} to your bank account.`
            );

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // Withdraw
    // ==========================================
    if (
        command === 'with' ||
        command === 'withdraw'
    ) {
        const user = getUserData(userId);

        let amount = args[0];

        if (amount === 'all') {
            amount = user.bank;
        } else {
            amount = parseInt(amount);
        }

        if (
            isNaN(amount) ||
            amount <= 0 ||
            user.bank < amount
        ) {
            return message.reply(
                "Invalid amount or insufficient bank balance."
            );
        }

        user.bank -= amount;
        user.cash += amount;

        const embed = new EmbedBuilder()
            .setAuthor({
                name: message.author.username,
                iconURL: message.author.displayAvatarURL()
            })
            .setColor('#2ecc71')
            .setDescription(
                `Successfully withdrew **${amount.toLocaleString()}** ${db.currency} from your bank account.`
            );

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // Balance
    // ==========================================
    if (
        command === 'bal' ||
        command === 'balance'
    ) {
        const target =
            message.mentions.users.first() ||
            message.author;

        const user = getUserData(target.id);

        const embed = new EmbedBuilder()
            .setAuthor({
                name: `${target.username}'s Balance`,
                iconURL: target.displayAvatarURL()
            })
            .setColor('#f1c40f')
            .addFields(
                {
                    name: '💵 Cash',
                    value: `${user.cash.toLocaleString()} ${db.currency}`,
                    inline: true
                },
                {
                    name: '🏦 Bank',
                    value: `${user.bank.toLocaleString()} ${db.currency}`,
                    inline: true
                },
                {
                    name: '📊 Total',
                    value: `**${(
                        user.cash + user.bank
                    ).toLocaleString()}** ${db.currency}`,
                    inline: false
                }
            );

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // Leaderboard
    // ==========================================
    if (
        command === 'lb' ||
        command === 'leaderboard'
    ) {
        const sub = args[0]?.toLowerCase();

        let sorted = Object.keys(db.users).map(id => ({
            id,
            cash: db.users[id].cash,
            bank: db.users[id].bank,
            total:
                db.users[id].cash +
                db.users[id].bank
        }));

        if (sub === 'cash') {
            sorted.sort(
                (a, b) => b.cash - a.cash
            );
        } else {
            sorted.sort(
                (a, b) => b.total - a.total
            );
        }

        let description = '';

        for (
            let i = 0;
            i < Math.min(sorted.length, 10);
            i++
        ) {
            const userObj =
                await client.users
                    .fetch(sorted[i].id)
                    .catch(() => null);

            if (!userObj) continue;

            const amount =
                sub === 'cash'
                    ? sorted[i].cash
                    : sorted[i].total;

            description +=
                `**#${i + 1}** | ${userObj.username} - ${amount.toLocaleString()} ${db.currency}\n`;
        }

        const embed = new EmbedBuilder()
            .setTitle(
                `🏆 Rich Leaderboard (${sub === 'cash' ? 'Top Cash' : 'Top Total'})`
            )
            .setColor('#f1c40f')
            .setDescription(
                description || 'No players yet.'
            );

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // BLACKJACK
    // ==========================================
    if (
        command === 'bj' ||
        command === 'blackjack'
    ) {
        const user = getUserData(userId);
        const bet = parseInt(args[0]);

        if (
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `❌ Minimum bet for Blackjack is **${minBet}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ You don't have enough cash."
            );
        }

        user.cash -= bet;

        let totalBet = bet;

        const deck = createDeck();

        let playerHand;
        let dealerHand;

        if (Math.random() < 0.20) {
            playerHand = [
                {
                    name: 'A',
                    value: 11,
                    suit: '♥️'
                },
                {
                    name: '10',
                    value: 10,
                    suit: '♠️'
                }
            ];

            dealerHand = [
                deck.pop(),
                deck.pop()
            ];
        } else {
            playerHand = [
                deck.pop(),
                deck.pop()
            ];

            dealerHand = [
                deck.pop(),
                deck.pop()
            ];
        }

        const getStatusEmbed = (
            finished = false
        ) => {
            const pVal =
                calculateHand(playerHand);

            const dVal =
                calculateHand(dealerHand);

            const dealerString = finished
                ? dealerHand
                      .map(
                          c =>
                              `[${c.name}${c.suit}]`
                      )
                      .join(', ') +
                  `\n\nValue: **${dVal}**`
                : `[${dealerHand[0].name}${dealerHand[0].suit}], [?]\n\nValue: **${dealerHand[0].value}**`;

            return new EmbedBuilder()
                .setAuthor({
                    name: `${message.author.username}'s Game`,
                    iconURL:
                        message.author.displayAvatarURL()
                })
                .setTitle(
                    '🃏 Blackjack 🃏'
                )
                .setColor('#f1c40f')
                .addFields(
                    {
                        name: 'Your Hand',
                        value:
                            playerHand
                                .map(
                                    c =>
                                        `**${c.name}**`
                                )
                                .join(', ') +
                            `\n\nValue: **${pVal}**`,
                        inline: false
                    },
                    {
                        name: 'Dealer',
                        value: dealerString,
                        inline: false
                    }
                );
        };

        const row =
            new ActionRowBuilder()
                .addComponents(
                    new ButtonBuilder()
                        .setCustomId('hit')
                        .setLabel('Hit')
                        .setStyle(
                            ButtonStyle.Primary
                        ),

                    new ButtonBuilder()
                        .setCustomId('stand')
                        .setLabel('Stand')
                        .setStyle(
                            ButtonStyle.Success
                        ),

                    new ButtonBuilder()
                        .setCustomId('double')
                        .setLabel('Double')
                        .setStyle(
                            ButtonStyle.Danger
                        )
                );

        const msg =
            await message.reply({
                embeds: [
                    getStatusEmbed()
                ],
                components: [row]
            });

        const filter =
            i => i.user.id === userId;

        const collector =
            msg.createMessageComponentCollector({
                filter,
                time: 60000
            });

        collector.on(
            'collect',
            async i => {
                await i.deferUpdate();

                if (
                    i.customId === 'double'
                ) {
                    if (
                        user.cash < bet
                    ) {
                        return message.followUp(
                            {
                                content:
                                    "Not enough cash to double!",
                                ephemeral: true
                            }
                        );
                    }

                    user.cash -= bet;
                    totalBet += bet;

                    playerHand.push(
                        deck.pop()
                    );

                    collector.stop(
                        'double'
                    );

                    return;
                }

                if (
                    i.customId === 'hit'
                ) {
                    playerHand.push(
                        deck.pop()
                    );

                    if (
                        calculateHand(
                            playerHand
                        ) > 21
                    ) {
                        collector.stop(
                            'bust'
                        );
                    } else {
                        await msg.edit({
                            embeds: [
                                getStatusEmbed()
                            ]
                        });
                    }

                    return;
                }

                if (
                    i.customId === 'stand'
                ) {
                    collector.stop(
                        'stand'
                    );
                }
            }
        );

        collector.on(
            'end',
            async (
                collected,
                reason
            ) => {
                if (
                    reason === 'stand' ||
                    reason === 'double'
                ) {
                    while (
                        calculateHand(
                            dealerHand
                        ) < 17
                    ) {
                        dealerHand.push(
                            deck.pop()
                        );
                    }
                }

                const pVal =
                    calculateHand(
                        playerHand
                    );

                const dVal =
                    calculateHand(
                        dealerHand
                    );

                const finalEmbed =
                    getStatusEmbed(true);

                let winAmount = 0;
                let outcomeMessage = '';

                if (pVal > 21) {
                    outcomeMessage =
                        `❌ You busted and lost **${totalBet.toLocaleString()}** ${db.currency}`;
                } else if (dVal > 21) {
                    winAmount =
                        totalBet * 2;

                    outcomeMessage =
                        `🎉 Dealer busted! You won **${winAmount.toLocaleString()}** ${db.currency}`;
                } else if (pVal > dVal) {
                    winAmount =
                        totalBet * 2;

                    if (
                        pVal === 21 &&
                        playerHand.length === 2
                    ) {
                        winAmount =
                            Math.floor(
                                totalBet * 2.5
                            );
                    }

                    outcomeMessage =
                        `🎉 You won! You got **${winAmount.toLocaleString()}** ${db.currency}`;
                } else if (pVal < dVal) {
                    if (
                        dVal - pVal === 1 &&
                        Math.random() < 0.3
                    ) {
                        winAmount =
                            totalBet;

                        outcomeMessage =
                            `🤝 Saved by luck! It's a Tie. Your bet of **${totalBet.toLocaleString()}** ${db.currency} was returned.`;
                    } else {
                        outcomeMessage =
                            `❌ You lost **${totalBet.toLocaleString()}** ${db.currency}`;
                    }
                } else {
                    winAmount =
                        totalBet;

                    outcomeMessage =
                        `🤝 It's a Tie! Returned **${totalBet.toLocaleString()}** ${db.currency}`;
                }

                user.cash += winAmount;

                finalEmbed.setDescription(
                    outcomeMessage
                );

                await msg.edit({
                    embeds: [
                        finalEmbed
                    ],
                    components: []
                });
            }
        );

        return;
    }

    // ==========================================
    // COCKFIGHT
    // ==========================================
    if (
        command === 'cf' ||
        command === 'cockfight' ||
        command === 'chickenfight'
    ) {
        const user =
            getUserData(userId);

        const bet =
            parseInt(args[0]);

        if (
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `❌ Minimum bet is **${minBet}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const strength =
            Math.floor(
                Math.random() * 28
            ) + 55;

        const isWin =
            Math.random() <
            strength / 100;

        const embed =
            new EmbedBuilder()
                .setAuthor({
                    name: message.author.username,
                    iconURL:
                        message.author.displayAvatarURL()
                });

        if (isWin) {
            const winAmt =
                bet * 2;

            user.cash += winAmt;

            embed
                .setColor('#2ecc71')
                .setDescription(
                    `Your chicken won the fight, you won **${bet.toLocaleString()}** ${db.currency} 🐓!\n\n**Your chicken's strength (chance of winning):** ${strength}%\nYou now have **${user.cash.toLocaleString()}** ${db.currency}`
                );
        } else {
            embed
                .setColor('#e74c3c')
                .setDescription(
                    `Your chicken lost the fight... You lost **${bet.toLocaleString()}** ${db.currency} 🐓.`
                );
        }

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // COINFLIP
    // ==========================================
    if (
        command === 'ht' ||
        command === 'coinflip'
    ) {
        const user =
            getUserData(userId);

        const choice =
            args[0]?.toLowerCase();

        const bet =
            parseInt(args[1]);

        if (
            !['heads', 'tails'].includes(
                choice
            ) ||
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `Usage: ${PREFIX}ht [heads/tails] [amount] (Min bet: ${minBet})`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const result =
            Math.random() < 0.5
                ? 'heads'
                : 'tails';

        const embed =
            new EmbedBuilder()
                .setAuthor({
                    name: message.author.username,
                    iconURL:
                        message.author.displayAvatarURL()
                });

        if (
            choice === result
        ) {
            user.cash += bet * 2;

            embed
                .setColor('#2ecc71')
                .setDescription(
                    `🪙 The coin landed on **${result}**! You won **${(
                        bet * 2
                    ).toLocaleString()}** ${db.currency}.`
                );
        } else {
            embed
                .setColor('#e74c3c')
                .setDescription(
                    `🪙 The coin landed on **${result}**! You lost **${bet.toLocaleString()}** ${db.currency}.`
                );
        }

        return message.reply({
            embeds: [embed]
        });
    }

    // ==========================================
    // HIGHER / LOWER
    // ==========================================
    if (
        command === 'hl' ||
        command === 'higherlower'
    ) {
        const user =
            getUserData(userId);

        const bet =
            parseInt(args[0]);

        if (
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `❌ Minimum bet is **${minBet}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const num1 =
            Math.floor(
                Math.random() * 12
            ) + 1;

        const embed =
            new EmbedBuilder()
                .setTitle(
                    '🎲 Higher or Lower 🎲'
                )
                .setColor('#9b59b6')
                .setDescription(
                    `**Betting Amount:** ${bet}\n\n**1 :** ${num1}\n**2 :** ❓\n\n**Higher:** 1.5x\n**Same:** 25x\n**Lower:** 1.5x`
                );

        const row =
            new ActionRowBuilder()
                .addComponents(
                    new ButtonBuilder()
                        .setCustomId(
                            'higher'
                        )
                        .setLabel('Higher')
                        .setStyle(
                            ButtonStyle.Primary
                        ),

                    new ButtonBuilder()
                        .setCustomId(
                            'same'
                        )
                        .setLabel('Same')
                        .setStyle(
                            ButtonStyle.Secondary
                        ),

                    new ButtonBuilder()
                        .setCustomId(
                            'lower'
                        )
                        .setLabel('Lower')
                        .setStyle(
                            ButtonStyle.Primary
                        )
                );

        const msg =
            await message.reply({
                embeds: [embed],
                components: [row]
            });

        const filter =
            i => i.user.id === userId;

        const interaction =
            await msg
                .awaitMessageComponent({
                    filter,
                    time: 30000
                })
                .catch(() => null);

        if (!interaction) {
            user.cash += bet;

            return msg.edit({
                content:
                    'Game timed out! Your bet was returned.',
                components: []
            });
        }

        await interaction.deferUpdate();

        const num2 =
            Math.floor(
                Math.random() * 12
            ) + 1;

        let won = false;
        let payoutMultiplier = 0;

        if (
            interaction.customId ===
                'higher' &&
            num2 > num1
        ) {
            won = true;
            payoutMultiplier = 1.5;
        } else if (
            interaction.customId ===
                'lower' &&
            num2 < num1
        ) {
            won = true;
            payoutMultiplier = 1.5;
        } else if (
            interaction.customId ===
                'same' &&
            num2 === num1
        ) {
            won = true;
            payoutMultiplier = 25;
        }

        const finalEmbed =
            new EmbedBuilder()
                .setTitle(
                    '🎲 Higher or Lower Result 🎲'
                )
                .setAuthor({
                    name:
                        message.author.username,
                    iconURL:
                        message.author.displayAvatarURL()
                });

        if (won) {
            const winnings =
                Math.floor(
                    bet *
                        payoutMultiplier
                );

            user.cash += winnings;

            finalEmbed
                .setColor('#2ecc71')
                .setDescription(
                    `**1 :** ${num1}\n**2 :** **${num2}**\n\n🎉 Correct! You won **${winnings.toLocaleString()}** ${db.currency}!`
                );
        } else {
            finalEmbed
                .setColor('#e74c3c')
                .setDescription(
                    `**1 :** ${num1}\n**2 :** **${num2}**\n\n❌ Wrong guess! You lost **${bet.toLocaleString()}** ${db.currency}.`
                );
        }

        return msg.edit({
            embeds: [finalEmbed],
            components: []
        });
    }

    // ==========================================
    // MINES
    // ==========================================
    if (command === 'mines') {
        const user =
            getUserData(userId);

        const bet =
            parseInt(args[0]);

        if (
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `❌ Minimum bet is **${minBet}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const bombIndex =
            Math.floor(
                Math.random() * 9
            );

        const multipliers = [
            1.1,
            1.2,
            1.4,
            1.6,
            2.0,
            2.6,
            3.6,
            8.0
        ];

        let clicks = 0;
        let revealedTiles = [];

        const getGridRows = (
            revealed = [],
            showBombs = false
        ) => {
            const rows = [];
            let buttons = [];

            for (
                let i = 0;
                i < 9;
                i++
            ) {
                const btn =
                    new ButtonBuilder()
                        .setCustomId(
                            `mine_${i}`
                        );

                if (
                    showBombs &&
                    i === bombIndex
                ) {
                    btn
                        .setEmoji('💣')
                        .setStyle(
                            ButtonStyle.Danger
                        )
                        .setDisabled(true);
                } else if (
                    revealed.includes(i)
                ) {
                    btn
                        .setEmoji('💎')
                        .setStyle(
                            ButtonStyle.Success
                        )
                        .setDisabled(true);
                } else {
                    btn
                        .setEmoji('⬛')
                        .setStyle(
                            ButtonStyle.Secondary
                        )
                        .setDisabled(
                            showBombs
                        );
                }

                buttons.push(btn);

                if (
                    buttons.length === 3
                ) {
                    rows.push(
                        new ActionRowBuilder()
                            .addComponents(
                                buttons
                            )
                    );

                    buttons = [];
                }
            }

            const currentProfit =
                clicks > 0
                    ? Math.floor(
                          bet *
                              multipliers[
                                  clicks - 1
                              ]
                      ) - bet
                    : 0;

            const cashoutRow =
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId(
                                'cashout'
                            )
                            .setLabel(
                                'Cashout'
                            )
                            .setStyle(
                                ButtonStyle.Success
                            )
                            .setDisabled(
                                clicks === 0 ||
                                    showBombs
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                'profit'
                            )
                            .setLabel(
                                `Profit: ${currentProfit} ${db.currency}`
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            )
                            .setDisabled(
                                true
                            )
                    );

            rows.push(cashoutRow);

            return rows;
        };

        const embed =
            new EmbedBuilder()
                .setAuthor({
                    name:
                        message.author.username,
                    iconURL:
                        message.author.displayAvatarURL()
                })
                .setTitle(
                    '💣 Mines 3x3 💣'
                )
                .setColor('#f1c40f')
                .setDescription(
                    `Find diamonds and avoid the single bomb!\nNext Multiplier: **${multipliers[0]}x**`
                );

        const msg =
            await message.reply({
                embeds: [embed],
                components:
                    getGridRows()
            });

        const filter =
            i => i.user.id === userId;

        const collector =
            msg.createMessageComponentCollector({
                filter,
                time: 120000
            });

        collector.on(
            'collect',
            async i => {
                await i.deferUpdate();

                if (
                    i.customId ===
                    'cashout'
                ) {
                    collector.stop(
                        'cashout'
                    );
                    return;
                }

                if (
                    i.customId ===
                    'profit'
                ) {
                    return;
                }

                const tileIndex =
                    parseInt(
                        i.customId.split(
                            '_'
                        )[1]
                    );

                if (
                    revealedTiles.includes(
                        tileIndex
                    )
                ) {
                    return;
                }

                if (
                    tileIndex ===
                    bombIndex
                ) {
                    collector.stop(
                        'bomb'
                    );
                    return;
                }

                revealedTiles.push(
                    tileIndex
                );

                clicks++;

                if (clicks === 8) {
                    collector.stop(
                        'max_win'
                    );
                    return;
                }

                const nextMult =
                    multipliers[
                        clicks
                    ];

                const currentTotalWin =
                    Math.floor(
                        bet *
                            multipliers[
                                clicks - 1
                            ]
                    );

                embed.setDescription(
                    `💎 Nice! Current total win: **${currentTotalWin.toLocaleString()}** ${db.currency}\nNext Multiplier: **${nextMult}x**`
                );

                await msg.edit({
                    embeds: [embed],
                    components:
                        getGridRows(
                            revealedTiles
                        )
                });
            }
        );

        collector.on(
            'end',
            async (
                collected,
                reason
            ) => {
                const finalEmbed =
                    new EmbedBuilder()
                        .setAuthor({
                            name:
                                message.author.username,
                            iconURL:
                                message.author.displayAvatarURL()
                        });

                if (
                    reason === 'bomb'
                ) {
                    finalEmbed
                        .setColor(
                            '#e74c3c'
                        )
                        .setTitle(
                            '💣 You hit a bomb!'
                        )
                        .setDescription(
                            `- You lost **${bet.toLocaleString()}** ${db.currency}\n\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.`
                        );

                    return msg.edit({
                        embeds: [
                            finalEmbed
                        ],
                        components:
                            getGridRows(
                                revealedTiles,
                                true
                            )
                    });
                }

                if (
                    reason ===
                        'cashout' ||
                    reason ===
                        'max_win'
                ) {
                    const multiplier =
                        multipliers[
                            clicks - 1
                        ];

                    const payout =
                        Math.floor(
                            bet *
                                multiplier
                        );

                    user.cash += payout;

                    finalEmbed
                        .setColor(
                            '#2ecc71'
                        )
                        .setTitle(
                            '💰 You cashed out!'
                        )
                        .setDescription(
                            `+ You won and got **${payout.toLocaleString()}** ${db.currency}\n\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.`
                        );

                    return msg.edit({
                        embeds: [
                            finalEmbed
                        ],
                        components:
                            getGridRows(
                                revealedTiles,
                                true
                            )
                    });
                }

                finalEmbed
                    .setColor('#e74c3c')
                    .setTitle(
                        '⏰ Game Timed Out'
                    )
                    .setDescription(
                        `The game timed out.\n\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.`
                    );

                return msg.edit({
                    embeds: [
                        finalEmbed
                    ],
                    components: []
                });
            }
        );

        return;
    }

    // ==========================================
    // MONEY TOWER
    // ==========================================
    if (
        command === 'mt' ||
        command === 'moneytower'
    ) {
        const user =
            getUserData(userId);

        const bet =
            parseInt(args[0]);

        if (
            isNaN(bet) ||
            bet < minBet
        ) {
            return message.reply(
                `❌ Minimum bet is **${minBet}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const mtMultipliers = [
            1.5,
            2.1,
            2.3,
            3.6,
            7.6
        ];

        let currentFloor = 0;

        const towerData = [];

        for (
            let f = 0;
            f < 5;
            f++
        ) {
            towerData.push(
                Math.floor(
                    Math.random() * 3
                )
            );
        }

        /*
         * Discord max = 5 Action Rows.
         * Therefore the Cashout button is placed
         * inside the current floor row.
         */

        const getTowerRows = (
            activeFloor,
            chosenTile = null,
            failed = false
        ) => {
            const rows = [];

            for (
                let f = 4;
                f >= 0;
                f--
            ) {
                const buttons = [];

                for (
                    let t = 0;
                    t < 3;
                    t++
                ) {
                    const btn =
                        new ButtonBuilder()
                            .setCustomId(
                                `mt_${f}_${t}`
                            );

                    if (
                        f < activeFloor
                    ) {
                        if (
                            t ===
                            towerData[f]
                        ) {
                            btn
                                .setEmoji(
                                    '💣'
                                )
                                .setStyle(
                                    ButtonStyle.Danger
                                );
                        } else {
                            btn
                                .setEmoji(
                                    '💵'
                                )
                                .setStyle(
                                    ButtonStyle.Success
                                );
                        }

                        btn.setDisabled(
                            true
                        );
                    } else if (
                        f === activeFloor
                    ) {
                        if (
                            failed &&
                            t ===
                                chosenTile
                        ) {
                            btn
                                .setEmoji(
                                    '💣'
                                )
                                .setStyle(
                                    ButtonStyle.Danger
                                )
                                .setDisabled(
                                    true
                                );
                        } else if (
                            chosenTile !==
                                null &&
                            t ===
                                chosenTile
                        ) {
                            btn
                                .setEmoji(
                                    '💵'
                                )
                                .setStyle(
                                    ButtonStyle.Success
                                )
                                .setDisabled(
                                    true
                                );
                        } else {
                            btn
                                .setEmoji(
                                    '❓'
                                )
                                .setStyle(
                                    ButtonStyle.Primary
                                )
                                .setDisabled(
                                    failed
                                );
                        }
                    } else {
                        btn
                            .setEmoji(
                                '🔒'
                            )
                            .setStyle(
                                ButtonStyle.Secondary
                            )
                            .setDisabled(
                                true
                            );
                    }

                    buttons.push(btn);
                }

                // Add Cashout to the current floor
                // while keeping max 5 Action Rows.
                if (
                    f === activeFloor &&
                    activeFloor > 0
                ) {
                    buttons[2] =
                        new ButtonBuilder()
                            .setCustomId(
                                'mt_cashout'
                            )
                            .setLabel(
                                'Cashout'
                            )
                            .setStyle(
                                ButtonStyle.Success
                            )
                            .setDisabled(
                                failed
                            );
                }

                rows.push(
                    new ActionRowBuilder()
                        .addComponents(
                            buttons
                        )
                );
            }

            return rows;
        };

        const embed =
            new EmbedBuilder()
                .setAuthor({
                    name:
                        message.author.username,
                    iconURL:
                        message.author.displayAvatarURL()
                })
                .setTitle(
                    '🏢 Money Tower 🏢'
                )
                .setColor('#f1c40f')
                .setDescription(
                    `Climb the 5-row tower! Each row has 1 Bomb and 2 Cash slots.\n\nNext Multiplier: **${mtMultipliers[0]}x**`
                );

        const msg =
            await message.reply({
                embeds: [embed],
                components:
                    getTowerRows(
                        currentFloor
                    )
            });

        const filter =
            i => i.user.id === userId;

        const collector =
            msg.createMessageComponentCollector({
                filter,
                time: 120000
            });

        collector.on(
            'collect',
            async i => {
                await i.deferUpdate();

                if (
                    i.customId ===
                    'mt_cashout'
                ) {
                    collector.stop(
                        'cashout'
                    );
                    return;
                }

                const parts =
                    i.customId.split(
                        '_'
                    );

                if (
                    parts[0] !== 'mt'
                ) {
                    return;
                }

                const clickedFloor =
                    parseInt(
                        parts[1]
                    );

                const clickedTile =
                    parseInt(
                        parts[2]
                    );

                if (
                    clickedFloor !==
                    currentFloor
                ) {
                    return;
                }

                if (
                    clickedTile ===
                    towerData[
                        currentFloor
                    ]
                ) {
                    collector.stop(
                        'bomb'
                    );
                    return;
                }

                currentFloor++;

                if (
                    currentFloor ===
                    5
                ) {
                    collector.stop(
                        'max_win'
                    );
                    return;
                }

                embed.setDescription(
                    `You climbed **${currentFloor}** rows!\nNext Multiplier: **${mtMultipliers[currentFloor]}x**`
                );

                await msg.edit({
                    embeds: [embed],
                    components:
                        getTowerRows(
                            currentFloor
                        )
                });
            }
        );

        collector.on(
            'end',
            async (
                collected,
                reason
            ) => {
                const finalEmbed =
                    new EmbedBuilder()
                        .setAuthor({
                            name:
                                message.author.username,
                            iconURL:
                                message.author.displayAvatarURL()
                        });

                if (
                    reason === 'bomb'
                ) {
                    finalEmbed
                        .setColor(
                            '#e74c3c'
                        )
                        .setTitle(
                            '💣 You hit a bomb!'
                        )
                        .setDescription(
                            `- You lost **${bet.toLocaleString()}** ${db.currency}\nYou climbed ${currentFloor} rows.`
                        );

                    return msg.edit({
                        embeds: [
                            finalEmbed
                        ],
                        components:
                            getTowerRows(
                                currentFloor,
                                towerData[
                                    currentFloor
                                ],
                                true
                            )
                    });
                }

                if (
                    reason ===
                    'cashout'
                ) {
                    const multiplier =
                        mtMultipliers[
                            currentFloor - 1
                        ];

                    const payout =
                        Math.floor(
                            bet *
                                multiplier
                        );

                    user.cash += payout;

                    finalEmbed
                        .setColor(
                            '#2ecc71'
                        )
                        .setTitle(
                            '💰 You cashed out!'
                        )
                        .setDescription(
                            `+ You won and got **${payout.toLocaleString()}** ${db.currency}\nYou climbed ${currentFloor} rows successfully!`
                        );

                    return msg.edit({
                        embeds: [
                            finalEmbed
                        ],
                        components:
                            getTowerRows(
                                currentFloor
                            )
                    });
                }

                if (
                    reason ===
                    'max_win'
                ) {
                    const payout =
                        Math.floor(
                            bet *
                                mtMultipliers[4]
                        );

                    user.cash += payout;

                    finalEmbed
                        .setColor(
                            '#2ecc71'
                        )
                        .setTitle(
                            '🏆 Top of the Tower!'
                        )
                        .setDescription(
                            `+ You won and got **${payout.toLocaleString()}** ${db.currency}\nYou climbed 5 rows successfully!`
                        );

                    return msg.edit({
                        embeds: [
                            finalEmbed
                        ],
                        components: []
                    });
                }

                finalEmbed
                    .setColor('#e74c3c')
                    .setTitle(
                        '⏰ Game Timed Out'
                    )
                    .setDescription(
                        `The game timed out.\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.`
                    );

                return msg.edit({
                    embeds: [
                        finalEmbed
                    ],
                    components: []
                });
            }
        );

        return;
    }
});

// ==========================================
// Bot Login
// ==========================================
client.login(process.env.DISCORD_TOKEN);