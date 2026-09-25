🎰 Casino Bot — README

1. Install

npm install discord.js express

2. Environment variable

Create an environment variable named exactly:

DISCORD_TOKEN

Put your Discord bot token there. Do not put the token directly into index.js or upload it to GitHub.

3. Run

node index.js

For Render/Railway, the bot starts the small HTTP server automatically and uses the platform PORT when provided.

4. First Discord setup

Use these commands in this order:

$casinorole @CasinoAdmin
$roomgame #casino
$log-channel #casino-logs

• $casinorole controls casino-admin commands.
• $roomgame restricts games to the selected channel(s). Use $roomgame clear to remove the restriction.
• $log-channel sends detailed casino logs to a channel. Use $log-channel off to disable.

5. Prediction feed

For a casino admin:

$predict

This enables private prediction DMs for that admin. The feed can include hidden Mines/Goldmine layouts and Roulette/Slots results before the public result is shown.

Disable it with:

$predict off

6. Money commands

$bal
$deposit 5000
$deposit half
$deposit all
$withdraw 5000
$withdraw half
$withdraw all
$pay @user 5000
$pay @user half
$pay @user all

Every casino game accepts:

<exact amount>
half
all

Minimum bet: 175.

7. Admin money commands

$addmoney cash @user 100000
$addmoney bank @user 100000
$remove-money cash @user 100000
$remove-money bank @user 100000
$addmoney-role cash @role 100000
$addmoney-role bank @role 100000
$reset-economy

$reset-economy sets stored cash and bank balances to zero.

8. Games

$bj 1000
$cf half
$hl all
$ht 5000
$mines 1000
$gm half
$slots all
$roulette 1000 red
$roulette 1000 17
$wheel 1000
$crash half

Dice and Money Tower were removed.

9. Daily Summer wheel

$summer

One spin per 24 hours. Prizes:

• 1,750,000 — 45%
• 25,000,000 — 30%
• 65,000,000 — 15%
• 100,000,000 JACKPOT — 5%

10. Visual style

The embeds/buttons use the same general texture as the reference screenshots:

• dark casino panel
• purple accent
• blue action buttons
• green Cashout/win buttons
• red bomb/loss buttons
• large spaced Blackjack layout

Discord itself does not allow a bot embed to set a custom full-background texture like an image-based game UI, so the styling is matched using Discord’s supported embeds and buttons.

11. Important

Keep data.json persistent on your hosting platform if you want balances/configuration to survive restarts. If your host has ephemeral storage, use persistent storage or a database.