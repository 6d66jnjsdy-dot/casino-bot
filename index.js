const {
    Client,
    GatewayIntentBits,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle,
    PermissionFlagsBits
} = require("discord.js");

const express = require("express");

// ===============================
// RENDER WEB SERVER
// ===============================
const app = express();
const PORT = process.env.PORT || 10000;

app.get("/", (req, res) => {
    res.send("Casino Bot is Online 24/7!");
});

app.listen(PORT, "0.0.0.0", () => {
    console.log(`Web server running on port ${PORT}`);
});

// ===============================
// DISCORD
// ===============================
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

// ===============================
// DATABASE
// ===============================
const db = {
    users: {},
    currency: "💸",
    casinoRole: null
};

const PREFIX = "$";
const MIN_BET = 150;

function getUser(id) {
    if (!db.users[id]) {
        db.users[id] = {
            cash: 1000,
            bank: 0
        };
    }

    return db.users[id];
}

function isManager(message) {
    if (!message.member) return false;

    return (
        message.member.permissions.has(
            PermissionFlagsBits.Administrator
        ) ||
        (
            db.casinoRole &&
            message.member.roles.cache.has(db.casinoRole)
        )
    );
}

// ===============================
// DECK
// ===============================
function createDeck() {
    const suits = ["♠️", "♥️", "♦️", "♣️"];

    const cards = [
        ["2", 2],
        ["3", 3],
        ["4", 4],
        ["5", 5],
        ["6", 6],
        ["7", 7],
        ["8", 8],
        ["9", 9],
        ["10", 10],
        ["J", 10],
        ["Q", 10],
        ["K", 10],
        ["A", 11]
    ];

    const deck = [];

    for (const suit of suits) {
        for (const [name, value] of cards) {
            deck.push({ name, value, suit });
        }
    }

    for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
    }

    return deck;
}

function handValue(hand) {
    let value = hand.reduce(
        (sum, card) => sum + card.value,
        0
    );

    let aces = hand.filter(
        card => card.name === "A"
    ).length;

    while (value > 21 && aces > 0) {
        value -= 10;
        aces--;
    }

    return value;
}

