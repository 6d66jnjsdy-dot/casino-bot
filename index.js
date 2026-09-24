

const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');
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
        if (!message.member.permissions.has('Administrator')) return message.reply('❌ No admin perms.');
        const role = message.mentions.roles.first();
        if (!role) return message.reply('❌ Mention a role.');
        casinoRole = role.id;
        return message.reply(`✅ Role set to: **${role.name}**`);
    }

    if (command === 'addmoney') {
        if (!hasCasinoAccess()) return message.reply('❌ Staff only.');
        const target = message.mentions.users.first();
        const type = args[1] ? args[1].toLowerCase() : null;
        const amount = parseInt(args[2]);
        if (!target || !type || isNaN(amount) || amount <= 0 || (type !== 'cash' && type !== 'bank')) {
            return message.reply('❌ Use: `$addmoney @user [cash/bank] [amount]`');
        }
        const data = getUserData(target.id);
        data[type] += amount;
        return message.reply(`✅ Added **${amount.toLocaleString()}** ${serverCurrency} to ${target.username}'s ${type}.`);
    }

    if (command === 'setcurrency') {
        if (!hasCasinoAccess()) return message.reply('❌ Staff only.');
        const newCurrency = args[0];
        if (!newCurrency) return message.reply('❌ Provide an emoji.');
        serverCurrency = newCurrency;
        return message.reply(`✅ Currency set to: ${serverCurrency}`);
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
        let bet = betInput && betInput.toLowerCase() === 'all' ? data.cash : parseInt(betInput);
        if (isNaN(bet) || bet <= 0) return message.reply('❌ Invalid bet.');
        if (data.cash < bet) return message.reply('❌ Not enough cash.');
        const isWin = Math.random() < 0.52;
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
        if (isNaN(bet) || bet <= 0) return message.reply('❌ Invalid bet.');
        if (data.cash < bet) return message.reply('❌ Not enough cash.');
        let card1 = Math.floor(Math.random() * 13) + 1;
        let card2 = Math.floor(Math.random() * 13) + 1;
        if (Math.random() < 0.05) card2 = card1 > 7 ? Math.floor(Math.random() * (card1 - 1)) + 1 : Math.floor(Math.random() * (14 - card1)) + card1;
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
            if (i.user.id !== message.author.id) return;
            collector.stop();
            let won = (i.customId === 'higher' && card2 > card1) || (i.customId === 'lower' && card2 < card1) || (i.customId === 'same' && card2 === card1);
            let mul = i.customId === 'same' ? 8 : (i.customId === 'higher' ? 1.5 : 1.1);
            const resEmbed = new EmbedBuilder().setTitle('🎲 Higher or Lower - Result 🎲').setColor(won ? '#2ecc71' : '#e74c3c');
            if (won) {
                const winAmt = Math.floor(bet * mul);
                data.cash += (winAmt - bet);
                resEmbed.setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n\n\`1:\` ${card1}\n\`2:\` **${card2}**\n\n🎉 Won **${winAmt.toLocaleString()}** ${serverCurrency}`);
            } else {
                data.cash -= bet;
                resEmbed.setDescription(`**Betting Amount:** ${bet.toLocaleString()}\n\n\`1:\` ${card1}\n\`2:\` **${card2}**\n\n💥 Lost **${bet.toLocaleString()}** ${serverCurrency}`);
            }
            await i.update({ embeds: [resEmbed], components: [] });
        });
    }

    if (command === 'bj' || command === 'blackjack') {
        const data = getUserData(message.author.id);
        const bet = parseInt(args[0]);
        if (isNaN(bet) || bet <= 0) return message.reply('❌ Invalid bet.');
        if (data.cash < bet) return message.reply('❌ Not enough cash.');
        const draw = () => {
            const c = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'][Math.floor(Math.random() * 13)];
            return { display: c, value: ['J','Q','K'].includes(c) ? 10 : (c === 'A' ? 11 : parseInt(c)) };
        };
        let pHand = [draw(), draw()], dHand = [draw(), draw()];
        const val = (h) => {
            let s = h.reduce((a, b) => a + b.value, 0), aces = h.filter(c => c.display === 'A').length;
            while (s > 21 && aces > 0) { s -= 10; aces--; }
            return s;
        };
        if (Math.random() < 0.51) { while (val(pHand) < 15) pHand = [draw(), draw()]; }
        const makeEmbed = (end = false, txt = '') => new EmbedBuilder()
            .setAuthor({ name: `${message.author.username}'s Game` }).setTitle('🃏 Blackjack 🃏')
            .setDescription(`**Your Hand**\n${pHand.map(c => `\`${c.display}\``).join(', ')}\nValue: **${val(pHand)}**\n\n**Dealer**\n${end ? dHand.map(c => `\`${c.display}\``).join(', ') : `\`${dHand[0].display}\`, 🟥`}\nValue: **${end ? val(dHand) : dHand[0].value}**\n\n${txt}`)
            .setColor(end ? '#f1c40f' : '#10a3de');
        const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder().setCustomId('hit').setLabel('Hit').setStyle(ButtonStyle.Primary),
            new ButtonBuilder().setCustomId('stand').setLabel('Stand').setStyle(ButtonStyle.Success),
            new ButtonBuilder().setCustomId('double').setLabel('Double').setStyle(ButtonStyle.Danger)
        );
        const reply = await message.reply({ embeds: [makeEmbed()], components: [row] });
        const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 60000 });
        collector.on('collect', async (i) => {
            if (i.user.id !== message.author.id) return;
            if (i.customId === 'hit') {
                pHand.push(draw());
                if (val(pHand) > 21) {
                    collector.stop();
                    data.cash -= bet;
                    return i.update({ embeds: [makeEmbed(true, '💥 Bust! Lost.')], components: [] });
                }
                return i.update({ embeds: [makeEmbed()] });
            }
            if (i.customId === 'stand') {
                collector.stop();
                while (val(dHand) < 17) dHand.push(draw());
                let p = val(pHand), d = val(dHand), msg = '';

if (d > 21 || p > d) { data.cash += bet; msg = 🎉 Won ${bet.toLocaleString()} ${serverCurrency}!; }
else if (p < d) { data.cash -= bet; msg = ❌ Dealer won. Lost ${bet.toLocaleString()} ${serverCurrency}.; }
else msg = '👔 Push!';
return i.update({ embeds: [makeEmbed(true, msg)], components: [] });
}
});
}
if (command === 'mines') {
const data = getUserData(message.author.id);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet <= 0) return message.reply('❌ Invalid bet.');
if (data.cash < bet) return message.reply('❌ Not enough cash.');
let board = Array(9).fill('safe'), m1 = Math.floor(Math.random() * 9), m2 = Math.floor(Math.random() * 9);
while(m1 === m2) m2 = Math.floor(Math.random() * 9);
board[m1] = board[m2] = 'mine';
let profit = 0, rev = 0;
const getRows = (end = false) => {
const r = [];
for (let i = 0; i < 3; i++) {
const row = new ActionRowBuilder();
for (let j = 0; j < 3; j++) {
const idx = i * 3 + j;
const b = new ButtonBuilder().setCustomId(m_${idx}).setLabel('⬛').setStyle(ButtonStyle.Secondary);
if (end) b.setDisabled(true).setLabel(board[idx] === 'mine' ? '💥' : '💎');
row.addComponents(b);
}
r.push(row);
}
r.push(new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('co').setLabel('Cashout').setStyle(ButtonStyle.Success).setDisabled(rev === 0 || end)));
return r;
};
const embed = new EmbedBuilder().setTitle('💣 Mines 💣').setDescription(**Betting:** ${bet.toLocaleString()} ${serverCurrency}).setFields({ name: Profit: ${profit} ${serverCurrency}, value: '\u200B' }).setColor('#e67e22');
const reply = await message.reply({ embeds: [embed], components: getGridRows ? getGridRows() : getRows() });
const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 60000 });
collector.on('collect', async (i) => {
if (i.user.id !== message.author.id) return;
if (i.customId === 'co') {
collector.stop();
data.cash += profit;
return i.update({ embeds: [new EmbedBuilder().setTitle('💰 Cashout! 💰').setDescription(Won **${profit.toLocaleString()}** ${serverCurrency}).setColor('#2ecc71')], components: getRows(true) });
}
const idx = parseInt(i.customId.split('_')[1]);
if (board[idx] === 'mine') {
collector.stop();
data.cash -= bet;
return i.update({ embeds: [new EmbedBuilder().setTitle('💥 BOOM! 💥').setDescription(Lost **${bet.toLocaleString()}** ${serverCurrency}).setColor('#e74c3c')], components: getRows(true) });
} else {
rev++;
profit += Math.floor(bet * 0.35);
const next = new EmbedBuilder().setTitle('💣 Mines 💣').setDescription(**Betting:** ${bet.toLocaleString()} ${serverCurrency}).setFields({ name: Profit: ${profit} ${serverCurrency}, value: '💎 Safe!' }).setColor('#e67e22');
return i.update({ embeds: [next], components: getRows() });
}
});
}
if (command === 'poker' || command === 'texas') {
const data = getUserData(message.author.id);
const bet = parseInt(args[0]);
if (isNaN(bet) || bet <= 0) return message.reply('❌ Invalid bet.');
if (data.cash < bet) return message.reply('❌ Not enough cash.');
const s = ['♠️', '♥️', '♦️', '♣️'], v = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
const d = () => ({ val: v[Math.floor(Math.random()*13)], suit: s[Math.floor(Math.random()*4)] });
let pHand = [d(), d()], bHand = [d(), d()], comm = [d(), d(), d(), d(), d()];
const embed = new EmbedBuilder().setTitle('🃏 Texas Hold'em 🃏')
.setDescription(**Your Hand:** \[${pHand[0].val}${pHand[0].suit}]` `[${pHand[1].val}${pHand[1].suit}]`
Bot Hand: `[❓]` `[❓]`
Community: ${comm.map(c => \[${c.val}${c.suit}]`).join(' ')}).setColor('#1abc9c');
const row = new ActionRowBuilder().addComponents(
new ButtonBuilder().setCustomId('call').setLabel('Call').setStyle(ButtonStyle.Success),
new ButtonBuilder().setCustomId('fold').setLabel('Fold').setStyle(ButtonStyle.Danger)
);
const reply = await message.reply({ embeds: [embed], components: [row] });
const collector = reply.createMessageComponentCollector({ componentType: ComponentType.Button, time: 40000 });
collector.on('collect', async (i) => {
if (i.user.id !== message.author.id) return;
collector.stop();
if (i.customId === 'fold') { data.cash -= Math.floor(bet / 2); return i.update({ content: 🏳️ Folded. Lost: ${Math.floor(bet / 2)} ${serverCurrency}, embeds: [], components: [] }); }
const win = Math.random() < 0.53;
const res = new EmbedBuilder();
if (win) { data.cash += bet; res.setTitle('🎉 You Won! 🎉').setDescription(Bot held: \[${bHand[0].val}${bHand[0].suit}]` `[${bHand[1].val}${bHand[1].suit}]`\nWon ${bet.toLocaleString()} ${serverCurrency}).setColor('#2ecc71'); } else { data.cash -= bet; res.setTitle('❌ Bot Won! ❌').setDescription(Bot held: `[${bHand[0].val}${bHand[0].suit}]` `[${bHand[1].val}${bHand[1].suit}]`\nLost ${bet.toLocaleString()} ${serverCurrency}`).setColor('#e74c3c'); }
await i.update({ embeds: [res], components: [] });
});
}
});
client.login(process.env.DISCORD_TOKEN);
 האם המשחקים החדשים מגיבים בצורה חלק