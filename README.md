# Casino Bot

A Discord bot with a virtual-currency economy and 8 casino games: Gold Mines,
Mines, Chicken Fight, High-Low, Higher-Tail, Slots, Crash, and Blackjack.

Data is stored in plain JSON files under `data/` and is only ever added to —
restarting, redeploying, or updating the bot's code never resets balances.

## Setup

1. **Install Node.js 18+** if you don't have it.
2. In this folder, install dependencies:
   ```
   npm install
   ```
3. Create a Discord application + bot at https://discord.com/developers/applications,
   turn on the **Message Content Intent** and **Server Members Intent** under
   Bot settings, and copy the bot token.
4. Copy `.env.example` to `.env` and paste your token in:
   ```
   cp .env.example .env
   ```
5. Invite the bot to your server with these OAuth2 scopes/permissions:
   `bot`, `applications.commands` scope not required (message commands only);
   permissions: Send Messages, Embed Links, Read Message History, Use External
   Emojis.
6. Start the bot:
   ```
   npm start
   ```

## Commands

Default prefix is `$` (change it with `PREFIX` in `.env`).

Every bet amount accepts a number (e.g. `500`, `1,000`), `all`, or `half`.

### Games
| Command | Description |
|---|---|
| `$gm <amount>` | Gold Mines — 5×4 grid, 12 bombs, 8 safe tiles (2 coins ×2, 2 diamonds ×2.5, 3 rocks ×1.1, 1 rare jar ×27.5 / moneybag ×5). Cash out any time after your first safe dig. |
| `$mines <amount>` | Mines — 3×3 grid, 1 bomb. Multiplier climbs 1.1 → 1.4 → 1.7 → 2 → 2.7 → 4 → 6.5 → 8.7 as you clear diamonds. |
| `$cf <amount>` | Chicken Fight — win chance starts at 50%, +1% per consecutive win, capped at 85%. Pays 1:1. |
| `$hl <amount>` | Higher or Lower — rolls 1–10. Higher ×2.1, Lower ×1.9, Same ×15 (rare). |
| `$ht <amount>` | Higher/Tail coin flip. Pays 2× (profit = bet). |
| `$slots <amount>` | 3-reel slots with a short spin animation. Triples pay 2×–10× depending on symbol; any pair pays 1.2×. |
| `$crash <amount>` | Multiplier rises live; hit **Cash Out** before it crashes. |
| `$bj <amount>` | Blackjack — dealer stands on 17+, natural blackjack pays 3:2, regular win pays 1:1, push returns your bet, basic Split supported. |

### Economy
| Command | Description |
|---|---|
| `$bal` | Shows your cash (Money Out), Bank, and Total, with a button to view the leaderboard. |
| `$top` / `$lb` | Leaderboard with Bank / Total / Cash tabs and pagination. |
| `$work` | Guaranteed payout, short cooldown. |
| `$crime` | Guaranteed (higher) payout, short cooldown. |
| `$rob @user` | Steal 10–30% of a player's cash. **15% chance to get caught and get nothing.** |
| `$pay @user <amount|all|half>` | Send cash to another player. |

### Admin / setup
| Command | Who can use it | What it does |
|---|---|---|
| `$casino-role @role` | Server **Administrators** only | Sets which role counts as "Casino Staff" for the money commands below. |
| `$addmoney <bank\|cash> @user <amount>` | Casino Staff or Administrators | Grants money to a player. |
| `$removemoney <bank\|cash> @user <amount>` | Casino Staff or Administrators | Removes money from a player. |
| `$addmoney-role <bank\|cash> @role <amount>` | Casino Staff or Administrators | Grants money to every member holding a role. |
| `$setgameroom` (or `$setgameroom #channel ...`) | Server **Administrators** only | Toggles which channel(s) the games/economy commands work in. Run with no arguments in a channel to add/remove *that* channel. With no game room configured, commands work everywhere. |

There is no hardcoded "owner" user ID anywhere in the code — every admin
action is gated by real Discord permissions (the **Administrator** permission,
or the role you choose with `$casino-role`), so server owners stay in control
of who can grant money or reconfigure the bot, the same way they control any
other permission on their server.

## What was intentionally left out

Two things from the original request aren't in here, on purpose:

- **A "predict" command that reveals hidden game outcomes (mine/bomb
  locations) in advance.** Regardless of who has access to it, a command like
  that lets one player secretly win against everyone else who's betting in
  the same economy — that's a cheating tool, not a game feature.
- **Admin powers hardcoded to one personal Discord user ID.** Instead,
  `$casino-role` and `$setgameroom` are gated by the real Discord
  **Administrator** permission, so the server's actual owners/admins are
  always the ones in control — not a name baked into the code that they
  can't see or change.

Everything else — every game, its exact odds/multipliers, `$crime`/`$work`
always succeeding, `$rob`'s 15% catch chance, `all`/`half` amounts, the
admin money commands, and the game-room lock — is implemented as described.

## Project structure

```
casino-bot/
├── index.js                     # bot entry point, command loader/router
├── data/
│   ├── economy.json              # player balances (persists across restarts)
│   └── config.json               # casino role + game room settings
└── src/
    ├── data.js                   # JSON read/write helpers
    ├── embeds.js                 # shared embed styling
    ├── permissions.js             # role/admin permission checks
    ├── utils.js                  # bet parsing, formatting, RNG helpers
    └── commands/
        ├── economy/               # bal, top, pay, work, crime, rob
        ├── games/                 # gm, mines, cf, hl, ht, slots, crash, bj
        └── admin/                 # addmoney, removemoney, addmoney-role,
                                    # casino-role, setgameroom
```

## Customizing odds

Every multiplier/probability lives near the top of its game file as a plain
constant (e.g. `MULT` in `hl.js`, `MULTIPLIERS` in `mines.js`, the tile table
in `gm.js`), so you can tune the house edge without touching any game logic.