const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ComponentType } = require('discord.js');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

const PREFIX = '\$';
let balances = {}; 
let casinoRole = null; 
let serverCurrency = '💸'; 

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

    if (command === 'role-casino') {
        if (!message.member.permissions.has('Administrator')) return message.reply('No admin perms.');
        const role = message.mentions.roles.first();
        if (!role) return message.reply('Mention a role.');
        casinoRole = role.id;
        return message.reply(`Role set to: ${role.name}`);
    }

    if (command === 'bal' || command === 'balance') {
        const targetUser = message.mentions.users.first() || message.author;
        const data = getUserData(targetUser.id);
        const total = data.cash + data.bank;
        const embed = new EmbedBuilder()
            .setAuthor({ name: targetUser.username, iconURL: targetUser.displayAvatarURL() })
            .setDescription(`• **Money Out:** ${data.cash} ${serverCurrency}\n• **Bank:** ${data.bank} ${serverCurrency}\n• **Total:** ${total} ${serverCurrency}`)
            .setColor('#10a3de');
        return message.reply({ embeds: [embed] });
    }
});

client.login(process.env.DISCORD_TOKEN);
