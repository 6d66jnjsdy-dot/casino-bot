const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const fs = require('fs');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

const DB_FILE = './database.json';

// Load or initialize database
let db = {};
if (fs.existsSync(DB_FILE)) {
    try {
        db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
    } catch (e) {
        db = {};
    }
}

function saveDB() {
    fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
}

function getUserBalance(userId) {
    if (!db[userId]) {
        db[userId] = { balance: 1000 }; // Starting balance
        saveDB();
    }
    return db[userId].balance;
}

function updateUserBalance(userId, amount) {
    getUserBalance(userId);
    db[userId].balance += amount;
    saveDB();
}

client.once('ready', () => {
    console.log(`Logged in as ${client.user.tag}!`);
});

client.on('messageCreate', async message => {
    if (message.author.bot) return;

    const prefix = '!';
    if (!message.content.startsWith(prefix)) return;

    const args = message.content.slice(prefix.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();

    if (command === 'balance' || command === 'bal') {
        const balance = getUserBalance(message.author.id);
        return message.reply(`יש לך ${balance} מטבעות בחשבון! 🪙`);
    }

    if (command === 'daily') {
        const userId = message.author.id;
        getUserBalance(userId);
        
        const now = Date.now();
        const cooldown = 24 * 60 * 60 * 1000; // 24 hours
        
        if (db[userId].lastDaily && now - db[userId].lastDaily < cooldown) {
            const timeLeft = Math.ceil((cooldown - (now - db[userId].lastDaily)) / (1000 * 60 * 60));
            return message.reply(`כבר אספת את המתנה היומית שלך! תוכל לאסוף שוב בעוד כ-${timeLeft} שעות.`);
        }

        db[userId].lastDaily = now;
        updateUserBalance(userId, 500);
        return message.reply(`אספת בהצלחה את הבונוס היומי שלך: 500 מטבעות! 🎁`);
    }

    if (command === 'help') {
        const embed = new EmbedBuilder()
            .setTitle('🎰 פקודות בוט הקזינו')
            .setDescription('הנה רשימת הפקודות הזמינות בבוט:')
            .addFields(
                { name: '!bal / !balance', value: 'בדיקת יתרת המטבעות שלך', inline: false },
                { name: '!daily', value: 'קבלת בונוס מטבעות יומי', inline: false },
                { name: '!mines <הימור>', value: 'משחק המוקשים הקלאסי', inline: false },
                { name: '!goldmine <הימור>', value: 'משחק מכרה הזהב', inline: false }
            )
            .setColor('Gold');
        return message.reply({ embeds: [embed] });
    }

    if (command === 'mines') {
        const bet = parseInt(args[0]);
        const userId = message.author.id;
        const balance = getUserBalance(userId);

        if (isNaN(bet) || bet <= 0) {
            return message.reply('אנא הכנס סכום הימור תקין. דוגמה: `!mines 100`');
        }
        if (bet > balance) {
            return message.reply('אין לך מספיק מטבעות בשביל ההימור הזה!');
        }

        updateUserBalance(userId, -bet);
        return message.reply(`התחלת משחק Mines על סך ${bet} מטבעות! (המערכת מוכנה לפעולה)`);
    }
});

// Login using Render environment variable
client.login(process.env.DISCORD_TOKEN);
