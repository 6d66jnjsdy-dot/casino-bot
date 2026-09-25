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
- `$deposit <amount|all>` / `$withdraw <amount|all>`
- `$lb` or `$top` — richest players (cash + bank)
- `$top cash` — most cash on hand (useful for `$rob` targets)

### Admin
- `$addmoney cash/bank @user <amount>` — add funds (Admin / casino role only)
- `$currency <emoji>` — change the currency shown everywhere (Admin / casino role only)
- `$casinorole @role` — grant a role admin access (Administrator only)

### Games (minimum bet: 175)
- `$bj <amount>` — Blackjack. ~20% instant natural blackjack (pays 2.5x), otherwise
  the deck is lightly weighted so the player wins roughly ~51% of hands.
- `$cf <amount>` — Cockfight. Your chicken's strength rolls 55–82%; higher wins, pays 2x.
- `$hl <amount>` — Higher or Lower. Higher/Lower multipliers are calculated from the
  real odds with a small edge in your favor; Same always pays 25x.
- `$ht <amount>` — Coinflip, 50/50, pays 2x.
- `$mines <amount>` — 3x3 grid, 1 bomb. Multipliers per safe tile: 1.1x, 1.2x, 1.4x,
  1.6x, 2x, 2.6x, 3.6x, 8x.
- `$mt <amount>` — Money Tower. 5 levels, 3 tiles each (1 bomb). Level multipliers:
  1.5x, 2.1x, 2.3x, 3.6x, 7.6x.
- `$gm <amount>` — Goldmine. 4x5 grid with 5 bombs. Tiles: 🪨 rock x1.1, 🪙 coin x2,
  💎 diamond x3.5, 🏮 lantern x15 (rare). One 🗺️ map tile auto-reveals 3 more
  guaranteed-safe tiles for free. Multipliers compound as you reveal more tiles.

## Notes

- Balances are saved to `data.json` next to `bot.js` so they survive restarts.
  On some hosts (depending on plan) the filesystem resets on redeploy — for permanent
  production use you'd eventually want a real database, but this is solid for a
  private/small server.
- Discord doesn't let bots draw custom card/tile artwork without an image-generation
  step, so hands and grids are shown as text/emoji rather than the rendered card
  graphics you see in some other bots.
