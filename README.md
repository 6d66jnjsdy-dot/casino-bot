# Casino Bot

## Setup

1. Put `bot.js`, `package.json` and `data.json` (auto-created) in the same folder.
2. `npm install`
3. Set the environment variable `DISCORD_TOKEN` (in Render: Environment tab; locally: `.env` or export it).
4. `node bot.js` (or `npm start`)

On Render: Build Command `npm install`, Start Command `npm start` or `node bot.js`.

Bot needs these permissions/intents enabled in the Discord Developer Portal:
`Server Members Intent` and `Message Content Intent` (Bot tab → Privileged Gateway Intents).

## Permissions system

- Server **Administrators** always have full access to admin commands.
- Run `$casinorole @role` (Administrator only) to grant any role the same admin access
  (add money, change currency, etc). `$casinorole remove` clears it.

## Commands

### Economy
- `$work` — earn 4,000–12,000, once every 4 minutes
- `$crime` — 75% chance to earn 6,000–15,000, else pay a fine, once every 4 minutes
- `$rob @user` — 45% chance to steal 10–30% of their cash, else pay a fine, once every 8 minutes
- `$bal [@user]` — shows cash (outside) / bank (inside) / total
- `$deposit`/`$dep` and `$withdraw`/`$with`/`$wd` `<amount|all>` — move money to/from your bank
- `$pay @user <amount|all>` — send cash directly to another player
- `$lb` or `$top` — richest players (cash + bank)
- `$top cash` — most cash on hand (useful for `$rob` targets)
- `$info` — short rules/payouts for every game in one place

### Admin
- `$addmoney cash/bank @user <amount>` — add funds (Admin / casino role only)
- `$currency <emoji>` — change the currency shown everywhere (Admin / casino role only)
- `$casinorole @role` — grant a role admin access (Administrator only)

### Games (minimum bet: 175 — every game also accepts `all` instead of an amount)
- `$bj <amount>` — Blackjack. ~20% instant natural blackjack (pays 2.5x), otherwise
  the deck is lightly weighted so the player wins roughly ~51% of hands. Cards render
  as real Unicode playing-card glyphs (🂡, 🂮, 🂠 for the hidden card, etc).
- `$cf <amount>` — Cockfight. Your win chance is a personal streak: it starts at 55%,
  climbs +1% every time you win (capped at 82%), and resets to 55% the moment you lose.
  Win pays 2x.
- `$hl <amount>` — Higher or Lower. Higher/Lower multipliers are calculated from the
  real odds with a small edge in your favor; Same always pays 25x.
- `$ht <amount>` — Coinflip, 50/50, pays 2x.
- `$mines <amount>` — 3x3 grid, 1 bomb. Multipliers per safe tile: 1.1x, 1.4x, 1.8x,
  2.1x, 2.8x, 4.2x, 6.2x, 8.9x.
- `$mt <amount>` — Money Tower. 5 levels, 3 tiles each (1 bomb). Level multipliers:
  1.5x, 2.1x, 2.3x, 3.6x, 7.6x.
- `$gm <amount>` — Goldmine. 24 tiles, 12 bombs. Tiles: 🪨 rock x1.2 (x4), 🪙 coin x2.5
  (x3), 💎 diamond x3.5 (x2), 💰 moneybag x6.5 (x1), 🏮 lantern x20 (x1). One 🗺️ map
  tile auto-reveals 3 more guaranteed-safe tiles for free. Multipliers compound.
- `$slots <amount>` — 3-reel slot machine.
- `$roulette <amount> <red/black/green/0-36>` — colors pay 2x (green 14x), an exact
  number pays 30x.
- `$dice <amount> <over/under/seven>` — two dice; over/under pays 2x, exact seven pays 5x.
- `$wheel <amount>` — spin for 0x–10x.
- `$crash <amount>` — a rising multiplier; cash out before it crashes.

## Notes

- Balances are saved to `data.json` next to `bot.js` so they survive restarts.
  On some hosts (depending on plan) the filesystem resets on redeploy — for permanent
  production use you'd eventually want a real database, but this is solid for a
  private/small server.
- Discord doesn't let bots draw custom card/tile artwork without an image-generation
  step, so hands and grids are shown as text/emoji rather than the rendered card
  graphics you see in some other bots.
