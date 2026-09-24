

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
const PREFIX = '$';let balances = {}; let casinoRole = null; let serverCurrency = '💸'; 
function getUserData(userId) {
    if (!balances[userId]) balances[userId] = { cash: 0, bank: 0 };
    return balances[userId];
}

client.once('ready', () => {
    console.log(`Bot ${client.user.tag} is online!`);
});

client.on('messageCreate', async (message) => {
    if (!message.content.startsWith(PREFIX) || message.author.bot) return;

    const args = message.content.slice(PREFIX.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();

    const hasCasinoAccess = () => {
        if (message.member.permissions.has('Administrator')) return true;
        if (casinoRole && message.member.roles.cache.has(casinoRole)) return true;
        return false;
    };

    if (command === 'role-casino') {
        if (!message.member.permissions.has('Administrator')) return message.reply('❌ אין לך הרשאות מנהל לבצע פקודה זו.');
        const role = message.mentions.roles.first();
        if (!role) return message.reply('❌ נא תייג את הרול שברצונך להגדיר. דוגמה: `$role-casino @CasinoStaff`');
        casinoRole = role.id;
        return message.reply(`✅ הרול המורשה לקזינו עודכן בהצלחה ל: **${role.name}**`);
    }

    if (command === 'addmoney') {
        if (!hasCasinoAccess()) return message.reply('❌ פקודה זו חסומה עבורך. רק מנהלי קזינו מורשים להשתמש בה.');
        
        const target = message.mentions.users.first();
        const type = args[0] ? args[0].toLowerCase() : null;
        const amount = parseInt(args[1]);

        if (!target || !type || isNaN(amount) || amount <= 0 || (type !== 'cash' && type !== 'bank')) {
            return message.reply('❌ מבנה פקודה לא תקין! יש לכתוב: `$addmoney @user [cash/bank] [amount]`');
        }

        const data = getUserData(target.id);
        data[type] += amount;

        return message.reply(`✅ בהצלחה הוסרו **${amount.toLocaleString()}** ${serverCurrency} לתוך ה-${type === 'cash' ? 'מזומן' : 'בנק'} של ${target.username}.`);
    }

    if (command === 'setcurrency') {
        if (!hasCasinoAccess()) return message.reply('❌ פקודה זו חסומה עבורך.');
        const newCurrency = args[0];
        if (!newCurrency) return message.reply('❌ נא ספק אמוג\'י או סימון למטבע החדש.');
        serverCurrency = newCurrency;
        return message.reply(`✅ המטבע של השרת עודכן בהצלחה ל: ${serverCurrency}`);
    }

    if (command === 'bal' || command === 'balance') {
        const targetUser = message.mentions.users.first() || message.author;
        const data = getUserData(targetUser.id);
        const total = data.cash + data.bank;

        const embed = new EmbedBuilder()
            .setAuthor({ name: targetUser.username, iconURL: targetUser.displayAvatarURL() })
            .setDescription(`Use the \`top\` command to view your rank.\n\n• **Money Out:** ${data.cash.toLocaleString()} ${serverCurrency}\n• **Bank Money:** ${data.bank.toLocaleString()} ${serverCurrency}\n• **Total Money:** ${total.toLocaleString()} ${serverCurrency}`)
            .setColor('#10a3de');

        return message.reply({ embeds: [embed] });
    }

    if (command === 'cf' || command === 'chickenfight') {
        const data = getUserData(message.author.id);
        let betInput = args[0];
        let bet = 0;

        if (!betInput) return message.reply('❌ נא לציין סכום הימור. דוגמה: `$cf 100` או `$cf all`');
        if (betInput.toLowerCase() === 'all') {
            bet = data.cash;
        } else {
            bet = parseInt(betInput);
        }

        if (isNaN(bet) || bet <= 0) return message.reply('❌ סכום הימור לא תקין.');
        if (data.cash < bet) return message.reply('❌ אין לך מספיק כסף במזומן (Money Out) עבור הימור זה.');

        const winChance = 0.52; 
        const isWin = Math.random() < winChance;

        if (isWin) {
            data.cash += bet;
            const embed = new EmbedBuilder()
                .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
                .setDescription(`Your chicken won the fight, you won ${bet.toLocaleString()} ${serverCurrency}🐔!\n\nYour chicken's strength (chance of winning): 51%\nYou now have ${data.cash.toLocaleString()} ${serverCurrency}`)
                .setColor('#2ecc71');
            return message.reply({ embeds: [embed] });
        } else {
            data.cash -= bet;
            const embed = new EmbedBuilder()
                .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
                .setDescription(`Your chicken lost the fight... You lost ${bet.toLocaleString()} ${serverCurrency}🐔.\n\nYour chicken's strength (chance of winning): 51%\nYou now have ${data.cash.toLocaleString()} ${serverCurrency}`)
                .setColor('#e74c3c');
            return message.reply({ embeds: [embed] });
        }
    }

    if (command === 'hilo' || command === 'high-low') {
        const data = getUserData(message.author.id);
        const bet = parseInt(args[0]);

        if (isNaN(bet) || bet <= 0) return message.reply('❌ נא לציין סכום הימור תקין. דוגמה: `$hilo 500`');
        if (data.cash < bet) return message.reply('❌ אין לך מספיק כסף במזומן.');

        let card1 = Math.floor(Math.random() * 13) + 1;
        let card2 = Math.floor(Math.random() * 13) + 1;

        if (Math.random() < 0.05) { 
            card2 = card1 > 7 ? Math.floor(Math.random() * (card1 - 1)) + 1 : Math.floor(Math.random() * (14 - card1)) + card1;
        }

        const embed = new EmbedBuilder()
            .setTitle('🎲 Higher or Lower 🎲')
            .setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n\n\`1:\` ${card1}\n\`2:\` ❓\n\n**Higher:** -\n**Same:** 8x\n**Lower:** 1.1x`)
            .setColor('#8e44ad');

        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('higher').setLabel('Higher').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('same').setLabel('Same').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId('lower').setLabel('Lower').setStyle(ButtonStyle.Primary)
        );

        const reply = await message.reply({ embeds: [embed], components: [row] });
        const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 30000 });

        collector.on('collect', async (i) => {
            if (i.user.id !== message.author.id) return i.reply({ content: '❌ זה לא המשחק שלך!', ephemeral: true });
            collector.stop();

            let won = false;
            let multiplier = 1;

            if (i.customId === 'higher' && card2 > card1) { won = true; multiplier = 1.5; }
            if (i.customId === 'lower' && card2 < card1) { won = true; multiplier = 1.1; }
            if (i.customId === 'same' && card2 === card1) { won = true; multiplier = 8; }

            const updatedEmbed = new EmbedBuilder()
                .setTitle('🎲 Higher or Lower - Result 🎲')
                .setColor(won ? '#2ecc71' : '#e74c3c');

            if (won) {
                const winAmount = Math.floor(bet * multiplier);
                data.cash += (winAmount - bet);
                updatedEmbed.setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n\n\`1:\` ${card1}\n\`2:\` **${card2}**\n\n🎉 ניצחת! קיבלת **${winAmount.toLocaleString()}** ${serverCurrency}`);
            } else {
                data.cash -= bet;
                updatedEmbed.setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n\n\`1:\` ${card1}\n\`2:\` **${card2}**\n\n💥 הפסדת את ההימור בסך **${bet.toLocaleString()}** ${serverCurrency}`);
            }

            await i.update({ embeds: [updatedEmbed], components: [] });
        });
    }

    if (command === 'bj' || command === 'blackjack') {
        const data = getUserData(message.author.id);
        const bet = parseInt(args[0]);

        if (isNaN(bet) || bet <= 0) return message.reply('❌ נא לציין סכום הימור תקין. דוגמה: `$bj 1000`');
        if (data.cash < bet) return message.reply('❌ אין לך מספיק כסף במזומן.');

        const drawCard = () => {
            const cards = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
            const card = cards[Math.floor(Math.random() * cards.length)];
            let val = parseInt(card);
            if (['J','Q','K'].includes(card)) val = 10;
            if (card === 'A') val = 11;
            return { display: card, value: val };
        };

        let playerHand = [drawCard(), drawCard()];
        let dealerHand = [drawCard(), drawCard()];

        const getHandValue = (hand) => {
            let sum = hand.reduce((a, b) => a + b.value, 0);
            let aces = hand.filter(c => c.display === 'A').length;
            while (sum > 21 && aces > 0) { sum -= 10; aces--; }
            return sum;
        };

        if (Math.random() < 0.51) {
            while (getHandValue(playerHand) < 15) {
                playerHand = [drawCard(), drawCard()];
            }
        }

        const makeEmbed = (ended = false, statusText = '') => {
            return new EmbedBuilder()
                .setAuthor({ name: `${message.author.username}'s Game` })
                .setTitle('🃏 Blackjack 🃏')
                .setDescription(`**Your Hand**\n${playerHand.map(c => `\`${c.display}\``).join(', ')}\nValue: **${getHandValue(playerHand)}**\n\n**Dealer**\n${ended ? dealerHand.map(c => `\`${c.display}\``).join(', ') : `\`${dealerHand[0].display}\`, 🟥`}\nValue: **${ended ? getHandValue(dealerHand) : dealerHand[0].value}**\n\n${statusText}`)

.setColor(ended ? '#f1c40f' : '#10a3de');
};
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('hit').setLabel('Hit').setStyle(ButtonStyle.Primary),
new ButtonBuilder().setCustomId('stand').setLabel('Stand').setStyle(ButtonStyle.Success),
new ButtonBuilder().setCustomId('double').setLabel('Double').setStyle(ButtonStyle.Danger),
new ButtonBuilder().setCustomId('split').setLabel('Split').setStyle(ButtonStyle.Secondary).setDisabled(playerHand[0].display !== playerHand[1].display)
);
const reply = await message.reply({ embeds: [makeEmbed()], components: [row] });
const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 60000 });
collector.on('collect', async (i) => {
if (i.user.id !== message.author.id) return i.reply({ content: '❌ לא המשחק שלך!', ephemeral: true });
let pVal = getHandValue(playerHand);
if (i.customId === 'hit') {
playerHand.push(drawCard());
pVal = getHandValue(playerHand);
if (pVal > 21) {
collector.stop();
data.cash -= bet;
return i.update({ embeds: [makeEmbed(true, '💥 עברת את 21! הפסדת.')], components: [] });
}
return i.update({ embeds: [makeEmbed()] });
}
if (i.customId === 'stand') {
collector.stop();
let dVal = getHandValue(dealerHand);
while (dVal < 17) {
dealerHand.push(drawCard());
dVal = getHandValue(dealerHand);
}
let msg = '';
if (dVal > 21 || pVal > dVal) {
data.cash += bet;
msg = 🎉 ניצחת והרווחת ${bet.toLocaleString()} ${serverCurrency}!;
} else if (pVal < dVal) {
data.cash -= bet;
msg = ❌ הדילר ניצח. הפסדת ${bet.toLocaleString()} ${serverCurrency}.;
} else {
msg = '👔 תיקו! הכסף חזר אליך.';
}
return i.update({ embeds: [makeEmbed(true, msg)], components: [] });
}
});
}
if (command === 'mines') {
const data = getUserData(message.author.id);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet <= 0) return message.reply('❌ נא לציין סכום הימור תקין. דוגמה: $mines 500');
if (data.cash < bet) return message.reply('❌ אין לך מספיק כסף.');
let board = Array(9).fill('safe');
let mine1 = Math.floor(Math.random() * 9);
let mine2 = Math.floor(Math.random() * 9);
while(mine1 === mine2) { mine2 = Math.floor(Math.random() * 9); }
board[mine1] = 'mine';
board[mine2] = 'mine';
let profit = 0;
let revealedCount = 0;
const getGridRows = (ended = false) => {
const rows = [];
for (let i = 0; i < 3; i++) {
const row = new ActionRowBuilder();
for (let j = 0; j < 3; j++) {
const index = i * 3 + j;
const btn = new ButtonBuilder().setCustomId(mine_${index}).setLabel('⬛').setStyle(ButtonStyle.Secondary);
if (ended) {
btn.setDisabled(true);
btn.setLabel(board[index] === 'mine' ? '💥' : '💎');
}
row.addComponents(btn);
}
rows.push(row);
}
const cashoutRow = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('cashout').setLabel('Cashout').setStyle(ButtonStyle.Success).setDisabled(revealedCount === 0 || ended)
);
rows.push(cashoutRow);
return rows;
};
const embed = new EmbedBuilder()
.setTitle('💣 Mines Game 💣')
.setDescription(**Betting:** ${bet.toLocaleString()} ${serverCurrency}\n\nClick the buttons to reveal rewards. Avoid the 2 hidden mines!)
.setFields({ name: Profit: ${profit} ${serverCurrency}, value: '\u200B' })
.setColor('#e67e22');
const reply = await message.reply({ embeds: [embed], components: getGridRows() });
const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 60000 });
collector.on('collect', async (i) => {
if (i.user.id !== message.author.id) return i.reply({ content: '❌ לא המשחק שלך!', ephemeral: true });
if (i.customId === 'cashout') {
collector.stop();
data.cash += profit;
const winEmbed = new EmbedBuilder().setTitle('💰 Cashout Success! 💰').setDescription(משכת בהצלחה את הרווחים בסך **${profit.toLocaleString()}** ${serverCurrency}!).setColor('#2ecc71');
return i.update({ embeds: [winEmbed], components: getGridRows(true) });
}
const index = parseInt(i.customId.split('_')[1]);
if (board[index] === 'mine') {
collector.stop();
data.cash -= bet;
const loseEmbed = new EmbedBuilder().setTitle('💥 BOOM! 💥').setDescription(פגעת במוקש! הפסדת את כל ההימור בסך **${bet.toLocaleString()}** ${serverCurrency}.).setColor('#e74c3c');
return i.update({ embeds: [loseEmbed], components: getGridRows(true) });
} else {
revealedCount++;
profit += Math.floor(bet * 0.35);
const nextEmbed = new EmbedBuilder()
.setTitle('💣 Mines Game 💣')
.setDescription(**Betting:** ${bet.toLocaleString()} ${serverCurrency})
.setFields({ name: Profit: ${profit} ${serverCurrency}, value: 'נחשפה משבצת בטוחה! המשך או לחץ Cashout' })
.setColor('#e67e22');
return i.update({ embeds: [nextEmbed], components: getGridRows() });
}
});
}
if (command === 'poker' || command === 'texas') {
const data = getUserData(message.author.id);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet <= 0) return message.reply('❌ נא לציין סכום הימור תקין עבור פוקר.');
if (data.cash < bet) return message.reply('❌ אין לך מספיק כסף.');
const suits = ['♠️', '♥️', '♦️', '♣️'];
const values = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
const draw = () => ({ val: values[Math.floor(Math.random()*13)], suit: suits[Math.floor(Math.random()*4)] });
let playerHand = [draw(), draw()];
let botHand = [draw(), draw()];
let communityCards = [draw(), draw(), draw(), draw(), draw()];
const embed = new EmbedBuilder()
.setTitle('🃏 Texas Hold'em (vs Bot) 🃏')
.setDescription(**Your Hand:** \[${playerHand[0].val}${playerHand[0].suit}]` `[${playerHand[1].val}${playerHand[1].suit}]`
Bot Hand: `[❓]` `[❓]`
Community Cards: `[${communityCards[0].val}${communityCards[0].suit}]` `[${communityCards[1].val}${communityCards[1].suit}]` `[${communityCards[2].val}${communityCards[2].suit}]` `[${communityCards[3].val}${communityCards[3].suit}]` `[${communityCards[4].val}${communityCards[4].suit}]``)
.setColor('#1abc9c');
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('call').setLabel('Play Hand / Call').setStyle(ButtonStyle.Success),
new ButtonBuilder().setCustomId('fold').setLabel('Fold').setStyle(ButtonStyle.Danger)
);
const reply = await message.reply({ embeds: [embed], components: [row] });
const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 40000 });
collector.on('collect', async (i) => {
if (i.user.id !== message.author.id) return;
collector.stop();
if (i.customId === 'fold') {
data.cash -= Math.floor(bet / 2);
return i.update({ content: 🏳️ פרשת מהמשחק. הפסדת חצי מסכום ההימור שלך: ${Math.floor(bet / 2)} ${serverCurrency}, embeds: [], components: [] });
}
const playerWins = Math.random() < 0.53;
const resultEmbed = new EmbedBuilder();
if (playerWins) {
data.cash += bet;
resultEmbed.setTitle('🎉 ניצחת ביד! 🎉')
.setDescription(הבוט הראה: \[${botHand[0].val}${botHand[0].suit}]` `[${botHand[1].val}${botHand[1].suit}]`
יש לך יד חזקה יותר! הרווחת ${bet.toLocaleString()} ${serverCurrency}.) .setColor('#2ecc71'); } else { data.cash -= bet; resultEmbed.setTitle('❌ הבוט ניצח! ❌') .setDescription(הבוט הראה: `[${botHand[0].val}${botHand[0].suit}]` `[${botHand[1].val}${botHand[1].suit}]`
לבוט היה שילוב חזק יותר. הפסדת ${bet.toLocaleString()} ${serverCurrency}.`)
.setColor('#e74c3c');
}
await i.update({ embeds: [resultEmbed], components: [] });
});
}
});
client.login(process.env.DISCORD_TOKEN);