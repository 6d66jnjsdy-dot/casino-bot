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

const cooldowns = new Map();

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

    if (
        casinoRole &&
        message.member.roles.cache.has(casinoRole)
    ) {
        return true;
    }

    return false;
}

function formatMoney(amount) {
    return `${Math.floor(amount).toLocaleString()} ${serverCurrency}`;
}

function randomAmount(min, max) {
    return Math.floor(
        Math.random() * (max - min + 1)
    ) + min;
}

function getRemainingCooldown(userId, command, duration) {
    const key = `${userId}:${command}`;
    const last = cooldowns.get(key);

    if (!last) return 0;

    const remaining =
        duration - (Date.now() - last);

    if (remaining <= 0) {
        cooldowns.delete(key);
        return 0;
    }

    return remaining;
}

function startCooldown(userId, command) {
    cooldowns.set(
        `${userId}:${command}`,
        Date.now()
    );
}

function formatTime(ms) {
    const seconds = Math.ceil(ms / 1000);

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes > 0) {
        return `${minutes} דקות ו-${remainingSeconds} שניות`;
    }

    return `${remainingSeconds} שניות`;
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

        const command = args.shift()?.toLowerCase();

        if (!command) return;

        // =========================
        // ROLE CASINO
        // =========================

        if (command === 'role-casino') {
            if (
                !message.member.permissions.has(
                    'Administrator'
                )
            ) {
                return message.reply(
                    '❌ רק Administrator יכול להגדיר את תפקיד הקזינו.'
                );
            }

            const role =
                message.mentions.roles.first();

            if (!role) {
                return message.reply(
                    '❌ תייג תפקיד.\nלדוגמה: `$role-casino @Casino Staff`'
                );
            }

            casinoRole = role.id;

            return message.reply(
                `✅ תפקיד הקזינו הוגדר ל־**${role.name}**`
            );
        }

        // =========================
        // ADD MONEY
        // =========================

        if (command === 'addmoney') {
            if (!hasCasinoAccess(message)) {
                return message.reply(
                    '❌ אין לך הרשאה להשתמש בפקודה הזאת.'
                );
            }

            const target =
                message.mentions.users.first();

            if (!target) {
                return message.reply(
                    '❌ צריך לתייג משתמש.\n\n`$addmoney @user 1000`\nאו\n`$addmoney @user cash 1000`'
                );
            }

            let type = 'cash';
            let amount;

            if (
                args[0] &&
                ['cash', 'bank'].includes(
                    args[0].toLowerCase()
                )
            ) {
                type = args[0].toLowerCase();
                amount = parseInt(args[1]);
            } else {
                amount = parseInt(args[0]);
            }

            if (
                isNaN(amount) ||
                amount <= 0
            ) {
                return message.reply(
                    '❌ סכום לא תקין.\n\n`$addmoney @user 1000`\nאו\n`$addmoney @user cash 1000`'
                );
            }

            const data =
                getUserData(target.id);

            data[type] += amount;

            return message.reply(
                `✅ נוסף **${amount.toLocaleString()} ${serverCurrency}** ל־${type} של **${target.username}**.\n\n` +
                `💵 Cash: **${formatMoney(data.cash)}**\n` +
                `🏦 Bank: **${formatMoney(data.bank)}**`
            );
        }

        // =========================
        // SET CURRENCY
        // =========================

        if (command === 'setcurrency') {
            if (!hasCasinoAccess(message)) {
                return message.reply(
                    '❌ אין לך הרשאה להשתמש בפקודה הזאת.'
                );
            }

            const newCurrency = args[0];

            if (!newCurrency) {
                return message.reply(
                    '❌ תן מטבע/אימוג׳י.'
                );
            }

            serverCurrency = newCurrency;

            return message.reply(
                `✅ המטבע שונה ל־${serverCurrency}`
            );
        }

        // =========================
        // BALANCE
        // =========================

        if (
            command === 'bal' ||
            command === 'balance'
        ) {
            const targetUser =
                message.mentions.users.first() ||
                message.author;

            const data =
                getUserData(targetUser.id);

            const total =
                data.cash + data.bank;

            const embed =
                new EmbedBuilder()
                    .setAuthor({
                        name: targetUser.username,
                        iconURL:
                            targetUser.displayAvatarURL()
                    })
                    .setTitle('💰 Balance')
                    .setDescription(
                        `💵 **Cash:** ${formatMoney(data.cash)}\n` +
                        `🏦 **Bank:** ${formatMoney(data.bank)}\n` +
                        `💰 **Total:** ${formatMoney(total)}`
                    )
                    .setColor('#10a3de');

            return message.reply({
                embeds: [embed]
            });
        }

        // =========================
        // DEPOSIT
        // =========================

        if (
            command === 'dep' ||
            command === 'deposit'
        ) {
            const data =
                getUserData(message.author.id);

            const input =
                args[0]?.toLowerCase();

            if (!input) {
                return message.reply(
                    '❌ שימוש: `$dep 5000` או `$dep all`'
                );
            }

            let amount;

            if (input === 'all') {
                amount = data.cash;
            } else {
                amount = parseInt(input);
            }

            if (
                isNaN(amount) ||
                amount <= 0
            ) {
                return message.reply(
                    '❌ סכום לא תקין.'
                );
            }

            if (data.cash < amount) {
                return message.reply(
                    `❌ אין לך מספיק Cash.\nיש לך רק **${formatMoney(data.cash)}**.`
                );
            }

            data.cash -= amount;
            data.bank += amount;

            return message.reply(
                `🏦 הפקדת **${formatMoney(amount)}**.\n\n` +
                `💵 Cash: **${formatMoney(data.cash)}**\n` +
                `🏦 Bank: **${formatMoney(data.bank)}**`
            );
        }

        // =========================
        // WITHDRAW
        // =========================

        if (
            command === 'with' ||
            command === 'withdraw'
        ) {
            const data =
                getUserData(message.author.id);

            const input =
                args[0]?.toLowerCase();

            if (!input) {
                return message.reply(
                    '❌ שימוש: `$with 5000` או `$with all`'
                );
            }

            let amount;

            if (input === 'all') {
                amount = data.bank;
            } else {
                amount = parseInt(input);
            }

            if (
                isNaN(amount) ||
                amount <= 0
            ) {
                return message.reply(
                    '❌ סכום לא תקין.'
                );
            }

            if (data.bank < amount) {
                return message.reply(
                    `❌ אין לך מספיק כסף בבנק.\nיש לך רק **${formatMoney(data.bank)}**.`
                );
            }

            data.bank -= amount;
            data.cash += amount;

            return message.reply(
                `💵 משכת **${formatMoney(amount)}** מהבנק.\n\n` +
                `💵 Cash: **${formatMoney(data.cash)}**\n` +
                `🏦 Bank: **${formatMoney(data.bank)}**`
            );
        }

        // =========================
        // TOP
        // =========================

        if (command === 'top') {
            const users = Object.entries(balances)
                .map(([userId, data]) => ({
                    userId,
                    total:
                        data.cash + data.bank
                }))
                .sort(
                    (a, b) =>
                        b.total - a.total
                )
                .slice(0, 10);

            if (users.length === 0) {
                return message.reply(
                    '❌ עדיין אין נתוני כסף.'
                );
            }

            let text = '';

            for (
                let i = 0;
                i < users.length;
                i++
            ) {
                const user =
                    await client.users
                        .fetch(users[i].userId)
                        .catch(() => null);

                const name =
                    user?.username ||
                    users[i].userId;

                text +=
                    `**${i + 1}. ${name}** — ${formatMoney(users[i].total)}\n`;
            }

            const embed =
                new EmbedBuilder()
                    .setTitle('🏆 Money Top')
                    .setDescription(text)
                    .setColor('#f1c40f');

            return message.reply({
                embeds: [embed]
            });
        }

        // =========================
        // WORK
        // =========================

        if (command === 'work') {
            const cooldown =
                2 * 60 * 1000;

            const remaining =
                getRemainingCooldown(
                    message.author.id,
                    'work',
                    cooldown
                );

            if (remaining > 0) {
                return message.reply(
                    `⏰ אתה יכול לעבוד שוב בעוד **${formatTime(remaining)}**.`
                );
            }

            const amount =
                randomAmount(
                    6500,
                    17000
                );

            const data =
                getUserData(message.author.id);

            data.cash += amount;

            startCooldown(
                message.author.id,
                'work'
            );

            return message.reply(
                `💼 עבדת וקיבלת **${formatMoney(amount)}**!\n\n` +
                `💵 Cash: **${formatMoney(data.cash)}**`
            );
        }

        // =========================
        // CRIME
        // =========================

        if (command === 'crime') {
            const cooldown =
                2 * 60 * 1000;

            const remaining =
                getRemainingCooldown(
                    message.author.id,
                    'crime',
                    cooldown
                );

            if (remaining > 0) {
                return message.reply(
                    `⏰ אתה יכול לבצע Crime שוב בעוד **${formatTime(remaining)}**.`
                );
            }

            const amount =
                randomAmount(
                    6500,
                    20000
                );

            const data =
                getUserData(message.author.id);

            data.cash += amount;

            startCooldown(
                message.author.id,
                'crime'
            );

            return message.reply(
                `🔫 ביצעת Crime וקיבלת **${formatMoney(amount)}**!\n\n` +
                `💵 Cash: **${formatMoney(data.cash)}**`
            );
        }

        // =========================
        // ROB
        // =========================

        if (command === 'rob') {
            const cooldown =
                7 * 60 * 1000;

            const remaining =
                getRemainingCooldown(
                    message.author.id,
                    'rob',
                    cooldown
                );

            if (remaining > 0) {
                return message.reply(
                    `⏰ אתה יכול לשדוד שוב בעוד **${formatTime(remaining)}**.`
                );
            }

            const target =
                message.mentions.users.first();

            if (!target) {
                return message.reply(
                    '❌ צריך לתייג משתמש.\nלדוגמה: `$rob @user`'
                );
            }

            if (
                target.id ===
                message.author.id
            ) {
                return message.reply(
                    '❌ אי אפשר לשדוד את עצמך.'
                );
            }

            if (target.bot) {
                return message.reply(
                    '❌ אי אפשר לשדוד בוט.'
                );
            }

            const targetData =
                getUserData(target.id);

            if (targetData.cash <= 0) {
                return message.reply(
                    `❌ ל־${target.username} אין Cash לשדוד.`
                );
            }

            const stolen =
                Math.floor(
                    targetData.cash * 0.85
                );

            if (stolen <= 0) {
                return message.reply(
                    '❌ אין מספיק כסף לשדוד.'
                );
            }

            targetData.cash -= stolen;

            const robberData =
                getUserData(
                    message.author.id
                );

            robberData.cash += stolen;

            startCooldown(
                message.author.id,
                'rob'
            );

            return message.reply(
                `💰 **השוד הצליח!**\n\n` +
                `👤 קורבן: **${target.username}**\n` +
                `💸 לקחת: **${formatMoney(stolen)}**\n` +
                `📊 זה 85% מה־Cash שהיה לקורבן.\n\n` +
                `💵 ה־Cash שלך: **${formatMoney(robberData.cash)}**`
            );
        }

        // =========================
        // CHICKEN FIGHT
        // =========================

        if (
            command === 'cf' ||
            command === 'chickenfight'
        ) {
            const data =
                getUserData(message.author.id);

            const betInput = args[0];

            const bet =
                betInput?.toLowerCase() === 'all'
                    ? data.cash
                    : parseInt(betInput);

            if (
                isNaN(bet) ||
                bet <= 0
            ) {
                return message.reply(
                    '❌ סכום הימור לא תקין.'
                );
            }

            if (data.cash < bet) {
                return message.reply(
                    '❌ אין לך מספיק Cash.'
                );
            }

            const isWin =
                Math.random() < 0.52;

            if (isWin) {
                data.cash += bet;

                return message.reply({
                    embeds: [
                        new EmbedBuilder()
                            .setTitle('🐔 Chicken Fight')
                            .setDescription(
                                `🎉 התרנגול שלך ניצח!\n\n` +
                                `הרווחת **${formatMoney(bet)}**\n\n` +
                                `💵 Cash: **${formatMoney(data.cash)}**`
                            )
                            .setColor('#2ecc71')
                    ]
                });
            }

            data.cash -= bet;

            return message.reply({
                embeds: [
                    new EmbedBuilder()
                        .setTitle('🐔 Chicken Fight')
                        .setDescription(
                            `💥 התרנגול שלך הפסיד!\n\n` +
                            `הפסדת **${formatMoney(bet)}**\n\n` +
                            `💵 Cash: **${formatMoney(data.cash)}**`
                        )
                        .setColor('#e74c3c')
                ]
            });
        }

        // =========================
        // HIGHER / LOWER
        // =========================

        if (
            command === 'hilo' ||
            command === 'high-low'
        ) {
            const data =
                getUserData(message.author.id);

            const bet =
                parseInt(args[0]);

            if (
                isNaN(bet) ||
                bet <= 0
            ) {
                return message.reply(
                    '❌ סכום הימור לא תקין.'
                );
            }

            if (data.cash < bet) {
                return message.reply(
                    '❌ אין לך מספיק Cash.'
                );
            }

            const card1 =
                Math.floor(
                    Math.random() * 13
                ) + 1;

            const card2 =
                Math.floor(
                    Math.random() * 13
                ) + 1;

            const embed =
                new EmbedBuilder()
                    .setTitle(
                        '🎲 Higher or Lower 🎲'
                    )
                    .setDescription(
                        `**Bet:** ${formatMoney(bet)}\n\n` +
                        `1️⃣ **${card1}**\n` +
                        `2️⃣ ❓\n\n` +
                        `⬆️ Higher: 1.5x\n` +
                        `🟰 Same: 8x\n` +
                        `⬇️ Lower: 1.1x`
                    )
                    .setColor('#8e44ad');

            const row =
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId(
                                'higher'
                            )
                            .setLabel(
                                'Higher'
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                'same'
                            )
                            .setLabel(
                                'Same'
                            )
                            .setStyle(
                                ButtonStyle.Secondary
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                'lower'
                            )
                            .setLabel(
                                'Lower'
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            )
                    );

            const reply =
                await message.reply({
                    embeds: [embed],
                    components: [row]
                });

            const collector =
                reply.createMessageComponentCollector({
                    componentType:
                        ComponentType.Button,
                    time: 30000
                });

            collector.on(
                'collect',
                async (i) => {
                    if (
                        i.user.id !==
                        message.author.id
                    ) {
                        return i.reply({
                            content:
                                '❌ המשחק הזה שייך למישהו אחר.',
                            ephemeral: true
                        });
                    }

                    collector.stop();

                    const won =
                        (
                            i.customId ===
                                'higher' &&
                            card2 > card1
                        ) ||
                        (
                            i.customId ===
                                'lower' &&
                            card2 < card1
                        ) ||
                        (
                            i.customId ===
                                'same' &&
                            card2 === card1
                        );

                    const multiplier =
                        i.customId === 'same'
                            ? 8
                            : i.customId === 'higher'
                                ? 1.5
                                : 1.1;

                    const result =
                        new EmbedBuilder()
                            .setTitle(
                                '🎲 Result'
                            )
                            .setDescription(
                                `1️⃣ **${card1}**\n` +
                                `2️⃣ **${card2}**\n\n`
                            )
                            .setColor(
                                won
                                    ? '#2ecc71'
                                    : '#e74c3c'
                            );

                    if (won) {
                        const winAmount =
                            Math.floor(
                                bet * multiplier
                            );

                        data.cash +=
                            winAmount - bet;

                        result.setDescription(
                            `1️⃣ **${card1}**\n` +
                            `2️⃣ **${card2}**\n\n` +
                            `🎉 זכית **${formatMoney(winAmount)}**`
                        );
                    } else {
                        data.cash -= bet;

                        result.setDescription(
                            `1️⃣ **${card1}**\n` +
                            `2️⃣ **${card2}**\n\n` +
                            `💥 הפסדת **${formatMoney(bet)}**`
                        );
                    }

                    return i.update({
                        embeds: [result],
                        components: []
                    });
                }
            );

            return;
        }

        // =========================
        // BLACKJACK
        // =========================

        if (
            command === 'bj' ||
            command === 'blackjack'
        ) {
            const data =
                getUserData(message.author.id);

            const bet =
                parseInt(args[0]);

            if (
                isNaN(bet) ||
                bet <= 0
            ) {
                return message.reply(
                    '❌ סכום הימור לא תקין.'
                );
            }

            if (data.cash < bet) {
                return message.reply(
                    '❌ אין לך מספיק Cash.'
                );
            }

            const draw = () => {
                const cards = [
                    '2', '3', '4', '5', '6',
                    '7', '8', '9', '10',
                    'J', 'Q', 'K', 'A'
                ];

                const c =
                    cards[
                        Math.floor(
                            Math.random() *
                            cards.length
                        )
                    ];

                return {
                    display: c,
                    value:
                        ['J', 'Q', 'K'].includes(c)
                            ? 10
                            : c === 'A'
                                ? 11
                                : parseInt(c)
                };
            };

            let pHand = [
                draw(),
                draw()
            ];

            let dHand = [
                draw(),
                draw()
            ];

            const val = (hand) => {
                let total =
                    hand.reduce(
                        (sum, card) =>
                            sum + card.value,
                        0
                    );

                let aces =
                    hand.filter(
                        card =>
                            card.display === 'A'
                    ).length;

                while (
                    total > 21 &&
                    aces > 0
                ) {
                    total -= 10;
                    aces--;
                }

                return total;
            };

            const makeEmbed = (
                end = false,
                txt = ''
            ) => {
                const playerValue =
                    val(pHand);

                const dealerValue =
                    val(dHand);

                return new EmbedBuilder()
                    .setTitle(
                        '🃏 Blackjack'
                    )
                    .setDescription(
                        `**Your Hand**\n` +
                        `${pHand
                            .map(
                                c =>
                                    `\`${c.display}\``
                            )
                            .join(', ')}\n` +
                        `Value: **${playerValue}**\n\n` +

                        `**Dealer**\n` +
                        `${
                            end
                                ? dHand
                                    .map(
                                        c =>
                                            `\`${c.display}\``
                                    )
                                    .join(', ')
                                : `\`${dHand[0].display}\`, 🟥`
                        }\n\n` +

                        txt
                    )
                    .setColor(
                        end
                            ? '#f1c40f'
                            : '#10a3de'
                    );
            };

            const row =
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId(
                                'hit'
                            )
                            .setLabel(
                                'Hit'
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                'stand'
                            )
                            .setLabel(
                                'Stand'
                            )
                            .setStyle(
                                ButtonStyle.Success
                            )
                    );

            const reply =
                await message.reply({
                    embeds: [
                        makeEmbed()
                    ],
                    components: [row]
                });

            const collector =
                reply.createMessageComponentCollector({
                    componentType:
                        ComponentType.Button,
                    time: 60000
                });

            collector.on(
                'collect',
                async (i) => {
                    if (
                        i.user.id !==
                        message.author.id
                    ) {
                        return i.reply({
                            content:
                                '❌ המשחק הזה שייך למישהו אחר.',
                            ephemeral: true
                        });
                    }

                    if (
                        i.customId ===
                        'hit'
                    ) {
                        pHand.push(draw());

                        if (
                            val(pHand) > 21
                        ) {
                            collector.stop();

                            data.cash -= bet;

                            return i.update({
                                embeds: [
                                    makeEmbed(
                                        true,
                                        `💥 Bust! הפסדת **${formatMoney(bet)}**.`
                                    )
                                ],
                                components: []
                            });
                        }

                        return i.update({
                            embeds: [
                                makeEmbed()
                            ],
                            components: [row]
                        });
                    }

                    if (
                        i.customId ===
                        'stand'
                    ) {
                        collector.stop();

                        while (
                            val(dHand) < 17
                        ) {
                            dHand.push(
                                draw()
                            );
                        }

                        const pVal =
                            val(pHand);

                        const dVal =
                            val(dHand);

                        let resultMessage;

                        if (
                            dVal > 21 ||
                            pVal > dVal
                        ) {
                            data.cash += bet;

                            resultMessage =
                                `🎉 ניצחת **${formatMoney(bet)}**!`;
                        } else if (
                            pVal < dVal
                        ) {
                            data.cash -= bet;

                            resultMessage =
                                `❌ הדילר ניצח. הפסדת **${formatMoney(bet)}**.`;
                        } else {
                            resultMessage =
                                `👔 תיקו! הכסף נשאר אצלך.`;
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
                }
            );

            return;
        }

        // =========================
        // MINES
        // =========================

        if (command === 'mines') {
            const data =
                getUserData(message.author.id);

            const bet =
                parseInt(args[0]);

            if (
                isNaN(bet) ||
                bet <= 0
            ) {
                return message.reply(
                    '❌ סכום הימור לא תקין.'
                );
            }

            if (data.cash < bet) {
                return message.reply(
                    '❌ אין לך מספיק Cash.'
                );
            }

            const board =
                Array(9).fill('safe');

            let m1 =
                Math.floor(
                    Math.random() * 9
                );

            let m2 =
                Math.floor(
                    Math.random() * 9
                );

            while (m1 === m2) {
                m2 =
                    Math.floor(
                        Math.random() * 9
                    );
            }

            board[m1] = 'mine';
            board[m2] = 'mine';

            let profit = 0;
            let revealed = 0;
            let gameOver = false;

            const getRows =
                (end = false) => {
                    const rows = [];

                    for (
                        let i = 0;
                        i < 3;
                        i++
                    ) {
                        const row =
                            new ActionRowBuilder();

                        for (
                            let j = 0;
                            j < 3;
                            j++
                        ) {
                            const index =
                                i * 3 + j;

                            row.addComponents(
                                new ButtonBuilder()
                                    .setCustomId(
                                        `mine_${index}`
                                    )
                                    .setLabel(
                                        end
                                            ? board[index] ===
                                                'mine'
                                                ? '💥'
                                                : '💎'
                                            : '⬛'
                                    )
                                    .setStyle(
                                        ButtonStyle.Secondary
                                    )
                                    .setDisabled(
                                        end
                                    )
                            );
                        }

                        rows.push(row);
                    }

                    const cashout =
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
                                revealed === 0 ||
                                end
                            );

                    rows.push(
                        new ActionRowBuilder()
                            .addComponents(
                                cashout
                            )
                    );

                    return rows;
                };

            const createEmbed =
                (text = '') =>
                    new EmbedBuilder()
                        .setTitle(
                            '💣 Mines'
                        )
                        .setDescription(
                            `**Bet:** ${formatMoney(bet)}\n\n` +
                            `**Profit:** ${formatMoney(profit)}\n\n` +
                            text
                        )
                        .setColor(
                            '#e67e22'
                        );

            const reply =
                await message.reply({
                    embeds: [
                        createEmbed()
                    ],
                    components:
                        getRows()
                });

            const collector =
                reply.createMessageComponentCollector({
                    componentType:
                        ComponentType.Button,
                    time: 60000
                });

            collector.on(
                'collect',
                async (i) => {
                    if (
                        i.user.id !==
                        message.author.id
                    ) {
                        return i.reply({
                            content:
                                '❌ המשחק הזה שייך למישהו אחר.',
                            ephemeral: true
                        });
                    }

                    if (gameOver) return;

                    if (
                        i.customId ===
                        'cashout'
                    ) {
                        gameOver = true;
                        collector.stop();

                        data.cash += profit;

                        return i.update({
                            embeds: [
                                new EmbedBuilder()
                                    .setTitle(
                                        '💰 Cashout'
                                    )
                                    .setDescription(
                                        `קיבלת **${formatMoney(profit)}**.`
                                    )
                                    .setColor(
                                        '#2ecc71'
                                    )
                            ],
                            components:
                                getRows(true)
                        });
                    }

                    const index =
                        parseInt(
                            i.customId.split(
                                '_'
                            )[1]
                        );

                    if (
                        board[index] ===
                        'mine'
                    ) {
                        gameOver = true;
                        collector.stop();

                        data.cash -= bet;

                        return i.update({
                            embeds: [
                                new EmbedBuilder()
                                    .setTitle(
                                        '💥 BOOM!'
                                    )
                                    .setDescription(
                                        `הפסדת **${formatMoney(bet)}**.`
                                    )
                                    .setColor(
                                        '#e74c3c'
                                    )
                            ],
                            components:
                                getRows(true)
                        });
                    }

                    revealed++;

                    profit +=
                        Math.floor(
                            bet * 0.35
                        );

                    return i.update({
                        embeds: [
                            createEmbed(
                                '💎 Safe!'
                            )
                        ],
                        components:
                            getRows()
                    });
                }
            );

            return;
        }

        // =========================
        // POKER
        // =========================

        if (
            command === 'poker' ||
            command === 'texas'
        ) {
            const data =
                getUserData(message.author.id);

            const bet =
                parseInt(args[0]);

            if (
                isNaN(bet) ||
                bet <= 0
            ) {
                return message.reply(
                    '❌ סכום הימור לא תקין.'
                );
            }

            if (data.cash < bet) {
                return message.reply(
                    '❌ אין לך מספיק Cash.'
                );
            }

            const suits = [
                '♠️',
                '♥️',
                '♦️',
                '♣️'
            ];

            const values = [
                '2', '3', '4', '5',
                '6', '7', '8', '9',
                '10', 'J', 'Q', 'K', 'A'
            ];

            const drawCard = () => ({
                val:
                    values[
                        Math.floor(
                            Math.random() *
                            values.length
                        )
                    ],
                suit:
                    suits[
                        Math.floor(
                            Math.random() *
                            suits.length
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

            const embed =
                new EmbedBuilder()
                    .setTitle(
                        '🃏 Texas Hold\'em'
                    )
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
                    .setColor(
                        '#1abc9c'
                    );

            const row =
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId(
                                'call'
                            )
                            .setLabel(
                                'Call'
                            )
                            .setStyle(
                                ButtonStyle.Success
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                'fold'
                            )
                            .setLabel(
                                'Fold'
                            )
                            .setStyle(
                                ButtonStyle.Danger
                            )
                    );

            const reply =
                await message.reply({
                    embeds: [embed],
                    components: [row]
                });

            const collector =
                reply.createMessageComponentCollector({
                    componentType:
                        ComponentType.Button,
                    time: 40000
                });

            collector.on(
                'collect',
                async (i) => {
                    if (
                        i.user.id !==
                        message.author.id
                    ) {
                        return i.reply({
                            content:
                                '❌ המשחק הזה שייך למישהו אחר.',
                            ephemeral: true
                        });
                    }

                    collector.stop();

                    if (
                        i.customId ===
                        'fold'
                    ) {
                        const lost =
                            Math.floor(
                                bet / 2
                            );

                        data.cash -= lost;

                        return i.update({
                            content:
                                `🏳️ Folded. הפסדת **${formatMoney(lost)}**.`,
                            embeds: [],
                            components: []
                        });
                    }

                    const win =
                        Math.random() <
                        0.53;

                    const result =
                        new EmbedBuilder();

                    if (win) {
                        data.cash += bet;

                        result
                            .setTitle(
                                '🎉 You Won!'
                            )
                            .setDescription(
                                `ניצחת!\n\n` +
                                `הרווח: **${formatMoney(bet)}**`
                            )
                            .setColor(
                                '#2ecc71'
                            );
                    } else {
                        data.cash -= bet;

                        result
                            .setTitle(
                                '❌ Bot Won!'
                            )
                            .setDescription(
                                `הבוט ניצח.\n\n` +
                                `הפסדת **${formatMoney(bet)}**`
                            )
                            .setColor(
                                '#e74c3c'
                            );
                    }

                    return i.update({
                        embeds: [result],
                        components: []
                    });
                }
            );

            return;
        }

    } catch (error) {
        console.error(
            'Command error:',
            error
        );

        try {
            await message.reply(
                '❌ אירעה שגיאה בהפעלת הפקודה.'
            );
        } catch {}
    }
});

client.login(
    process.env.DISCORD_TOKEN
);