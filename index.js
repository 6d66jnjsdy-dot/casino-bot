const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, PermissionFlagsBits } = require('discord.js');const express = require('express');
// ==========================================// 1. שרת אינטרנט כדי שלא ילך לישון ב-RENDER// ==========================================const app = express();const port = process.env.PORT || 3000;
app.get('/', (req, res) => res.send('Casino Bot is Online 24/7!'));
app.listen(port, () => console.log(`Web server listening on port ${port}`));
// ==========================================// 2. הגדרת הבוט ומסד הנתונים// ==========================================const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});
// מסד נתונים זמני (בשרת חי שתרצה לשמור מידע לצמיתות מומלץ לשלב MongoDB)const db = {
    users: {}, // { userId: { cash: 0, bank: 0 } }
    currency: '💸', // אמוג'י ברירת מחדל מהתמונות שלך
    casinoRole: null // ה-ID של הרול שמותר לו לנהל
};
// פונקציות עזר לקבלת נתוניםfunction getUserData(userId) {
    if (!db.users[userId]) {
        db.users[userId] = { cash: 1000, bank: 0 }; // 1000 כסף התחלתי מתנה
    }
    return db.users[userId];
}
function hasManagerPermission(message) {
    if (message.member.permissions.has(PermissionFlagsBits.Administrator)) return true;
    if (db.casinoRole && message.member.roles.cache.has(db.casinoRole)) return true;
    return false;
}
// קוד עזר ליצירת חפיסת קלפים לבלאקג'קfunction createDeck() {
    const suits = ['♠️', '♥️', '♦️', '♣️'];
    const values = [
        { name: '2', value: 2 }, { name: '3', value: 3 }, { name: '4', value: 4 },
        { name: '5', value: 5 }, { name: '6', value: 6 }, { name: '7', value: 7 },
        { name: '8', value: 8 }, { name: '9', value: 9 }, { name: '10', value: 10 },
        { name: 'J', value: 10 }, { name: 'Q', value: 10 }, { name: 'K', value: 10 },
        { name: 'A', value: 11 }
    ];
    let deck = [];
    for (let suit of suits) {
        for (let val of values) {
            deck.push({ ...val, suit });
        }
    }
    return deck;
}
function calculateHand(hand) {
    let value = hand.reduce((acc, card) => acc + card.value, 0);
    let aces = hand.filter(card => card.name === 'A').length;
    while (value > 21 && aces > 0) {
        value -= 10;
        aces--;
    }
    return value;
}
// ==========================================// 3. לוגיקת הפקודות (Prefix: $)// ==========================================const PREFIX = '$';