// ===============================
// MESSAGE HANDLER
// ===============================
client.on("messageCreate", async message => {
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
    const user = getUser(message.author.id);

    // ===============================
    // CURRENCY
    // ===============================
    if (command === "currency") {
        if (!isManager(message)) {
            return message.reply(
                "❌ You don't have permission to use this command."
            );
        }

        if (!args[0]) {
            return message.reply(
                `Usage: ${PREFIX}currency [emoji]`
            );
        }

        db.currency = args[0];

        return message.reply(
            `✅ Currency changed to ${db.currency}`
        );
    }

    // ===============================
    // CASINO ROLE
    // ===============================
    if (command === "casino") {
        if (
            !message.member.permissions.has(
                PermissionFlagsBits.Administrator
            )
        ) {
            return message.reply(
                "❌ Only Server Admins can use this."
            );
        }

        if (args[0]?.toLowerCase() === "role") {
            const role =
                message.mentions.roles.first() ||
                message.guild.roles.cache.get(args[1]);

            if (!role) {
                return message.reply(
                    `Usage: ${PREFIX}casino role @Role`
                );
            }

            db.casinoRole = role.id;

            return message.reply(
                `✅ Casino management access granted to **${role.name}**`
            );
        }
    }

    // ===============================
    // ADD MONEY
    // $addmoney cash @user 500
    // $addmoney bank @user 500
    // ===============================
    if (command === "addmoney") {
        if (!isManager(message)) {
            return message.reply("❌ Access Denied.");
        }

        const type = args[0]?.toLowerCase();

        const target =
            message.mentions.users.first() ||
            message.guild.members.cache
                .get(args[1])
                ?.user;

        const amount = Number(args[2]);

        if (
            !["cash", "bank"].includes(type) ||
            !target ||
            !Number.isInteger(amount) ||
            amount <= 0
        ) {
            return message.reply(
                `Usage: ${PREFIX}addmoney cash/bank @user amount`
            );
        }

        const targetData = getUser(target.id);

        targetData[type] += amount;

        return message.reply(
            `✅ Added **${amount.toLocaleString()}** ${db.currency} to **${target.username}** ${type}.`
        );
    }

    // ===============================
    // BALANCE
    // ===============================
    if (
        command === "bal" ||
        command === "balance"
    ) {
        const target =
            message.mentions.users.first() ||
            message.author;

        const data = getUser(target.id);

        const embed = new EmbedBuilder()
            .setAuthor({
                name: `${target.username}'s Balance`,
                iconURL: target.displayAvatarURL()
            })
            .setColor("#f1c40f")
            .addFields(
                {
                    name: "💵 Cash",
                    value: `${data.cash.toLocaleString()} ${db.currency}`,
                    inline: true
                },
                {
                    name: "🏦 Bank",
                    value: `${data.bank.toLocaleString()} ${db.currency}`,
                    inline: true
                },
                {
                    name: "📊 Total",
                    value: `**${(
                        data.cash + data.bank
                    ).toLocaleString()}** ${db.currency}`
                }
            );

        return message.reply({
            embeds: [embed]
        });
    }

    // ===============================
    // DEPOSIT
    // ===============================
    if (
        command === "dep" ||
        command === "deposit"
    ) {
        let amount =
            args[0]?.toLowerCase() === "all"
                ? user.cash
                : Number(args[0]);

        if (
            !Number.isInteger(amount) ||
            amount <= 0 ||
            amount > user.cash
        ) {
            return message.reply(
                "❌ Invalid amount or insufficient cash."
            );
        }

        user.cash -= amount;
        user.bank += amount;

        return message.reply({
            embeds: [
                new EmbedBuilder()
                    .setColor("#2ecc71")
                    .setDescription(
                        `Successfully deposited **${amount.toLocaleString()}** ${db.currency} to your bank account.`
                    )
            ]
        });
    }

    // ===============================
    // WITHDRAW
    // ===============================
    if (
        command === "with" ||
        command === "withdraw"
    ) {
        let amount =
            args[0]?.toLowerCase() === "all"
                ? user.bank
                : Number(args[0]);

        if (
            !Number.isInteger(amount) ||
            amount <= 0 ||
            amount > user.bank
        ) {
            return message.reply(
                "❌ Invalid amount or insufficient bank balance."
            );
        }

        user.bank -= amount;
        user.cash += amount;

        return message.reply({
            embeds: [
                new EmbedBuilder()
                    .setColor("#2ecc71")
                    .setDescription(
                        `Successfully withdrew **${amount.toLocaleString()}** ${db.currency} from your bank account.`
                    )
            ]
        });
    }

    // ===============================
    // LEADERBOARD
    // ===============================
    if (
        command === "lb" ||
        command === "leaderboard"
    ) {
        const sorted = Object.entries(db.users)
            .map(([id, data]) => ({
                id,
                total: data.cash + data.bank
            }))
            .sort((a, b) => b.total - a.total)
            .slice(0, 10);

        let text = "";

        for (let i = 0; i < sorted.length; i++) {
            const member =
                await client.users
                    .fetch(sorted[i].id)
                    .catch(() => null);

            if (!member) continue;

            text +=
                `**#${i + 1}** ${member.username} — ${sorted[i].total.toLocaleString()} ${db.currency}\n`;
        }

        return message.reply({
            embeds: [
                new EmbedBuilder()
                    .setTitle("🏆 Leaderboard")
                    .setColor("#f1c40f")
                    .setDescription(
                        text || "No players yet."
                    )
            ]
        });
    }

    // ==================================================
    // BLACKJACK
    // ==================================================
    if (
        command === "bj" ||
        command === "blackjack"
    ) {
        const bet = Number(args[0]);

        if (
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
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

        const playerHand = [
            deck.pop(),
            deck.pop()
        ];

        const dealerHand = [
            deck.pop(),
            deck.pop()
        ];

        function blackjackEmbed(showDealer = false) {
            const playerValue =
                handValue(playerHand);

            const dealerValue =
                handValue(dealerHand);

            const playerCards =
                playerHand
                    .map(
                        c =>
                            `[${c.name}${c.suit}]`
                    )
                    .join(", ");

            const dealerCards = showDealer
                ? dealerHand
                      .map(
                          c =>
                              `[${c.name}${c.suit}]`
                      )
                      .join(", ")
                : `[${dealerHand[0].name}${dealerHand[0].suit}], [?]`;

            return new EmbedBuilder()
                .setAuthor({
                    name: `${message.author.username}'s Game`,
                    iconURL:
                        message.author.displayAvatarURL()
                })
                .setTitle("🃏 Blackjack 🃏")
                .setColor("#f1c40f")
                .addFields(
                    {
                        name: "Your Hand",
                        value:
                            `${playerCards}\n\nValue: **${playerValue}**`
                    },
                    {
                        name: "Dealer",
                        value:
                            `${dealerCards}\n\nValue: **${
                                showDealer
                                    ? dealerValue
                                    : dealerHand[0].value
                            }**`
                    }
                );
        }

        const row =
            new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId("bj_hit")
                    .setLabel("Hit")
                    .setStyle(
                        ButtonStyle.Primary
                    ),

                new ButtonBuilder()
                    .setCustomId("bj_stand")
                    .setLabel("Stand")
                    .setStyle(
                        ButtonStyle.Success
                    ),

                new ButtonBuilder()
                    .setCustomId("bj_double")
                    .setLabel("Double")
                    .setStyle(
                        ButtonStyle.Danger
                    )
            );

        const msg =
            await message.reply({
                embeds: [
                    blackjackEmbed()
                ],
                components: [row]
            });

        const collector =
            msg.createMessageComponentCollector({
                filter:
                    i =>
                        i.user.id ===
                        message.author.id,
                time: 60000
            });

        collector.on(
            "collect",
            async interaction => {
                await interaction.deferUpdate();

                if (
                    interaction.customId ===
                    "bj_hit"
                ) {
                    playerHand.push(
                        deck.pop()
                    );

                    if (
                        handValue(
                            playerHand
                        ) >= 21
                    ) {
                        collector.stop(
                            "finished"
                        );
                    } else {
                        await msg.edit({
                            embeds: [
                                blackjackEmbed()
                            ]
                        });
                    }

                    return;
                }

                if (
                    interaction.customId ===
                    "bj_double"
                ) {
                    if (
                        user.cash < bet
                    ) {
                        return;
                    }

                    user.cash -= bet;
                    totalBet += bet;

                    playerHand.push(
                        deck.pop()
                    );

                    collector.stop(
                        "double"
                    );

                    return;
                }

                if (
                    interaction.customId ===
                    "bj_stand"
                ) {
                    collector.stop(
                        "stand"
                    );
                }
            }
        );

        collector.on(
            "end",
            async (_, reason) => {
                if (reason === "time") {
                    user.cash += totalBet;

                    return msg.edit({
                        embeds: [
                            new EmbedBuilder()
                                .setColor(
                                    "#95a5a6"
                                )
                                .setTitle(
                                    "⏰ Blackjack Timed Out"
                                )
                                .setDescription(
                                    `Your **${totalBet.toLocaleString()}** ${db.currency} bet was returned.`
                                )
                        ],
                        components: []
                    });
                }

                if (
                    reason === "stand" ||
                    reason === "double" ||
                    reason === "finished"
                ) {
                    while (
                        handValue(
                            dealerHand
                        ) < 17
                    ) {
                        dealerHand.push(
                            deck.pop()
                        );
                    }
                }

                const player =
                    handValue(playerHand);

                const dealer =
                    handValue(dealerHand);

                let payout = 0;
                let text = "";

                if (player > 21) {
                    text =
                        `❌ You busted and lost **${totalBet.toLocaleString()}** ${db.currency}`;
                } else if (dealer > 21) {
                    payout =
                        totalBet * 2;

                    text =
                        `🎉 Dealer busted! You won **${payout.toLocaleString()}** ${db.currency}`;
                } else if (player > dealer) {
                    payout =
                        totalBet * 2;

                    text =
                        `🎉 You won **${payout.toLocaleString()}** ${db.currency}`;
                } else if (player === dealer) {
                    payout = totalBet;

                    text =
                        `🤝 It's a Tie! Returned **${totalBet.toLocaleString()}** ${db.currency}`;
                } else {
                    text =
                        `❌ You lost **${totalBet.toLocaleString()}** ${db.currency}`;
                }

                user.cash += payout;

                const finalEmbed =
                    blackjackEmbed(true)
                        .setDescription(text);

                await msg.edit({
                    embeds: [finalEmbed],
                    components: []
                });
            }
        );

        return;
    }

    // ==================================================
    // COCKFIGHT
    // ==================================================
    if (
        command === "cf" ||
        command === "cockfight" ||
        command === "chickenfight"
    ) {
        const bet = Number(args[0]);

        if (
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
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

        const win =
            Math.random() <
            strength / 100;

        if (win) {
            const payout = bet * 2;

            user.cash += payout;

            return message.reply({
                embeds: [
                    new EmbedBuilder()
                        .setColor("#2ecc71")
                        .setDescription(
                            `Your chicken won the fight! You won **${payout.toLocaleString()}** ${db.currency} 🐓!\n\n**Your chicken's strength:** ${strength}%`
                        )
                ]
            });
        }

        return message.reply({
            embeds: [
                new EmbedBuilder()
                    .setColor("#e74c3c")
                    .setDescription(
                        `Your chicken lost the fight... You lost **${bet.toLocaleString()}** ${db.currency} 🐓.`
                    )
            ]
        });
    }

    // ==================================================
    // COINFLIP
    // ==================================================
    if (
        command === "ht" ||
        command === "coinflip"
    ) {
        const choice =
            args[0]?.toLowerCase();

        const bet = Number(args[1]);

        if (
            !["heads", "tails"].includes(
                choice
            ) ||
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `Usage: ${PREFIX}ht heads/tails amount\nMinimum: ${MIN_BET}`
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
                ? "heads"
                : "tails";

        if (choice === result) {
            const payout = bet * 2;

            user.cash += payout;

            return message.reply({
                embeds: [
                    new EmbedBuilder()
                        .setColor("#2ecc71")
                        .setDescription(
                            `🪙 The coin landed on **${result}**! You won **${payout.toLocaleString()}** ${db.currency}.`
                        )
                ]
            });
        }

        return message.reply({
            embeds: [
                new EmbedBuilder()
                    .setColor("#e74c3c")
                    .setDescription(
                        `🪙 The coin landed on **${result}**! You lost **${bet.toLocaleString()}** ${db.currency}.`
                    )
            ]
        });
    }

    // ==================================================
    // HIGHER LOWER
    // ==================================================
    if (
        command === "hl" ||
        command === "higherlower"
    ) {
        const bet = Number(args[0]);

        if (
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const first =
            Math.floor(
                Math.random() * 12
            ) + 1;

        const embed =
            new EmbedBuilder()
                .setTitle(
                    "🎲 Higher or Lower 🎲"
                )
                .setColor("#9b59b6")
                .setDescription(
                    `**Betting Amount:** ${bet} ${db.currency}\n\n**1 :** ${first}\n**2 :** ❓\n\n**Higher:** 1.5x\n**Same:** 25x\n**Lower:** 1.5x`
                );

        const row =
            new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId("hl_higher")
                    .setLabel("Higher")
                    .setStyle(
                        ButtonStyle.Primary
                    ),

                new ButtonBuilder()
                    .setCustomId("hl_same")
                    .setLabel("Same")
                    .setStyle(
                        ButtonStyle.Secondary
                    ),

                new ButtonBuilder()
                    .setCustomId("hl_lower")
                    .setLabel("Lower")
                    .setStyle(
                        ButtonStyle.Primary
                    )
            );

        const msg =
            await message.reply({
                embeds: [embed],
                components: [row]
            });

        const interaction =
            await msg
                .awaitMessageComponent({
                    filter:
                        i =>
                            i.user.id ===
                            message.author.id,
                    time: 30000
                })
                .catch(() => null);

        if (!interaction) {
            user.cash += bet;

            return msg.edit({
                content:
                    "⏰ Game timed out. Your bet was returned.",
                components: []
            });
        }

        await interaction.deferUpdate();

        const second =
            Math.floor(
                Math.random() * 12
            ) + 1;

        let multiplier = 0;

        if (
            interaction.customId ===
                "hl_higher" &&
            second > first
        ) {
            multiplier = 1.5;
        }

        if (
            interaction.customId ===
                "hl_lower" &&
            second < first
        ) {
            multiplier = 1.5;
        }

        if (
            interaction.customId ===
                "hl_same" &&
            second === first
        ) {
            multiplier = 25;
        }

        if (multiplier > 0) {
            const payout =
                Math.floor(
                    bet * multiplier
                );

            user.cash += payout;

            return msg.edit({
                embeds: [
                    new EmbedBuilder()
                        .setColor("#2ecc71")
                        .setTitle(
                            "🎲 Higher or Lower Result 🎲"
                        )
                        .setDescription(
                            `**1:** ${first}\n**2:** ${second}\n\n🎉 You won **${payout.toLocaleString()}** ${db.currency}!`
                        )
                ],
                components: []
            });
        }

        return msg.edit({
            embeds: [
                new EmbedBuilder()
                    .setColor("#e74c3c")
                    .setTitle(
                        "🎲 Higher or Lower Result 🎲"
                    )
                    .setDescription(
                        `**1:** ${first}\n**2:** ${second}\n\n❌ You lost **${bet.toLocaleString()}** ${db.currency}.`
                    )
            ],
            components: []
        });
    }

    // ==================================================
    // MINES
    // ==================================================
    if (command === "mines") {
        const bet = Number(args[0]);

        if (
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const bomb =
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

        const revealed = [];

        function mineRows(disabled = false) {
            const rows = [];

            for (let r = 0; r < 3; r++) {
                const buttons = [];

                for (let c = 0; c < 3; c++) {
                    const index =
                        r * 3 + c;

                    const button =
                        new ButtonBuilder()
                            .setCustomId(
                                `mine_${index}`
                            )
                            .setEmoji(
                                revealed.includes(
                                    index
                                )
                                    ? "💎"
                                    : "⬛"
                            )
                            .setStyle(
                                revealed.includes(
                                    index
                                )
                                    ? ButtonStyle.Success
                                    : ButtonStyle.Secondary
                            )
                            .setDisabled(
                                disabled ||
                                revealed.includes(
                                    index
                                )
                            );

                    buttons.push(button);
                }

                rows.push(
                    new ActionRowBuilder()
                        .addComponents(
                            buttons
                        )
                );
            }

            const profit =
                revealed.length
                    ? Math.floor(
                          bet *
                              multipliers[
                                  revealed.length -
                                      1
                              ]
                      )
                    : 0;

            rows.push(
                new ActionRowBuilder()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId(
                                "mine_cashout"
                            )
                            .setLabel(
                                "Cashout"
                            )
                            .setStyle(
                                ButtonStyle.Success
                            )
                            .setDisabled(
                                revealed.length ===
                                    0 ||
                                disabled
                            ),

                        new ButtonBuilder()
                            .setCustomId(
                                "mine_profit"
                            )
                            .setLabel(
                                `Profit: ${Math.max(
                                    0,
                                    profit - bet
                                )} ${db.currency}`
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            )
                            .setDisabled(true)
                    )
            );

            return rows;
        }

        const msg =
            await message.reply({
                embeds: [
                    new EmbedBuilder()
                        .setTitle(
                            "💣 Mines 3x3 💣"
                        )
                        .setColor("#f1c40f")
                        .setDescription(
                            `Find diamonds and avoid the bomb!\nNext Multiplier: **${multipliers[0]}x**`
                        )
                ],
                components: mineRows()
            });

        const collector =
            msg.createMessageComponentCollector({
                filter:
                    i =>
                        i.user.id ===
                        message.author.id,
                time: 120000
            });

        collector.on(
            "collect",
            async interaction => {
                await interaction.deferUpdate();

                if (
                    interaction.customId ===
                    "mine_cashout"
                ) {
                    collector.stop(
                        "cashout"
                    );
                    return;
                }

                if (
                    interaction.customId ===
                    "mine_profit"
                ) {
                    return;
                }

                const index =
                    Number(
                        interaction.customId.split(
                            "_"
                        )[1]
                    );

                if (
                    index === bomb
                ) {
                    collector.stop(
                        "bomb"
                    );
                    return;
                }

                if (
                    revealed.includes(
                        index
                    )
                ) {
                    return;
                }

                revealed.push(index);

                if (
                    revealed.length === 8
                ) {
                    collector.stop(
                        "win"
                    );
                    return;
                }

                const next =
                    multipliers[
                        revealed.length
                    ];

                await msg.edit({
                    embeds: [
                        new EmbedBuilder()
                            .setTitle(
                                "💣 Mines 3x3 💣"
                            )
                            .setColor("#f1c40f")
                            .setDescription(
                                `💎 Safe!\nCurrent Multiplier: **${multipliers[
                                    revealed.length -
                                        1
                                ]}x**\nNext Multiplier: **${next}x**`
                            )
                    ],
                    components:
                        mineRows()
                });
            }
        );

        collector.on(
            "end",
            async (_, reason) => {
                if (
                    reason === "time"
                ) {
                    user.cash += bet;

                    return msg.edit({
                        content:
                            "⏰ Game timed out. Your bet was returned.",
                        components: []
                    });
                }

                if (
                    reason === "bomb"
                ) {
                    return msg.edit({
                        embeds: [
                            new EmbedBuilder()
                                .setColor(
                                    "#e74c3c"
                                )
                                .setTitle(
                                    "💣 You hit the bomb!"
                                )
                                .setDescription(
                                    `You lost **${bet.toLocaleString()}** ${db.currency}.`
                                )
                        ],
                        components: []
                    });
                }

                const multiplier =
                    multipliers[
                        revealed.length -
                            1
                    ];

                const payout =
                    Math.floor(
                        bet * multiplier
                    );

                user.cash += payout;

                return msg.edit({
                    embeds: [
                        new EmbedBuilder()
                            .setColor(
                                "#2ecc71"
                            )
                            .setTitle(
                                "💰 You cashed out!"
                            )
                            .setDescription(
                                `You won **${payout.toLocaleString()}** ${db.currency}!`
                            )
                    ],
                    components: []
                });
            }
        );

        return;
    }

    // ==================================================
    // MONEY TOWER
    // ==================================================
    if (
        command === "mt" ||
        command === "moneytower"
    ) {
        const bet = Number(args[0]);

        if (
            !Number.isInteger(bet) ||
            bet < MIN_BET
        ) {
            return message.reply(
                `❌ Minimum bet is **${MIN_BET}** ${db.currency}.`
            );
        }

        if (user.cash < bet) {
            return message.reply(
                "❌ Insufficient funds."
            );
        }

        user.cash -= bet;

        const multipliers = [
            1.5,
            2.1,
            2.3,
            3.6,
            7.6
        ];

        const bombs = Array.from(
            { length: 5 },
            () =>
                Math.floor(
                    Math.random() * 3
                )
        );

        let floor = 0;

        function towerRows(disabled = false) {
            const rows = [];

            for (let f = 0; f < 5; f++) {
                const buttons = [];

                for (let t = 0; t < 3; t++) {
                    const button =
                        new ButtonBuilder()
                            .setCustomId(
                                `mt_${f}_${t}`
                            )
                            .setLabel(
                                `${t + 1}`
                            )
                            .setStyle(
                                ButtonStyle.Primary
                            );

                    if (
                        f < floor ||
                        f !== floor ||
                        disabled
                    ) {
                        button.setDisabled(
                            true
                        );
                    }

                    buttons.push(button);
                }

                rows.push(
                    new ActionRowBuilder()
                        .addComponents(
                            buttons
                        )
                );
            }

            return rows;
        }

        const msg =
            await message.reply({
                embeds: [
                    new EmbedBuilder()
                        .setTitle(
                            "🏢 Money Tower 🏢"
                        )
                        .setColor("#f1c40f")
                        .setDescription(
                            `Climb the Money Tower!\n\nFloor: **1/5**\nMultiplier: **${multipliers[0]}x**`
                        )
                ],
                components: towerRows()
            });

        const collector =
            msg.createMessageComponentCollector({
                filter:
                    i =>
                        i.user.id ===
                        message.author.id,
                time: 120000
            });

        collector.on(
            "collect",
            async interaction => {
                await interaction.deferUpdate();

                const parts =
                    interaction.customId.split(
                        "_"
                    );

                const selectedFloor =
                    Number(parts[1]);

                const selectedTile =
                    Number(parts[2]);

                if (
                    selectedFloor !==
                    floor
                ) {
                    return;
                }

                if (
                    selectedTile ===
                    bombs[floor]
                ) {
                    collector.stop(
                        "bomb"
                    );
                    return;
                }

                floor++;

                if (floor >= 5) {
                    collector.stop(
                        "win"
                    );
                    return;
                }

                await msg.edit({
                    embeds: [
                        new EmbedBuilder()
                            .setTitle(
                                "🏢 Money Tower 🏢"
                            )
                            .setColor(
                                "#f1c40f"
                            )
                            .setDescription(
                                `You passed the floor!\n\nFloor: **${
                                    floor + 1
                                }/5**\nMultiplier: **${multipliers[floor]}x**`
                            )
                    ],
                    components:
                        towerRows()
                });
            }
        );

        collector.on(
            "end",
            async (_, reason) => {
                if (
                    reason === "time"
                ) {
                    user.cash += bet;

                    return msg.edit({
                        content:
                            "⏰ Game timed out. Your bet was returned.",
                        components: []
                    });
                }

                if (
                    reason === "bomb"
                ) {
                    return msg.edit({
                        embeds: [
                            new EmbedBuilder()
                                .setColor(
                                    "#e74c3c"
                                )
                                .setTitle(
                                    "💣 You hit a bomb!"
                                )
                                .setDescription(
                                    `You lost **${bet.toLocaleString()}** ${db.currency}.`
                                )
                        ],
                        components: []
                    });
                }

                const multiplier =
                    multipliers[
                        Math.min(
                            floor - 1,
                            4
                        )
                    ];

                const payout =
                    Math.floor(
                        bet * multiplier
                    );

                user.cash += payout;

                return msg.edit({
                    embeds: [
                        new EmbedBuilder()
                            .setColor(
                                "#2ecc71"
                            )
                            .setTitle(
                                "🏆 You reached the top!"
                            )
                            .setDescription(
                                `You won **${payout.toLocaleString()}** ${db.currency}!`
                            )
                    ],
                    components: []
                });
            }
        );

        return;
    }
});

// ===============================
// LOGIN
// ===============================
client.once("ready", () => {
    console.log(
        `Logged in as ${client.user.tag}`
    );
});

if (!process.env.DISCORD_TOKEN) {
    console.error(
        "DISCORD_TOKEN is missing from Environment Variables."
    );
    process.exit(1);
}

client.login(process.env.DISCORD_TOKEN);