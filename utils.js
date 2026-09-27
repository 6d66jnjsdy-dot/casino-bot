const MONEY_EMOJI = '💸';

function fmt(n) {
  return Math.round(n).toLocaleString('en-US');
}

function money(n) {
  return `${fmt(n)} ${MONEY_EMOJI}`;
}

/**
 * Parses a bet amount argument.
 * Accepts: "all", "half", or a plain number (commas allowed, e.g. "1,000").
 * Returns an integer amount, or null if invalid.
 */
function parseAmount(arg, balance) {
  if (arg === undefined || arg === null) return null;
  const clean = String(arg).trim().toLowerCase();

  if (clean === 'all') return Math.floor(balance);
  if (clean === 'half') return Math.floor(balance / 2);

  const numeric = Number(clean.replace(/,/g, ''));
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return Math.floor(numeric);
}

/**
 * Resolves a target user for pay/rob/admin commands: mention, plain ID, or
 * (for admin commands) "all" handled separately by the caller.
 */
function resolveUserId(message, arg) {
  const mentioned = message.mentions.users.first();
  if (mentioned) return mentioned.id;
  if (arg && /^\d{15,25}$/.test(arg)) return arg;
  return null;
}

function randInt(min, max) {
  // inclusive on both ends
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function chance(pct) {
  return Math.random() * 100 < pct;
}

function pickWeighted(entries) {
  // entries: [{ value, weight }]
  const total = entries.reduce((s, e) => s + e.weight, 0);
  let roll = Math.random() * total;
  for (const e of entries) {
    if (roll < e.weight) return e.value;
    roll -= e.weight;
  }
  return entries[entries.length - 1].value;
}

module.exports = { MONEY_EMOJI, fmt, money, parseAmount, resolveUserId, randInt, chance, pickWeighted };