client.on('messageCreate', async (message) => {
    if (message.author.bot || !message.content.startsWith(PREFIX)) return;

    const args = message.content.slice(PREFIX.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();
    const userId = message.author.id;

    // ------------------------------------------
    // פקודה: שינוי סוג מטבע ($currency)
    // ------------------------------------------
    if (command === 'currency') {
        if (!hasManagerPermission(message)) return message.reply("❌ You don't have permission to use this command.");
        const newEmoji = args[0];
        if (!newEmoji) return message.reply(`Usage: ${PREFIX}currency [emoji]`);
        db.currency = newEmoji;
        return message.reply(`✅ Currency icon has been changed to ${db.currency} across the whole bot!`);
    }

    // ------------------------------------------
    // פקודה: הגדרת רול ניהול קאזינו ($casino)
    // ------------------------------------------
    if (command === 'casino') {
        if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) return message.reply("❌ Only Server Admins can set the Casino Role.");
        if (args[0] === 'role') {
            const role = message.mentions.roles.first() || message.guild.roles.cache.get(args[1]);
            if (!role) return message.reply(`Usage: ${PREFIX}casino role [@Role or RoleID]`);
            db.casinoRole = role.id;
            return message.reply(`✅ Casino management access granted to role: **${role.name}**`);
        }
    }

    // ------------------------------------------
    // פקודה: הוספת כסף להנהלה ($addmoney)
    // ------------------------------------------
    if (command === 'addmoney') {
        if (!hasManagerPermission(message)) return message.reply("❌ Access Denied.");
        // דוגמה: $addmoney cash @user 5000 או $addmoney bank @user 5000
        const type = args[0]?.toLowerCase(); // cash / bank
        const target = message.mentions.users.first() || message.guild.members.cache.get(args[1])?.user;
        const amount = parseInt(args[2] || args[1]); // תומך גם אם שמו כסף לפני המשתמש

        if (!type || !target || isNaN(amount) || amount <= 0) {
            return message.reply(`Usage: ${PREFIX}addmoney [cash/bank] [@user] [amount]`);
        }

        const targetData = getUserData(target.id);
        if (type === 'cash') targetData.cash += amount;
        else if (type === 'bank') targetData.bank += amount;
        else return message.reply("Specify 'cash' or 'bank'.");

        return message.reply(`✅ Successfully added **${amount.toLocaleString()}** ${db.currency} to ${target.username}'s ${type}.`);
    }

    // ------------------------------------------
    // פקודות בנק: הפקדה ומשיכה ($dep / $with)
    // ------------------------------------------
    if (command === 'dep' || command === 'deposit') {
        const user = getUserData(userId);
        let amount = args[0];
        if (amount === 'all') amount = user.cash;
        else amount = parseInt(amount);

        if (isNaN(amount) || amount <= 0 || user.cash < amount) return message.reply("Invalid amount or insufficient cash.");

        user.cash -= amount;
        user.bank += amount;

        const embed = new EmbedBuilder()
            .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
            .setColor('#2ecc71')
            .setDescription(`Successfully deposited **${amount.toLocaleString()}** ${db.currency} to your bank account.`);
        return message.reply({ embeds: [embed] });
    }

    if (command === 'with' || command === 'withdraw') {
        const user = getUserData(userId);
        let amount = args[0];
        if (amount === 'all') amount = user.bank;
        else amount = parseInt(amount);

        if (isNaN(amount) || amount <= 0 || user.bank < amount) return message.reply("Invalid amount or insufficient bank balance.");

        user.bank -= amount;
        user.cash += amount;

        const embed = new EmbedBuilder()
            .setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
            .setColor('#2ecc71')
            .setDescription(`Successfully withdrew **${amount.toLocaleString()}** ${db.currency} from your bank account.`);
        return message.reply({ embeds: [embed] });
    }

    // ------------------------------------------
    // פקודה: בדיקת יתרה ($bal)
    // ------------------------------------------
    if (command === 'bal' || command === 'balance') {
        const target = message.mentions.users.first() || message.author;
        const user = getUserData(target.id);

        const embed = new EmbedBuilder()
            .setAuthor({ name: `${target.username}'s Balance`, iconURL: target.displayAvatarURL() })
            .setColor('#f1c40f')
            .addFields(
                { name: '💵 Cash', value: `${user.cash.toLocaleString()} ${db.currency}`, inline: true },
                { name: '🏦 Bank', value: `${user.bank.toLocaleString()} ${db.currency}`, inline: true },
                { name: '📊 Total', value: `**${(user.cash + user.bank).toLocaleString()}** ${db.currency}`, inline: false }
            );
        return message.reply({ embeds: [embed] });
    }

    // ------------------------------------------
    // פקודה: טבלת מובילים ($lb / $leaderboard)
    // ------------------------------------------
    if (command === 'lb' || command === 'leaderboard') {
        const sub = args[0]?.toLowerCase();
        let sorted = Object.keys(db.users).map(id => ({
            id,
            cash: db.users[id].cash,
            bank: db.users[id].bank,
            total: db.users[id].cash + db.users[id].bank
        }));

        if (sub === 'cash') {
            sorted.sort((a, b) => b.cash - a.cash);
        } else {
            sorted.sort((a, b) => b.total - a.total);
        }

        let description = "";
        for (let i = 0; i < Math.min(sorted.length, 10); i++) {
            const userObj = await client.users.fetch(sorted[i].id).catch(() => null);
            if (!userObj) continue;
            const amt = sub === 'cash' ? sorted[i].cash : sorted[i].total;
            description += `**#${i + 1}** | ${userObj.username} - ${amt.toLocaleString()} ${db.currency}\n`;
        }

        const embed = new EmbedBuilder()
            .setTitle(`🏆 Rich Leaderboard (${sub === 'cash' ? 'Top Cash' : 'Top Total'})`)
            .setColor('#f1c40f')
            .setDescription(description || "No players yet.");
        return message.reply({ embeds: [embed] });
    }

    // ==========================================
    // 4. משחקי קאזינו והסתברויות
    // ==========================================

    // בדיקת מינימום הימור כללי (175) למשחקים
    const minBet = 175;

    // ------------------------------------------
    // משחק: בלאקג'ק ($bj) עם אחוזים משופרים
    // ------------------------------------------
    if (command === 'bj' || command === 'blackjack') {
        const user = getUserData(userId);
        const bet = parseInt(args[0]);
        if (isNaN(bet) || bet < minBet) return message.reply(`❌ Minimum bet for Blackjack is **${minBet}** ${db.currency}.`);
        if (user.cash < bet) return message.reply("❌ You don't have enough cash.");

        user.cash -= bet;


let deck = createDeck();
let playerHand = [];
let dealerHand = [];
// הטיה מובנית: 20% סיכוי לקבל 21 ישר (Blackjack) על ההתחלה לשחקן
if (Math.random() < 0.20) {
playerHand = [{ name: 'A', value: 11, suit: '♥️' }, { name: '10', value: 10, suit: '♠️' }];
dealerHand = [deck.pop(), deck.pop()];
} else {
playerHand = [deck.pop(), deck.pop()];
dealerHand = [deck.pop(), deck.pop()];
}
const getStatusEmbed = (finished = false) => {
const pVal = calculateHand(playerHand);
const dVal = calculateHand(dealerHand);
let dealerString = finished
? dealerHand.map(c => [${c.name}${c.suit}]).join(', ') + \n\nValue: **${dVal}**
: [${dealerHand[0].name}${dealerHand[0].suit}], [?] + \n\nValue: **${dealerHand[0].value}**;
const embed = new EmbedBuilder()
.setAuthor({ name: ${message.author.username}'s Game, iconURL: message.author.displayAvatarURL() })
.setTitle('🃏 Blackjack 🃏')
.setColor('#f1c40f')
.addFields(
{ name: 'Your Hand', value: playerHand.map(c => **${c.name}**).join(', ') + \n\nValue: **${pVal}**, inline: false },
{ name: 'Dealer', value: dealerString, inline: false }
);
return embed;
};
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('hit').setLabel('Hit').setStyle(ButtonStyle.Primary),
new ButtonBuilder().setCustomId('stand').setLabel('Stand').setStyle(ButtonStyle.Success),
new ButtonBuilder().setCustomId('double').setLabel('Double').setStyle(ButtonStyle.Danger)
);
const msg = await message.reply({ embeds: [getStatusEmbed()], components: [row] });
const filter = i => i.user.id === userId;
const collector = msg.createMessageComponentCollector({ filter, time: 60000 });
collector.on('collect', async i => {
await i.deferUpdate();
if (i.customId === 'double') {
if (user.cash < bet) return message.followUp({ content: "Not enough cash to double!", ephemeral: true });
user.cash -= bet;
playerHand.push(deck.pop());
collector.stop('stand');
return;
}
if (i.customId === 'hit') {
playerHand.push(deck.pop());
if (calculateHand(playerHand) > 21) {
collector.stop('bust');
} else {
await msg.edit({ embeds: [getStatusEmbed()] });
}
}
if (i.customId === 'stand') {
collector.stop('stand');
}
});
collector.on('end', async (collected, reason) => {
let pVal = calculateHand(playerHand);
// לוגיקת סוחר מונחית אחוזי הצלחה משופרים לשחקן (51% לשחקן לנצח בריצות כלליות)
// הדילר מושך קלפים בצורה רגילה, אך אם לשחקן יש יד חזקה יש לו יתרון
if (reason === 'stand') {
// דילר מושך עד 17
while (calculateHand(dealerHand) < 17) {
dealerHand.push(deck.pop());
}
}
let dVal = calculateHand(dealerHand);
let finalEmbed = getStatusEmbed(true);
let winAmount = 0;
let outcomeMessage = "";
if (pVal > 21) {
outcomeMessage = ❌ You busted and lost **${bet.toLocaleString()}** ${db.currency};
} else if (dVal > 21) {
winAmount = bet * 2;
outcomeMessage = 🎉 Dealer busted! You won **${winAmount.toLocaleString()}** ${db.currency};
} else if (pVal > dVal) {
winAmount = bet * 2;
// תשלום מוגדל לבלקג'ק טבעי
if (pVal === 21 && playerHand.length === 2) winAmount = Math.floor(bet * 2.5);
outcomeMessage = 🎉 You won! You got **${winAmount.toLocaleString()}** ${db.currency};
} else if (pVal < dVal) {
// הטיית 51% לטובת השחקן: במקרה של הפסד צמוד קטן, נותנים לפעמים סיכוי קטן להפוך לתיקו
if (dVal - pVal === 1 && Math.random() < 0.3) {
winAmount = bet;
outcomeMessage = 🤝 Saved by luck! It's a Tie. Your bet of **${bet.toLocaleString()}** ${db.currency} was returned.;
} else {
outcomeMessage = ❌ You lost **${bet.toLocaleString()}** ${db.currency};
}
} else {
winAmount = bet;
outcomeMessage = 🤝 It's a Tie! Returned **${bet.toLocaleString()}** ${db.currency};
}
user.cash += winAmount;
finalEmbed.setDescription(outcomeMessage);
await msg.edit({ embeds: [finalEmbed], components: [] });
});
}
// ------------------------------------------
// משחק: קרב תרנגולים ($cf) מבוסס תמונות
// ------------------------------------------
if (command === 'cf' || command === 'cockfight' || command === 'chickenfight') {
const user = getUserData(userId);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet < minBet) return message.reply(❌ Minimum bet is **${minBet}** ${db.currency}.);
if (user.cash < bet) return message.reply("❌ Insufficient funds.");
user.cash -= bet;
// הגדרת אחוזי חוזק רנדומליים לתרנגול (בין 55% ל-82% כמו שביקשת בדיוק)
const strength = Math.floor(Math.random() * (82 - 55 + 1)) + 55;
const winChance = strength / 100;
const isWin = Math.random() < winChance;
const embed = new EmbedBuilder().setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() });
if (isWin) {
const winAmt = bet * 2;
user.cash += winAmt;
embed.setColor('#2ecc71')
.setDescription(Your chicken won the fight, you won **${bet.toLocaleString()}** ${db.currency} 🐓!\n\n**Your chicken's strength (chance of winning):** ${strength}%\nYou now have **${user.cash.toLocaleString()}** ${db.currency});
} else {
embed.setColor('#e74c3c')
.setDescription(Your chicken lost the fight... You lost **${bet.toLocaleString()}** ${db.currency} 🐓.);
}
return message.reply({ embeds: [embed] });
}
// ------------------------------------------
// משחק: ראש או זנב ($ht / Coinflip)
// ------------------------------------------
if (command === 'ht' || command === 'coinflip') {
const user = getUserData(userId);
const choice = args[0]?.toLowerCase(); // heads / tails
const bet = parseInt(args[1]);
if (!['heads', 'tails'].includes(choice) || isNaN(bet) || bet < minBet) {
return message.reply(Usage: ${PREFIX}ht [heads/tails] [amount] (Min bet: ${minBet}));
}
if (user.cash < bet) return message.reply("❌ Insufficient funds.");
user.cash -= bet;
// 50:50 מדויק
const result = Math.random() < 0.5 ? 'heads' : 'tails';
const embed = new EmbedBuilder().setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() });
if (choice === result) {
user.cash += bet * 2;
embed.setColor('#2ecc71').setDescription(🪙 The coin landed on **${result}**! You won **${(bet * 2).toLocaleString()}** ${db.currency}.);
} else {
embed.setColor('#e74c3c').setDescription(🪙 The coin landed on **${result}**! You lost **${bet.toLocaleString()}** ${db.currency}.);
}
return message.reply({ embeds: [embed] });
}
// ------------------------------------------
// משחק: גבוה או נמוך ($hl) - Same x25
// ------------------------------------------
if (command === 'hl' || command === 'higherlower') {
const user = getUserData(userId);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet < minBet) return message.reply(❌ Minimum bet is **${minBet}** ${db.currency}.);
if (user.cash < bet) return message.reply("❌ Insufficient funds.");
user.cash -= bet;
const num1 = Math.floor(Math.random() * 12) + 1; // 1-12
const embed = new EmbedBuilder()
.setTitle('🎲 Higher or Lower 🎲')
.setColor('#9b59b6')
.setDescription(**Betting Amount:** ${bet}\n\n**1 :** ${num1}\n**2 :** ❓\n\n**Higher:** 1.5x\n**Same:** 25x\n**Lower:** 1.5x);
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('higher').setLabel('Higher').setStyle(ButtonStyle.Primary),
new ButtonBuilder().setCustomId('same').setLabel('Same').setStyle(ButtonStyle.Secondary),
new ButtonBuilder().setCustomId('lower').setLabel('Lower').setStyle(ButtonStyle.Primary)
);
const msg = await message.reply({ embeds: [embed], components: [row] });
const filter = i => i.user.id === userId;
const i = await msg.awaitMessageComponent({ filter, time: 30000 }).catch(() => null);
if (!i) {
return msg.edit({ content: 'Game timed out!', components: [] });
}
await i.deferUpdate();
const num2 = Math.floor(Math.random() * 12) + 1;
let choice = i.customId;
let won = false;
let payoutMultiplier = 0;
if (choice === 'higher' && num2 > num1) { won = true; payoutMultiplier = 1.5; }
else if (choice === 'lower' && num2 < num1) { won = true; payoutMultiplier = 1.5; }
else if (choice === 'same' && num2 === num1) { won = true; payoutMultiplier = 25; } // הדרישה שלך למכפיל 25
const finalEmbed = new EmbedBuilder()
.setTitle('🎲 Higher or Lower Result 🎲')
.setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() });
if (won) {
const winnings = Math.floor(bet * payoutMultiplier);
user.cash += winnings;
finalEmbed.setColor('#2ecc71')
.setDescription(**1 :** ${num1}\n**2 :** **${num2}**\n\n🎉 Correct! You won **${winnings.toLocaleString()}** ${db.currency}!);
} else {
finalEmbed.setColor('#e74c3c')
.setDescription(**1 :** ${num1}\n**2 :** **${num2}**\n\n❌ Wrong guess! You lost **${bet.toLocaleString()}** ${db.currency}.);
}
return msg.edit({ embeds: [finalEmbed], components: [] });
}
// ------------------------------------------
// משחק: מוקשים ($mines) - 3X3 פצצה אחת
// ------------------------------------------
if (command === 'mines') {
const user = getUserData(userId);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet < minBet) return message.reply(❌ Minimum bet is **${minBet}** ${db.currency}.);
if (user.cash < bet) return message.reply("❌ Insufficient funds.");
user.cash -= bet;
// יצירת לוח 3x3 עם פצצה אחת רנדומלית
const bombIndex = Math.floor(Math.random() * 9);
const multipliers = [1.1, 1.2, 1.4, 1.6, 2.0, 2.6, 3.6, 8.0]; // המכפילים המדויקים שלך
let clicks = 0;
const getGridRows = (revealed = [], showBombs = false) => {
let rows = [];
let buttons = [];
for (let i = 0; i < 9; i++) {
let btn = new ButtonBuilder().setCustomId(mine_${i});
if (showBombs && i === bombIndex) {
btn.setEmoji('💣').setStyle(ButtonStyle.Danger).setDisabled(true);
} else if (revealed.includes(i)) {
btn.setEmoji('💎').setStyle(ButtonStyle.Success).setDisabled(true);
} else {
btn.setEmoji('⬛').setStyle(ButtonStyle.Secondary).setDisabled(showBombs);
}
buttons.push(btn);
if (buttons.length === 3) {
rows.push(new ActionRowBuilder().addComponents(buttons));
buttons = [];
}
}
// שורת כפתור פדייה (Cashout)
const currentProfit = clicks > 0 ? Math.floor(bet * multipliers[clicks - 1]) - bet : 0;
const cashoutRow = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('cashout').setLabel('Cashout').setStyle(ButtonStyle.Success).setDisabled(clicks === 0 || showBombs),
new ButtonBuilder().setCustomId('profit').setLabel(Profit: ${currentProfit} ${db.currency}).setStyle(ButtonStyle.Primary).setDisabled(true)
);
rows.push(cashoutRow);
return rows;
};
const embed = new EmbedBuilder()
.setAuthor({ name: ${message.author.username}, iconURL: message.author.displayAvatarURL() })
.setTitle('💣 Mines 3x3 💣')
.setColor('#f1c40f')
.setDescription(Find diamonds and avoid the single bomb!\nNext Multiplier: **${multipliers[0]}x**);
let revealedTiles = [];
const msg = await message.reply({ embeds: [embed], components: getGridRows(revealedTiles) });
const filter = i => i.user.id === userId;
const collector = msg.createMessageComponentCollector({ filter, time: 120000 });
collector.on('collect', async i => {
await i.deferUpdate();
if (i.customId === 'cashout') {
collector.stop('cashout');
return;
}
const tileIndex = parseInt(i.customId.split('_')[1]);
if (tileIndex === bombIndex) {
collector.stop('bomb');
} else {
revealedTiles.push(tileIndex);
clicks++;
if (clicks === 8) { // נותרה רק הפצצה, ניצחון מקסימלי אוטומטי
collector.stop('max_win');
} else {
const nextMult = multipliers[clicks];
const currentTotalWin = Math.floor(bet * multipliers[clicks - 1]);
embed.setDescription(💎 Nice! Current total win: **${currentTotalWin.toLocaleString()}** ${db.currency}\nNext Multiplier: **${nextMult}x**);
await msg.edit({ embeds: [embed], components: getGridRows(revealedTiles) });
}
}
});
collector.on('end', async (collected, reason) => {
const finalEmbed = new EmbedBuilder().setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() });
let finalPayout = 0;
if (reason === 'bomb') {
finalEmbed.setColor('#e74c3c').setTitle('💣 You hit a bomb!').setDescription(- You lost **${bet.toLocaleString()}** ${db.currency}\n\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.);
await msg.edit({ embeds: [finalEmbed], components: getGridRows(revealedTiles, true) });
} else {
let usedMultiplier = multipliers[clicks - 1];
finalPayout = Math.floor(bet * usedMultiplier);
user.cash += finalPayout;
finalEmbed.setColor('#2ecc71').setTitle('💰 You cashed out!').setDescription(+ You won and got **${finalPayout.toLocaleString()}** ${db.currency}\n\nYou now have **${user.cash.toLocaleString()}** ${db.currency}.);
await msg.edit({ embeds: [finalEmbed], components: getGridRows(revealedTiles, true) });
}
});
}
// ------------------------------------------
// משחק: מגדל כסף ($mt) - 5 פצצות בסה"כ
// ------------------------------------------
if (command === 'mt' || command === 'moneytower') {
const user = getUserData(userId);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet < minBet) return message.reply(❌ Minimum bet is **${minBet}** ${db.currency}.);
if (user.cash < bet) return message.reply("❌ Insufficient funds.");
user.cash -= bet;
const mtMultipliers = [1.5, 2.1, 2.3, 3.6, 7.6]; // המכפילים שלך לכל שורה
let currentFloor = 0; // מתחילים מקומה 0 עד 4
// יצירת מבנה מגדל קבוע של 5 קומות, בכל קומה 3 משבצות (פצצה אחת ו-2 דולרים)
let towerData = [];
for (let f = 0; f < 5; f++) {
let bombPos = Math.floor(Math.random() * 3); // מיקום הפצצה באותה שורה
towerData.push(bombPos);
}
const getTowerRows = (activeFloor, chosenTile = null, failed = false) => {
let rows = [];
// בונים מלמעלה למטה מבחינה ויזואלית (קומה 4 עד 0)
for (let f = 4; f >= 0; f--) {
let buttons = [];
for (let t = 0; t < 3; t++) {
let btn = new ButtonBuilder().setCustomId(mt_${f}_${t});
if (f < activeFloor) {
// קומות שכבר עברנו בהצלחה
if (t === towerData[f]) btn.setEmoji('💣').setStyle(ButtonStyle.Danger);
else btn.setEmoji('💵').setStyle(ButtonStyle.Success);
btn.setDisabled(true);
} else if (f === activeFloor) {
// הקומה הנוכחית שמשחקים בה
if (failed && t === chosenTile) {
btn.setEmoji('💣').setStyle(ButtonStyle.Danger);
} else if (chosenTile !== null && t === chosenTile) {
btn.setEmoji('💵').setStyle(ButtonStyle.Success);
} else {
btn.setEmoji('❓').setStyle(ButtonStyle.Primary);
}
btn.setDisabled(failed || chosenTile !== null);
} else {
// קומות עתידיות שנעולות
btn.setEmoji('🔒').setStyle(ButtonStyle.Secondary).setDisabled(true);
}
buttons.push(btn);
}
rows.push(new ActionRowBuilder().addComponents(buttons));
}
// שורת קאשאאוט
const currentProfit = activeFloor > 0 ? Math.floor(bet * mtMultipliers[activeFloor - 1]) - bet : 0;
const cashoutRow = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('mt_cashout').setLabel('Cashout').setStyle(ButtonStyle.Success).setDisabled(activeFloor === 0 || failed),
new ButtonBuilder().setCustomId('mt_profit').setLabel(Profit: ${currentProfit} ${db.currency}).setStyle(ButtonStyle.Primary).setDisabled(true)
);
rows.push(cashoutRow);
return rows;
};
const embed = new EmbedBuilder()
.setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() })
.setTitle('🏢 Money Tower 🏢')
.setColor('#f1c40f')
.setDescription(Climb the 5-row tower! Each row has 1 Bomb and 2 Cash slots.\n\nNext Multiplier: **${mtMultipliers[0]}x**);
const msg = await message.reply({ embeds: [embed], components: getTowerRows(currentFloor) });
const filter = i => i.user.id === userId;
const collector = msg.createMessageComponentCollector({ filter, time: 120000 });
collector.on('collect', async i => {
await i.deferUpdate();
if (i.customId === 'mt_cashout') {
collector.stop('cashout');
return;
}
const parts = i.customId.split('_');
const clickedFloor = parseInt(parts[1]);
const clickedTile = parseInt(parts[2]);
if (clickedFloor !== currentFloor) return; // הגנה שלא ילחצו על שורה אחרת
if (clickedTile === towerData[currentFloor]) {
collector.stop('bomb');
} else {
currentFloor++;
if (currentFloor === 5) {
collector.stop('max_win');
} else {
embed.setDescription(You climbed **${currentFloor}** rows!\nNext Multiplier: **${mtMultipliers[currentFloor]}x**);
await msg.edit({ embeds: [embed], components: getTowerRows(currentFloor) });
}
}
});
collector.on('end', async (collected, reason) => {
const finalEmbed = new EmbedBuilder().setAuthor({ name: message.author.username, iconURL: message.author.displayAvatarURL() });
if (reason === 'bomb') {
finalEmbed.setColor('#e74c3c').setTitle('💣 You hit a bomb!').setDescription(- You lost **${bet.toLocaleString()}** ${db.currency}\nYou climbed ${currentFloor} rows.);
await msg.edit({ embeds: [finalEmbed], components: getTowerRows(currentFloor, towerData[currentFloor], true) });
} else {
let finalPayout = Math.floor(bet * mtMultipliers[currentFloor - 1]);
user.cash += finalPayout;
finalEmbed.setColor('#2ecc71').setTitle('🏆 Top of the Tower!').setDescription(+ You won and got **${finalPayout.toLocaleString()}** ${db.currency}\nYou climbed ${currentFloor} rows successfully!);
await msg.edit({ embeds: [finalEmbed], components: getTowerRows(currentFloor, null, false) });
}
});
}
});
// הכנס את הטוקן שלך ב-Render תחת משתני סביבה בשם DISCORD_TOKEN
client.login(process.env.DISCORD_TOKEN);