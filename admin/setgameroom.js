const { isServerAdmin } = require('../../permissions');

module.exports = {
  name: 'setgameroom',
  aliases: [],
  description:
    'Server Administrator only. Restricts casino commands to specific channel(s). ' +
    'Usage: $setgameroom (toggles current channel) or $setgameroom #channel1 #channel2 ...',
  async execute(message, args, ctx) {
    if (!isServerAdmin(message.member)) {
      return message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.loss, description: 'Only server Administrators can set the game room(s).' })] });
    }

    const mentionedChannels = [...message.mentions.channels.values()];
    const targets = mentionedChannels.length > 0 ? mentionedChannels : [message.channel];

    const added = [];
    const removed = [];
    for (const channel of targets) {
      const idx = ctx.config.gameRooms.indexOf(channel.id);
      if (idx === -1) {
        ctx.config.gameRooms.push(channel.id);
        added.push(channel);
      } else {
        ctx.config.gameRooms.splice(idx, 1);
        removed.push(channel);
      }
    }
    ctx.saveConfig(ctx.config);

    const lines = [];
    if (added.length) lines.push(`✅ Added: ${added.map((c) => `${c}`).join(', ')}`);
    if (removed.length) lines.push(`❌ Removed: ${removed.map((c) => `${c}`).join(', ')}`);
    if (ctx.config.gameRooms.length === 0) lines.push('\nNo game rooms configured — casino commands now work in every channel.');
    else lines.push(`\nCurrent game rooms: ${ctx.config.gameRooms.map((id) => `<#${id}>`).join(', ')}`);

    await message.reply({ embeds: [ctx.embed({ color: ctx.COLORS.win, description: lines.join('\n') })] });
  }
};
