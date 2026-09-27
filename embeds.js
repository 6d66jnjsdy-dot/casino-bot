const { EmbedBuilder } = require('discord.js');

const COLORS = {
  win: 0x57f287, // green
  loss: 0xed4245, // red
  push: 0xfee75c, // yellow / neutral
  info: 0x5865f2 // blurple
};

// Wraps a value in an inline code block so it renders as a little
// "boxed" chip of text, matching the reference screenshots.
function box(value) {
  return `\`${value}\``;
}

function baseEmbed({ title, color = COLORS.info, description = '' }) {
  const embed = new EmbedBuilder().setColor(color);
  if (title) embed.setTitle(title);
  if (description) embed.setDescription(description);
  return embed;
}

function playerLine(name, avatarURL) {
  return { name, avatarURL };
}

module.exports = { COLORS, box, baseEmbed, playerLine, EmbedBuilder };
