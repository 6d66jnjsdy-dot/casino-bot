const { PermissionsBitField } = require('discord.js');

/**
 * True if the member has the real Discord "Administrator" permission.
 * Used to gate the setup commands that configure the bot itself
 * ($casino-role, $setgameroom) — real server admins only, no hardcoded IDs.
 */
function isServerAdmin(member) {
  if (!member) return false;
  return member.permissions.has(PermissionsBitField.Flags.Administrator);
}

/**
 * True if the member is a server admin OR holds the configured
 * "casino staff" role. Used to gate $addmoney / $removemoney / $addmoney-role.
 */
function isCasinoStaff(member, config) {
  if (!member) return false;
  if (isServerAdmin(member)) return true;
  if (!config.casinoRoleId) return false;
  return member.roles.cache.has(config.casinoRoleId);
}

/**
 * True if a command may run in this channel. If no game rooms have been
 * configured yet, games/economy commands work everywhere (so the bot is
 * usable out of the box). Once $setgameroom is used, restricted commands
 * only work in the configured channel(s).
 */
function isAllowedChannel(channelId, config) {
  if (!config.gameRooms || config.gameRooms.length === 0) return true;
  return config.gameRooms.includes(channelId);
}

module.exports = { isServerAdmin, isCasinoStaff, isAllowedChannel };
