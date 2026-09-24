const {
    Client,
    GatewayIntentBits,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle,
    ComponentType
} = require('discord.js');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

const PREFIX = '$';

let balances = {};
let casinoRole = null;
let serverCurrency = '💸';

function getUserData(userId) {
    if (!balances[userId]) {
        balances[userId] = {
            cash: 0,
            bank: 0
        };
    }

    return balances[userId];
}

function hasCasinoAccess(message) {
    if (!message.member) return false;

    if (message.member.permissions.has('Administrator')) {
        return true;
    }

    if (casinoRole && message.member.roles.cache.has(casinoRole)) {
        return true;
    }

    return false;
}

client.once('ready', () => {
    console.log(`Bot ${client.user.tag} is online!`);
});

client.on('messageCreate', async (message) => {
    try {
        if (
            message.author.bot ||
            !message.content.startsWith(PREFIX)
        ) {
            return;
        }

        const args = message.content
            .slice(PREFIX.length)
            .trim()
            .split(/\s+/);

        const command = args.shift().toLowerCase();

        // =========================
        // ROLE-CASINO
        // =========================

        if (command === 'role-casino') {
            if (!message.member.permissions.has('Administrator')) {
                return message.reply('❌ No admin perms.');
            }

            const role = message.mentions.roles.first();

            if (!role) {
                return message.reply('❌ Mention a role.');
            }

            casinoRole = role.id;

            return message.reply(
                `✅ Casino role set to: **${role.name}**`
            );
        }

        // =========================
        // ADD MONEY
        // =========================

        if (command === 'addmoney') {
            if (!hasCasinoAccess(message)) {
                return message.reply('❌ Staff only.');
            }

            const target = message.mentions.users.first();
            const type = args[0]?.toLowerCase();
            const amount = parseInt(args[1]);

            if (
                !target ||
                !type ||
                isNaN(amount) ||
                amount <= 0 ||
                !['cash', 'bank'].includes(type)
            ) {
                return message.reply(
                    '❌ Use: `$addmoney @user [cash/bank] [amount]`'
                );
            }

            const data = getUserData(target.id);
            data[type] += amount;

            return message.reply(
                `✅ Added **${amount.toLocaleString()}** ${serverCurrency} to ${target.username}'s ${type}.`
            );
        }

        // =========================
        // SET CURRENCY
        // =========================

        if (command === 'setcurrency') {
            if (!hasCasinoAccess(message)) {
                return message.reply('❌ Staff only.');
            }

            const newCurrency = args[0];

            if (!newCurrency) {
                return message.reply('❌ Provide a currency emoji.');
            }

            serverCurrency = newCurrency;

            return message.reply(
                `✅ Currency set to: ${serverCurrency}`
            );
        }

        // =========================
        // BALANCE
        // =========================

        if (command === 'bal' || command === 'balance') {
            const targetUser =
                message.mentions.users.first() || message.author;

            const data = getUserData(targetUser.id);
            const total = data.cash + data.bank;

            const embed = new EmbedBuilder()
                .setAuthor({
                    name: targetUser.username,
                    iconURL: targetUser.displayAvatarURL()
                })
                .setDescription(
                    `Use the \`$top\` command to view your rank.\n\n` +
                    `• **Money Out:** ${data.cash.toLocaleString()} ${serverCurrency}\n` +
                    `• **Bank Money:** ${data.bank.toLocaleString()} ${serverCurrency}\n` +
                    `• **Total Money:** ${total.toLocaleString()} ${serverCurrency}`
                )
                .setColor('#10a3de');

            return message.reply({
                embeds: [embed]
            });
        }

        // =========================
        // CHICKEN FIGHT
        // =========================

        if (
            command === 'cf' ||
            command === 'chickenfight'
        ) {
            const data = getUserData(message.author.id);

            const betInput = args[0];

            const bet =
                betInput?.toLowerCase() === 'all'
                    ? data.cash
                    : parseInt(betInput);

            if (isNaN(bet) || bet <= 0) {
                return message.reply('❌ Invalid bet.');
            }

            if (data.cash < bet) {
                return message.reply('❌ Not enough cash.');
            }

            const isWin = Math.random() < 0.52;

            if (isWin) {
                data.cash += bet;

                const embed = new EmbedBuilder()
                    .setAuthor({
                        name: message.author.username,
                        iconURL: message.author.displayAvatarURL()
                    })
                    .setDescription(
                        `Your chicken won the fight! 🎉\n\n` +
                        `You won **${bet.toLocaleString()} ${serverCurrency}** 🐔\n\n` +
                        `Your chicken's strength: **52%**\n` +
                        `You now have **${data.cash.toLocaleString()} ${serverCurrency}**`
                    )
                    .setColor('#2ecc71');

                return message.reply({
                    embeds: [embed]
                });
            }

            data.cash -= bet;

            const embed = new EmbedBuilder()
                .setAuthor({
                    name: message.author.username,
                    iconURL: message.author.displayAvatarURL()
                })
                .setDescription(
                    `Your chicken lost the fight... 💥🐔\n\n` +
                    `You lost **${bet.toLocaleString()} ${serverCurrency}**\n\n` +
                    `Your chicken's strength: **52%**\n` +
                    `You now have **${data.cash.toLocaleString()} ${serverCurrency}**`
                )
                .setColor('#e74c3c');

            return message.reply({
                embeds: [embed]
            });
        }

        // =========================
        // HIGHER / LOWER
        // =========================

        if (
            command === 'hilo' ||
            command === 'high-low'
        ) {
            const data = getUserData(message.author.id);
            const bet = parseInt(args[0]);

            if (isNaN(bet) || bet <= 0) {
                return message.reply('❌ Invalid bet.');
            }

            if (data.cash < bet) {
                return message.reply('❌ Not enough cash.');
            }

            const card1 = Math.floor(Math.random() * 13) + 1;
            const card2 = Math.floor(Math.random() * 13) + 1;

            const embed = new EmbedBuilder()
                .setTitle('🎲 Higher or Lower 🎲')
                .setDescription(
                    `**Betting Amount:** ${bet.toLocaleString()} ${serverCurrency}\n\n` +
                    `\`1:\` ${card1}\n` +
                    `\`2:\` ❓\n\n` +
                    `**Higher:** 1.5x\n` +
                    `**Same:** 8x\n` +
                    `**Lower:** 1.1x`
                )
                .setColor('#8e44ad');

            const row = new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId('higher')
                    .setLabel('Higher')
                    .setStyle(ButtonStyle.Primary),

                new ButtonBuilder()
                    .setCustomId('same')
                    .setLabel('Same')
                    .setStyle(ButtonStyle.Secondary),

                new ButtonBuilder()
                    .setCustomId('lower')
                    .setLabel('Lower')
                    .setStyle(ButtonStyle.Primary)
            );

            const reply = await message.reply({
                embeds: [embed],
                components: [row]
            });

            const collector =
                reply.createMessageComponentCollector({
                    componentType: ComponentType.Button,
                    time: 30000
                });

            collector.on('collect', async (i) => {
                if (i.user.id !== message.author.id) {
                    return i.reply({
                        content: '❌ This game belongs to someone else.',
                        ephemeral: true
                    });
                }

                collector.stop();

                const won =
                    (i.customId === 'higher' && card2 > card1) ||
                    (i.customId === 'lower' && card2 < card1) ||
                    (i.customId === 'same' && card2 === card1);

                const multiplier =
                    i.customId === 'same'
                        ? 8
                        : i.customId === 'higher'
                            ? 1.5
                            : 1.1;

                const resultEmbed = new EmbedBuilder()
                    .setTitle('🎲 Higher or Lower - Result 🎲')
                    .setColor(
                        won ? '#2ecc71' : '#e74c3c'
                    );

                if (won) {
                    const winAmount = Math.floor(
                        bet * multiplier
                    );

                    data.cash += winAmount - bet;

                    resultEmbed.setDescription(
                        `**Betting Amount:** ${bet.toLocaleString()} ${serverCurrency}\n\n` +
                        `\`1:\` ${card1}\n` +
                        `\`2:\` **${card2}**\n\n` +
                        `🎉 Won **${winAmount.toLocaleString()} ${serverCurrency}**`
                    );
                } else {
                    data.cash -= bet;

                    resultEmbed.setDescription(
                        `**Betting Amount:** ${bet.toLocaleString()} ${serverCurrency}\n\n` +
                        `\`1:\` ${card1}\n` +
                        `\`2:\` **${card2}**\n\n` +
                        `💥 Lost **${bet.toLocaleString()} ${serverCurrency}**`
                    );
                }

                return i.update({
                    embeds: [resultEmbed],
                    components: []
                });
            });

            collector.on('end', async (_, reason) => {
                if (reason === 'time') {
                    try {
                        await reply.edit({
                            content: '⏰ Game expired.',
                            components: []
                        });
                    } catch {}
                }
            });

            return;
        }

        // =========================
        // BLACKJACK
        // =========================

        if (
            command === 'bj' ||
            command === 'blackjack'
        ) {
            const data = getUserData(message.author.id);
            const bet = parseInt(args[0]);

            if (isNaN(bet) || bet <= 0) {
                return message.reply('❌ Invalid bet.');
            }

            if (data.cash < bet) {
                return message.reply('❌ Not enough cash.');
            }

            const draw = () => {
                const cards = [
                    '2', '3', '4', '5', '6', '7',
                    '8', '9', '10', 'J', 'Q', 'K', 'A'
                ];

                const c =
                    cards[Math.floor(Math.random() * cards.length)];

                return {
                    display: c,
                    value: ['J', 'Q', 'K'].includes(c)
                        ? 10
                        : c === 'A'
                            ? 11
                            : parseInt(c)
                };
            };

            let pHand = [draw(), draw()];
            let dHand = [draw(), draw()];

            const val = (hand) => {
                let total = hand.reduce(
                    (sum, card) => sum + card.value,
                    0
                );

                let aces = hand.filter(
                    card => card.display === 'A'
                ).length;

                while (total > 21 && aces > 0) {
                    total -= 10;
                    aces--;
                }

                return total;
            };

            const makeEmbed = (
                end = false,
                txt = ''
            ) => {
                const playerValue = val(pHand);
                const dealerValue = val(dHand);

                return new EmbedBuilder()
                    .setAuthor({
                        name: `${message.author.username}'s Game`
                    })
                    .setTitle('🃏 Blackjack 🃏')
                    .setDescription(
                        `**Your Hand**\n` +
                        `${pHand.map(c => `\`${c.display}\``).join(', ')}\n` +
                        `Value: **${playerValue}**\n\n` +

                        `**Dealer**\n` +
                        `${
                            end
                                ? dHand.map(c => `\`${c.display}\``).join(', ')
                                : `\`${dHand[0].display}\`, 🟥`
                        }\n` +

                        `Value: **${
                            end
                                ? dealerValue
                                : dHand[0].value
                        }**\n\n` +

                        txt
                    )
                    .setColor(
                        end ? '#f1c40f' : '#10a3de'
                    );
            };

            const row = new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId('hit')
                    .setLabel('Hit')
                    .setStyle(ButtonStyle.Primary),

                new ButtonBuilder()
                    .setCustomId('stand')
                    .setLabel('Stand')
                    .setStyle(ButtonStyle.Success)
            );

            const reply = await message.reply({
                embeds: [makeEmbed()],
                components: [row]
            });

            const collector =
                reply.createMessageComponentCollector({
                    componentType: ComponentType.Button,
                    time: 60000
                });

            collector.on('collect', async (i) => {
                if (i.user.id !== message.author.id) {
                    return i.reply({
                        content: '❌ This game belongs to someone else.',
                        ephemeral: true
                    });
                }

                if (i.customId === 'hit') {
                    pHand.push(draw());

                    if (val(pHand) > 21) {
                        collector.stop();

                        data.cash -= bet;

                        return i.update({
                            embeds: [
                                makeEmbed(
                                    true,
                                    `💥 Bust! Lost **${bet.toLocaleString()} ${serverCurrency}**.`
                                )
                            ],
                            components: []
                        });
                    }

                    return i.update({
                        embeds: [makeEmbed()],
                        components: [row]
                    });
                }

                if (i.customId === 'stand') {
                    collector.stop();

                    while (val(dHand) < 17) {
                        dHand.push(draw());
                    }

                    const pVal = val(pHand);
                    const dVal = val(dHand);

                    let resultMessage;

                    if (dVal > 21 || pVal > dVal) {
                        data.cash += bet;

                        resultMessage =
                            `🎉 Won **${bet.toLocaleString()} ${serverCurrency}**!`;
                    } else if (pVal < dVal) {
                        data.cash -= bet;

                        resultMessage =
                            `❌ Dealer won. Lost **${bet.toLocaleString()} ${serverCurrency}**.`;
                    } else {
                        resultMessage =
                            `👔 Push! Your bet was returned.`;
                    }

                    return i.update({
                        embeds: [
                            makeEmbed(
                                true,
                                resultMessage
                            )
                        ],
                        components: []
                    });
                }
            });

            return;
        }

        // =========================
        // MINES
        // =========================

        if (command === 'mines') {
            const data = getUserData(message.author.id);
            const bet = parseInt(args[0]);

            if (isNaN(bet) || bet <= 0) {
                return message.reply('❌ Invalid bet.');
            }

            if (data.cash < bet) {
                return message.reply('❌ Not enough cash.');
            }

            const board = Array(9).fill('safe');

            let m1 = Math.floor(Math.random() * 9);
            let m2 = Math.floor(Math.random() * 9);

            while (m1 === m2) {
                m2 = Math.floor(Math.random() * 9);
            }

            board[m1] = 'mine';
            board[m2] = 'mine';

            let profit = 0;
            let revealed = 0;
            let gameOver = false;

            const getRows = (end = false) => {
                const rows = [];

                for (let i = 0; i < 3; i++) {
                    const row =
                        new ActionRowBuilder();

                    for (let j = 0; j < 3; j++) {
                        const index = i * 3 + j;

                        const button =
                            new ButtonBuilder()
                                .setCustomId(`mine_${index}`)
                                .setLabel(
                                    end
                                        ? board[index] === 'mine'
                                            ? '💥'
                                            : '💎'
                                        : '⬛'
                                )
                                .setStyle(
                                    end
                                        ? ButtonStyle.Secondary
                                        : ButtonStyle.Secondary
                                )
                                .setDisabled(end);

                        row.addComponents(button);
                    }

                    rows.push(row);
                }

                const cashoutButton =
                    new ButtonBuilder()
                        .setCustomId('cashout')
                        .setLabel('Cashout')
                        .setStyle(ButtonStyle.Success)
                        .setDisabled(
                            revealed === 0 || end
                        );

                rows.push(
                    new ActionRowBuilder().addComponents(
                        cashoutButton
                    )
                );

                return rows;
            };

            const createEmbed = (text = '') =>
                new EmbedBuilder()
                    .setTitle('💣 Mines 💣')
                    .setDescription(
                        `**Betting:** ${bet.toLocaleString()} ${serverCurrency}\n\n` +
                        `**Profit:** ${profit.toLocaleString()} ${serverCurrency}\n\n` +
                        text
                    )
                    .setColor('#e67e22');

            const reply = await message.reply({
                embeds: [createEmbed()],
                components: getRows()
            });

            const collector =
                reply.createMessageComponentCollector({
                    componentType: ComponentType.Button,
                    time: 60000
                });

            collector.on('collect', async (i) => {
                if (i.user.id !== message.author.id) {
                    return i.reply({
                        content: '❌ This game belongs to someone else.',
                        ephemeral: true
                    });
                }

                if (gameOver) return;

                if (i.customId === 'cashout') {
                    gameOver = true;
                    collector.stop();

                    data.cash += profit;

                    return i.update({
                        embeds: [
                            new EmbedBuilder()
                                .setTitle('💰 Cashout! 💰')
                                .setDescription(
                                    `You cashed out **${profit.toLocaleString()} ${serverCurrency}**.`
                                )
                                .setColor('#2ecc71')
                        ],
                        components: getRows(true)
                    });
                }

                const index = parseInt(
                    i.customId.split('_')[1]
                );

                if (board[index] === 'mine') {
                    gameOver = true;
                    collector.stop();

                    data.cash -= bet;

                    return i.update({
                        embeds: [
                            new EmbedBuilder()
                                .setTitle('💥 BOOM! 💥')
                                .setDescription(
                                    `You lost **${bet.toLocaleString()} ${serverCurrency}**.`
                                )
                                .setColor('#e74c3c')
                        ],
                        components: getRows(true)
                    });
                }

                revealed++;
                profit += Math.floor(bet * 0.35);

                return i.update({
                    embeds: [
                        createEmbed('💎 Safe!')
                    ],
                    components: getRows()
                });
            });

            return;
        }

        // =========================
        // POKER / TEXAS
        // =========================

        if (
            command === 'poker' ||
            command === 'texas'
        ) {
            const data = getUserData(message.author.id);
            const bet = parseInt(args[0]);

            if (isNaN(bet) || bet <= 0) {
                return message.reply('❌ Invalid bet.');
            }

            if (data.cash < bet) {
                return message.reply('❌ Not enough cash.');
            }

            const suits = [
                '♠️',
                '♥️',
                '♦️',
                '♣️'
            ];

            const values = [
                '2', '3', '4', '5', '6', '7',
                '8', '9', '10', 'J', 'Q', 'K', 'A'
            ];

            const drawCard = () => ({
                val:
                    values[
                        Math.floor(
                            Math.random() * values.length
                        )
                    ],

                suit:
                    suits[
                        Math.floor(
                            Math.random() * suits.length
                        )
                    ]
            });

            const pHand = [
                drawCard(),
                drawCard()
            ];

            const bHand = [
                drawCard(),
                drawCard()
            ];

            const community = [
                drawCard(),
                drawCard(),
                drawCard(),
                drawCard(),
                drawCard()
            ];

            const embed = new EmbedBuilder()
                .setTitle('🃏 Texas Hold\'em 🃏')
                .setDescription(
                    `**Your Hand:** ` +
                    `[${pHand[0].val}${pHand[0].suit}] ` +
                    `[${pHand[1].val}${pHand[1].suit}]\n\n` +

                    `**Bot Hand:** [❓] [❓]\n\n` +

                    `**Community:** ` +
                    community
                        .map(
                            card =>
                                `[${card.val}${card.suit}]`
                        )
                        .join(' ')
                )
                .setColor('#1abc9c');

            const row =
                new ActionRowBuilder().addComponents(
                    new ButtonBuilder()
                        .setCustomId('call')
                        .setLabel('Call')
                        .setStyle(ButtonStyle.Success),

                    new ButtonBuilder()
                        .setCustomId('fold')
                        .setLabel('Fold')
                        .setStyle(ButtonStyle.Danger)
                );

            const reply = await message.reply({
                embeds: [embed],
                components: [row]
            });

            const collector =
                reply.createMessageComponentCollector({
                    componentType: ComponentType.Button,
                    time: 40000
                });

            collector.on('collect', async (i) => {
                if (i.user.id !== message.author.id) {
                    return i.reply({
                        content: '❌ This game belongs to someone else.',
                        ephemeral: true
                    });
                }

                collector.stop();

                if (i.customId === 'fold') {
                    const lost =
                        Math.floor(bet / 2);

                    data.cash -= lost;

                    return i.update({
                        content:
                            `🏳️ Folded. Lost **${lost.toLocaleString()} ${serverCurrency}**.`,
                        embeds: [],
                        components: []
                    });
                }

                const win =
                    Math.random() < 0.53;

                const result =
                    new EmbedBuilder();

                if (win) {
                    data.cash += bet;

                    result
                        .setTitle('🎉 You Won! 🎉')
                        .setDescription(
                            `Bot held: ` +
                            `[${bHand[0].val}${bHand[0].suit}] ` +
                            `[${bHand[1].val}${bHand[1].suit}]\n\n` +
                            `Won **${bet.toLocaleString()} ${serverCurrency}**`
                        )
                        .setColor('#2ecc71');
                } else {
                    data.cash -= bet;

                    result
                        .setTitle('❌ Bot Won! ❌')
                        .setDescription(
                            `Bot held: ` +
                            `[${bHand[0].val}${bHand[0].suit}] ` +
                            `[${bHand[1].val}${bHand[1].suit}]\n\n` +
                            `Lost **${bet.toLocaleString()} ${serverCurrency}**`
                        )
                        .setColor('#e74c3c');
                }

                return i.update({
                    embeds: [result],
                    components: []
                });
            });

            return;
        }
    } catch (error) {
        console.error('Command error:', error);

        try {
            await message.reply(
                '❌ Something went wrong while running this command.'
            );
        } catch {}
    }
});

client.login(process.env.DISCORD_TOKEN);