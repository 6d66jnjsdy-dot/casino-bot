require('dotenv').config();
const fs = require('fs');
const path = require('path');
const { Client, GatewayIntentBits, Partials } = require('discord.js');

const { loadEconomy, saveEconomy, loadConfig, saveConfig } = require('./src/data');
const { COLORS, baseEmbed } = require('./src/embeds');
const { isAllowedChannel } = require('./src/permissions');

const PREFIX = process.env.PREFIX || '$';

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ],
  partials: [Partials.Channel]
});

// ---- Load all command modules ----
const commands = new Map();
const RESTRICTED_TO_GAME_ROOM = new Set([
  'gm', 'mines', 'cf', 'hl', 'ht', 'slots', 'crash', 'bj',
  'work', 'crime', 'rob', 'pay'
]);

function loadCommandsFrom(dir) {
  const full = path.join(__dirname, dir);
  if (!fs.existsSync(full)) return;
  for (const file of fs.readdirSync(full)) {
    if (!file.endsWith('.js')) continue;
    const cmd = require(path.join(full, file));
    if (!cmd || !cmd.name || typeof cmd.execute !== 'function') continue;
    commands.set(cmd.name, cmd);
    for (const alias of cmd.aliases || []) commands.set(alias, cmd);
  }
}

loadCommandsFrom('src/commands/economy');
loadCommandsFrom('src/commands/games');
loadCommandsFrom('src/commands/admin');

// ---- Shared context passed to every command ----
let economy = loadEconomy();
let config = loadConfig();

function makeContext() {
  return {
    economy,
    config,
    saveEconomy,
    saveConfig,
    COLORS,
    embed: (opts) => baseEmbed(opts)
  };
}

client.once('ready', () => {
  console.log(`Logged in as ${client.user.tag}. Prefix: ${PREFIX}`);
});

client.on('messageCreate', async (message) => {
  try {
    if (message.author.bot) return;
    if (!message.content.startsWith(PREFIX)) return;
    if (!message.guild) return; // casino only works in servers

    const withoutPrefix = message.content.slice(PREFIX.length).trim();
    if (!withoutPrefix) return;
    const [rawName, ...args] = withoutPrefix.split(/\s+/);
    const name = rawName.toLowerCase();

    const command = commands.get(name);
    if (!command) return;

    if (RESTRICTED_TO_GAME_ROOM.has(command.name) && !isAllowedChannel(message.channel.id, config)) {
      const allowed = config.gameRooms.map((id) => `<#${id}>`).join(', ');
      return message.reply({
        embeds: [baseEmbed({ color: COLORS.loss, description: `Casino commands can only be used in: ${allowed}` })]
      });
    }

    await command.execute(message, args, makeContext());
  } catch (err) {
    console.error(`Error running command from message "${message.content}":`, err);
    message.reply('⚠️ Something went wrong running that command.').catch(() => {});
  }
});

const token = process.env.DISCORD_TOKEN;
if (!token) {
  console.error('Missing DISCORD_TOKEN in your .env file. Copy .env.example to .env and fill it in.');
  process.exit(1);
}

client.login(token);
