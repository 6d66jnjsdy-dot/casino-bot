const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});
const PREFIX = '$';
let balances = {}; let casinoRole = null; let serverCurrency = '💸'; 
function getUserData(userId) {
    if (!balances[userId]) {
        balances[userId] = { cash: 0, bank: 0 };
    }
    return balances[userId];
}

client.once('ready', () => {
    console.log(`Bot ${client.user.tag} is online and ready! Prefix is: ${PREFIX}`);
});

client.on('messageCreate', async (message) => {
    if (!message.content.startsWith(PREFIX) || message.author.bot) return;

    const args = message.content.slice(PREFIX.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();

    // ----------------------------------------------------
    // Command: $role-casino
    // ----------------------------------------------------
    if (command === 'role-casino') {
        if (!message.member.permissions.has('Administrator')) {
            return message.reply('You do not have Administrator permissions to use this command.');
        }
        const role = message.mentions.roles.first();
        if (!role) return message.reply('Please mention a valid role. Example: `$role-casino @Role`');
        casinoRole = role.id;
        return message.reply(`Casino management role has been set to: **${role.name}**`);
    }

    // ----------------------------------------------------
    // Command: $addmoney
    // ----------------------------------------------------
    if (command === 'addmoney') {
        if (!casinoRole) {
            return message.reply('Casino role is not set yet. Please use `$role-casino @Role` first.');
        }
        if (!message.member.roles.cache.has(casinoRole) && !message.member.permissions.has('Administrator')) {
            return message.reply('You do not have access to this command (Staff only).');
        }

        const amount = parseInt(args);
        const type = args?.toLowerCase();
        const targetUser = message.mentions.users.first() || message.author;

        if (isNaN(amount) || !['bank', 'cash'].includes(type)) {
            return message.reply('Invalid syntax. Use: `$addmoney (number) [bank / cash] @mention`');
        }

        const data = getUserData(targetUser.id);
        if (type === 'cash') data.cash += amount;
        if (type === 'bank') data.bank += amount;

        return message.reply(`Successfully added **${amount.toLocaleString()}** ${serverCurrency} to ${targetUser.username}'s ${type}.`);
    }

    // ----------------------------------------------------
    // Command: $bal
    // ----------------------------------------------------
    if (command === 'bal' || command === 'balance') {
        const targetUser = message.mentions.users.first() || message.author;
        const data = getUserData(targetUser.id);
        const total = data.cash + data.bank;

        const embed = new EmbedBuilder()
            .setAuthor({ name: targetUser.username, iconURL: targetUser.displayAvatarURL() })
            .setDescription(
                `Use the \`top\` command to view your rank.\n\n` +
                `• **Money Out:** ${data.cash.toLocaleString()} ${serverCurrency}\n` +
                `• **Bank Money:** ${data.bank.toLocaleString()} ${serverCurrency}\n` +
                `• **Total Money:** ${total.toLocaleString()} ${serverCurrency}`
            )
            .setColor('#10a3de'); 

        return message.reply({ embeds: [embed] });
    }

    // ----------------------------------------------------
    // Command: $currency
    // ----------------------------------------------------
    if (command === 'currency') {
        if (!casinoRole || (!message.member.roles.cache.has(casinoRole) && !message.member.permissions.has('Administrator'))) {
            return message.reply('You do not have permission to change the currency.');
        }
        const newCurrency = args;
        if (!newCurrency) return message.reply('Please provide an emoji or a symbol for the new currency.');
        serverCurrency = newCurrency;
        return message.reply(`Server currency has been updated to: ${serverCurrency}`);
    }

    // ----------------------------------------------------
    // Command: $chicken / $cf
    // ----------------------------------------------------
    if (command === 'chicken' || command === 'cf') {
        const userData = getUserData(message.author.id);
        let bet = args;

        if (bet === 'all') bet = userData.cash;
        else bet = parseInt(bet);

        if (isNaN(bet) || bet <= 0) return message.reply('Please enter a valid betting amount or all.');
        if (userData.cash < bet) return message.reply(`You do not have enough cash (Money Out) for this bet.`);

        const realRoll = Math.random() * 100;
        const isWin = realRoll <= 52; 

        if (isWin) {
            userData.cash += bet;
            const embedWin = new EmbedBuilder()
                .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
                .setDescription(
                    `Your chicken won the fight, you won ${bet.toLocaleString()} ${serverCurrency} Rooster!\n\n` +
                    `Your chicken's strength (chance of winning): 51%\n` +
                    `You now have ${userData.cash.toLocaleString()} ${serverCurrency}`
                )
                .setColor('#2ecc71'); 
            return message.reply({ embeds: [embedWin] });
        } else {
            userData.cash -= bet;
            const embedLoss = new EmbedBuilder()
                .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
                .setDescription(`Your chicken lost the fight... You lost ${bet.toLocaleString()} ${serverCurrency} Rooster.`)
                .setColor('#e74c3c'); 
            return message.reply({ embeds: [embedLoss] });
        }
    }

    // ----------------------------------------------------
    // Command: $high-low
    // ----------------------------------------------------
    if (command === 'high-low' || command === 'hilo') {
        const userData = getUserData(message.author.id);
        let bet = parseInt(args);

        if (isNaN(bet) || bet <= 0) return message.reply('Please enter a valid betting amount.');
        if (userData.cash < bet) return message.reply('You do not have navigate cash for this bet.');

        const firstNumber = Math.floor(Math.random() * 12) + 1; 

        const embed = new EmbedBuilder()
            .setAuthor({ name: `${message.author.username}'s Game` })
            .setTitle('Higher or Lower')
            .setDescription(
                `**Betting Amount:** ${bet.toLocaleString()}\n` +
                `1️⃣ : ${firstNumber}\n` +
                `2️⃣ : \`?\` \n\n` +
                `**Higher:** -\n` +
                `**Same:** 8x\n` +
                `**Lower:** 1.1x`
            )
            .setColor('#34495e');

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('hilo_higher').setLabel('Higher').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('hilo_same').setLabel('Same').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('hilo_lower').setLabel('Lower').setStyle(ButtonStyle.Success)
        );

        const gameMsg = await message.reply({ embeds: [embed], components: [row] });
        const filter = i => i.user.id === message.author.id;
        const collector = gameMsg.createMessageComponentCollector({ filter, componentType: ComponentType.Button, time: 30000 });

        collector.on('collect', async i => {
            await i.deferUpdate();
            let secondNumber;
            const playerBuff = Math.random() * 100;

            if (i.customId === 'hilo_higher') {
                secondNumber = (playerBuff <= 54) ? Math.floor(Math.random() * (14 - (firstNumber + 1))) + firstNumber + 1 : Math.floor(Math.random() * 13) + 1;
            } else if (i.customId === 'hilo_lower') {
                secondNumber = (playerBuff <= 54) ? Math.floor(Math.random() * (firstNumber - 1)) + 1 : Math.floor(Math.random() * 13) + 1;
            } else {
                secondNumber = Math.floor(Math.random() * 13) + 1;
            }

            if (secondNumber > 13) secondNumber = 13;
            if (secondNumber < 1) secondNumber = 1;

            let resultText = '';
            let finalWin = false;

            if (i.customId === 'hilo_higher' && secondNumber > firstNumber) finalWin = true;
            if (i.customId === 'hilo_lower' && secondNumber < firstNumber) finalWin = true;
            if (i.customId === 'hilo_same' && secondNumber === firstNumber) finalWin = true;

            if (finalWin) {
                let multiplier = i.customId === 'hilo_same' ? 8 : (i.customId === 'hilo_lower' ? 1.1 : 1.5);
                let winnings = Math.floor(bet * multiplier);
                userData.cash += (winnings - bet);
                resultText = `**You won!** The second number was **${secondNumber}**. You won ${winnings} ${serverCurrency}`;
            } else {
                userData.cash -= bet;
                resultText = `**You lost.** The second number was **${secondNumber}**. You lost ${bet} ${serverCurrency}`;
            }

            const finalEmbed = new EmbedBuilder()
                .setAuthor({ name: `${message.author.username}'s Game` })
                .setTitle('Higher or Lower - Result')
                .setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n1️⃣ : ${firstNumber}\n2️⃣ : **${secondNumber}**\n\n${resultText}`)
                .setColor(finalWin ? '#2ecc71' : '#e74c3c');


await gameMsg.edit({ embeds: [finalEmbed], components: [] });
collector.stop();
});
});
// ----------------------------------------------------
// Command: $mines
// ----------------------------------------------------
if (command === 'mines') {
const userData = getUserData(message.author.id);
let bet = parseInt(args);
if (isNaN(bet) || bet <= 0) return message.reply('Usage: $mines [bet amount]');
if (userData.cash < bet) return message.reply('You do not have enough cash.');
const embed = new EmbedBuilder()
.setAuthor({ name: ${message.author.username}'s Mines })
.setDescription('Click the squares to reveal paths, avoid the hidden mines!')
.addFields({ name: 'Current Profit', value: Profit: 0 ${serverCurrency} })
.setColor('#2c3e50');
const row1 = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('mine_0').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_1').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_2').setLabel('⬜').setStyle(ButtonStyle.Secondary)
);
const row2 = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('mine_3').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_4').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_5').setLabel('⬜').setStyle(ButtonStyle.Secondary)
);
const row3 = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('mine_6').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_7').setLabel('⬜').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('mine_8').setLabel('⬜').setStyle(ButtonStyle.Secondary)
);
const controlRow = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('mine_cashout').setLabel('Cashout').setStyle(ButtonStyle.Success)
);
await message.reply({ embeds: [embed], components: [row1, row2, row3, controlRow] });
}
// ----------------------------------------------------
// Command: $blackjack
// ----------------------------------------------------
if (command === 'blackjack' || command === 'bj') {
const userData = getUserData(message.author.id);
let bet = parseInt(args);
if (isNaN(bet) || bet <= 0) return message.reply('Usage: $blackjack [bet amount]');
if (userData.cash < bet) return message.reply('You do not have enough cash.');
const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
function drawCard() {
const val = values[Math.floor(Math.random() * values.length)];
return { display: \${val}``, value: val };
}
const bjWinChance = Math.random() * 100;
let playerHand, dealerHand;
if (bjWinChance <= 51) {
playerHand = [ { display: '3', value: '3' }, { display: '3', value: '3' } ];
dealerHand = [ { display: 'Q', value: 'Q' }, { display: '5', value: '5' } ];
} else {
playerHand = [ drawCard(), drawCard() ];
dealerHand = [ drawCard(), drawCard() ];
}
function calculateScore(hand) {
let score = 0;
let aces = 0;
for (let card of hand) {
if (['J', 'Q', 'K'].includes(card.value)) score += 10;
else if (card.value === 'A') { score += 11; aces++; }
else score += parseInt(card.value);
}
while (score > 21 && aces > 0) { score -= 10; aces--; }
return score;
}
const embed = new EmbedBuilder()
.setAuthor({ name: ${message.author.username}'s Game })
.setTitle('Blackjack')
.setDescription(**Your Hand**\n${playerHand.map(c => c.display).join(', ')}\n\nValue: **${calculateScore(playerHand)}**\n\n**Dealer**\n${dealerHand.display}, 🟥\n\nValue: **${calculateScore([dealerHand])}**)
.setColor('#f1c40f');
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('bj_hit').setLabel('Hit').setStyle(ButtonStyle.Primary),
new ButtonBuilder().setCustomId('bj_stand').setLabel('Stand').setStyle(ButtonStyle.Success),
new ButtonBuilder().setCustomId('bj_double').setLabel('Double').setStyle(ButtonStyle.Danger),
new ButtonBuilder().setCustomId('bj_split').setLabel('Split').setStyle(ButtonStyle.Secondary)
);
await message.reply({ embeds: [embed], components: [row] });
}
// ----------------------------------------------------
// Command: $texas-holdem
// ----------------------------------------------------
if (command === 'texas-holdem' || command === 'poker') {
const embed = new EmbedBuilder()
.setTitle('Texas Hold'em Poker')
.setDescription('Select your preferred game mode using the buttons below:')
.setColor('#1abc9c');
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('poker_bot').setLabel('Play against bot').setStyle(ButtonStyle.Primary),
new ButtonBuilder().setCustomId('poker_multi').setLabel('Multiplayer (4 Players)').setStyle(ButtonStyle.Success)
);
return message.reply({ embeds: [embed], components: [row] });
}
});
// משיכת הטוקן בצורה מאובטחת מהגדרות השרת
client.login(process.env.DISCORD_TOKEN);