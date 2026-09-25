/* ============================================================
   CASINO BOT — FULL BUILD (UPDATED)
   discord.js v14
   ============================================================ */

const fs = require("fs");
const path = require("path");
const express = require("express");
const {
  Client,
  GatewayIntentBits,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  PermissionFlagsBits
} = require("discord.js");

/* ========================= KEEP ALIVE ========================= */
const app = express();
const PORT = process.env.PORT || 10000;
app.get("/", (_, res) => res.send("Casino Bot is Online 24/7!"));
app.listen(PORT, "0.0.0.0", () => console.log(`Web server running on port ${PORT}`));

/* ============================ BOT ============================= */
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

const PREFIX = "$";
const MIN_BET = 175;
const COLOR_WIN = 0x57f287;
const COLOR_LOSE = 0xed4245;
const COLOR_INFO = 0x5865f2;
const COLOR_NEUTRAL = 0x2b2d31;

/* ============================ DATA ============================ */
const DATA_FILE = path.join(__dirname, "data.json");
let db = {
  currency: "💸",
  casinoRoleId: null,
  gameChannels: [],
  logChannelId: null,
  users: {},
  summer: {}
};

function loadData() {
  try {
    if (!fs.existsSync(DATA_FILE)) return;
    const parsed = JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
    db = Object.assign(db, parsed);
    db.gameChannels = Array.isArray(db.gameChannels) ? db.gameChannels : [];
    db.summer = db.summer || {};
    db.users = db.users || {};
  } catch (e) {
    console.error("Failed to load data.json:", e);
  }
}
let saveQueued = false;
function saveData() {
  if (saveQueued) return;
  saveQueued = true;
  setImmediate(() => {
    saveQueued = false;
    try { fs.writeFileSync(DATA_FILE, JSON.stringify(db, null, 2)); }
    catch (e) { console.error("Failed to save data.json:", e); }
  });
}
loadData();

/* =========================== HELPERS ========================== */
function getUser(id) {
  if (!db.users[id]) db.users[id] = { cash: 0, bank: 0, cooldowns: {}, cfStreak: 55 };
  db.users[id].cooldowns ||= {};
  if (db.users[id].cfStreak == null) db.users[id].cfStreak = 55;
  return db.users[id];
}
function money(n) { return Math.floor(Number(n) || 0).toLocaleString("en-US"); }
function random(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function randomFloat(min, max) { return Math.random() * (max - min) + min; }
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = random(0, i); [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function weightedPick(entries) {
  const total = entries.reduce((s, x) => s + x.weight, 0);
  let r = Math.random() * total;
  for (const e of entries) { if (r < e.weight) return e; r -= e.weight; }
  return entries[entries.length - 1];
}
function embed(description, color = COLOR_NEUTRAL, title = null) {
  const e = new EmbedBuilder().setDescription(description).setColor(color);
  if (title) e.setTitle(title);
  return e;
}
function disabledRow(row) {
  return new ActionRowBuilder().addComponents(
    row.components.map(c => ButtonBuilder.from(c).setDisabled(true))
  );
}
function formatDuration(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(s / 60);
  return m ? `${m}m${s % 60}s` : `${s}s`;
}
function onCooldown(user, key, ms) {
  const left = (user.cooldowns[key] || 0) + ms - Date.now();
  return left > 0 ? left : 0;
}
function hasCasinoAccess(member) {
  if (!member) return false;
  if (member.permissions.has(PermissionFlagsBits.Administrator)) return true;
  return !!(db.casinoRoleId && member.roles.cache.has(db.casinoRoleId));
}
function isGameChannel(message) {
  if (!db.gameChannels.length) return true;
  return db.gameChannels.includes(message.channel.id);
}
function gameRoomCheck(message) {
  if (isGameChannel(message)) return true;
  message.reply({ embeds: [embed(`❌ Games are only allowed in the configured casino rooms.\nUse $roomgame to configure them.`, COLOR_LOSE)] }).catch(() => {});
  return false;
}
function parseBet(user, raw) {
  const value = String(raw || "").toLowerCase();
  let bet;
  if (value === "all") bet = user.cash;
  else if (value === "half") bet = Math.floor(user.cash / 2);
  else bet = Number(value);
  if (!Number.isFinite(bet) || bet < MIN_BET) return { error: `❌ Minimum bet is **${money(MIN_BET)}**${db.currency}. You can use an exact amount, \`half\`, or \`all\`.` };
  bet = Math.floor(bet);
  if (bet > user.cash) return { error: `❌ You only have **${money(user.cash)}**${db.currency} in cash.` };
  return { bet };
}
function validBet(message, args) {
  const parsed = parseBet(getUser(message.author.id), args[0]);
  if (parsed.error) {
    message.reply({ embeds: [embed(parsed.error, COLOR_LOSE)] }).catch(() => {});
    return null;
  }
  return parsed.bet;
}
function amountHelp() { return "`<amount>` accepts any amount, `half`, or `all`."; }

/* ============================= LOGS =========================== */
async function logEvent(guild, text, color = COLOR_INFO) {
  if (!db.logChannelId) return;
  try {
    const ch = guild.channels.cache.get(db.logChannelId) || await guild.channels.fetch(db.logChannelId);
    if (!ch || !ch.isTextBased()) return;
    await ch.send({ embeds: [embed(text, color, "🧾 Casino Log")] });
  } catch (e) { console.error("Log error:", e.message); }
}

/* =========================== READY ============================= */
client.once("ready", () => console.log(`Logged in as ${client.user.tag}`));

client.on("interactionCreate", async interaction => {
  if (!interaction.isButton() || !interaction.guild) return;
  await logEvent(
    interaction.guild,
    `Button **${interaction.customId}** clicked by **${interaction.user.tag}** in <#${interaction.channelId}>.`,
    COLOR_INFO
  );
});

/* ========================= COMMANDS =========================== */
client.on("messageCreate", async message => {
  if (message.author.bot || !message.guild || !message.content.startsWith(PREFIX)) return;
  const parts = message.content.slice(PREFIX.length).trim().split(/\s+/);
  const command = (parts.shift() || "").toLowerCase();
  const args = parts;
  const user = getUser(message.author.id);

  try {
    await logEvent(message.guild, `Command **${message.content}** used in <#${message.channel.id}>.`, COLOR_INFO);

    /* HELP */
    if (command === "help") {
      return message.reply({ embeds: [embed([
        "**💰 Economy**",
        "`$work` · `$crime` · `$rob @user` · `$bal`",
        "`$deposit/$dep <amount|half|all>` · `$withdraw/$with <amount|half|all>`",
        "`$pay @user <amount|half|all>` · `$lb/$top`",
        "",
        `**🎰 Games — minimum ${money(MIN_BET)}${db.currency}**`,
        "`$bj` · `$cf` · `$hl` · `$ht` · `$mines` · `$gm` · `$slots` · `$roulette` · `$wheel` · `$crash` · `$texas`",
        "Every game accepts **any amount**, `half`, or `all`.",
        "",
        "**🛠️ Admin**",
        "`$addmoney cash/bank @user <amount>` · `$remove-money cash/bank @user <amount>`",
        "`$addmoney-role cash/bank @role <amount>` · `$reset-economy`",
        "`$casinorole @role` · `$roomgame #channel` · `$log-channel #channel`",
        "`$currency <emoji>`",
        "`$summer` — once every 24h"
      ].join("\n"), COLOR_INFO, "🎲 Casino Bot")] });
    }

    /* ACCESS / ADMIN CONFIG */
    if (command === "casinorole") {
      if (!message.member.permissions.has(PermissionFlagsBits.Administrator)) return message.reply({ embeds: [embed("❌ Administrator only.", COLOR_LOSE)] });
      if ((args[0] || "").toLowerCase() === "remove") { db.casinoRoleId = null; saveData(); return message.reply({ embeds: [embed("✅ Casino admin role removed.", COLOR_WIN)] }); }
      const role = message.mentions.roles.first();
      if (!role) return message.reply({ embeds: [embed("❌ Usage: `$casinorole @role`", COLOR_LOSE)] });
      db.casinoRoleId = role.id; saveData();
      return message.reply({ embeds: [embed(`✅ Casino admin access is now given to <@&${role.id}>.`, COLOR_WIN)] });
    }
    if (command === "roomgame") {
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      if ((args[0] || "").toLowerCase() === "clear") { db.gameChannels = []; saveData(); return message.reply({ embeds: [embed("✅ Game-room restriction cleared. Games work everywhere again.", COLOR_WIN)] }); }
      const channel = message.mentions.channels.first();
      if (!channel) return message.reply({ embeds: [embed("❌ Usage: `$roomgame #channel` or `$roomgame clear`", COLOR_LOSE)] });
      if (!db.gameChannels.includes(channel.id)) db.gameChannels.push(channel.id);
      saveData();
      return message.reply({ embeds: [embed(`✅ Games can now be played in <#${channel.id}>. Add more channels with the same command.`, COLOR_WIN)] });
    }
    if (command === "log-channel") {
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      if ((args[0] || "").toLowerCase() === "off") { db.logChannelId = null; saveData(); return message.reply({ embeds: [embed("✅ Casino logs disabled.", COLOR_WIN)] }); }
      const ch = message.mentions.channels.first();
      if (!ch) return message.reply({ embeds: [embed("❌ Usage: `$log-channel #channel` or `$log-channel off`", COLOR_LOSE)] });
      db.logChannelId = ch.id; saveData();
      return message.reply({ embeds: [embed(`✅ All casino activity logs will go to <#${ch.id}>.`, COLOR_WIN)] });
    }
    if (command === "currency") {
      if (!args[0]) return message.reply({ embeds: [embed(`Current currency: ${db.currency}`, COLOR_INFO)] });
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ Casino-admin only.", COLOR_LOSE)] });
      db.currency = args[0]; saveData();
      return message.reply({ embeds: [embed(`✅ Currency changed to ${args[0]}.`, COLOR_WIN)] });
    }

    /* MONEY ADMIN */
    if (command === "addmoney" || command === "remove-money") {
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      const location = (args[0] || "").toLowerCase();
      const target = message.mentions.users.first();
      const amount = Number(args[2]);
      if (!['cash','bank'].includes(location) || !target || !Number.isFinite(amount) || amount <= 0) return message.reply({ embeds: [embed(`❌ Usage: \`$${command} cash/bank @user <amount>\``, COLOR_LOSE)] });
      const u = getUser(target.id), n = Math.floor(amount);
      if (command === "addmoney") u[location] += n;
      else u[location] = Math.max(0, u[location] - n);
      saveData();
      await logEvent(message.guild, `**${command}**: ${message.author.tag} changed <@${target.id}> ${location} by **${money(n)}** ${db.currency}.`, command === "addmoney" ? COLOR_WIN : COLOR_LOSE);
      return message.reply({ embeds: [embed(`${command === "addmoney" ? "✅ Added" : "🗑️ Removed"} **${money(n)}** ${db.currency} ${command === "addmoney" ? "to" : "from"} <@${target.id}>'s ${location}.`, command === "addmoney" ? COLOR_WIN : COLOR_LOSE)] });
    }
    if (command === "addmoney-role") {
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      const location = (args[0] || "").toLowerCase();
      const role = message.mentions.roles.first();
      const amount = Number(args[2]);
      if (!['cash','bank'].includes(location) || !role || !Number.isFinite(amount) || amount <= 0) return message.reply({ embeds: [embed("❌ Usage: `$addmoney-role cash/bank @role <amount>`", COLOR_LOSE)] });
      await message.guild.members.fetch();
      const n = Math.floor(amount); let count = 0;
      for (const [, member] of message.guild.members.cache) {
        if (!member.user.bot && member.roles.cache.has(role.id)) { getUser(member.id)[location] += n; count++; }
      }
      saveData();
      return message.reply({ embeds: [embed(`✅ Added **${money(n)}** ${db.currency} to ${count} members with <@&${role.id}> (${location}).`, COLOR_WIN)] });
    }
    if (command === "reset-economy" || command === "reset-economey") {
      if (!hasCasinoAccess(message.member)) return message.reply({ embeds: [embed("❌ You don't have casino-admin access.", COLOR_LOSE)] });
      for (const id of Object.keys(db.users)) { db.users[id].cash = 0; db.users[id].bank = 0; }
      saveData();
      await logEvent(message.guild, `⚠️ Economy reset by **${message.author.tag}**. All stored cash and bank balances were set to 0.`, COLOR_LOSE);
      return message.reply({ embeds: [embed("⚠️ Economy reset complete. Cash, bank and leaderboard balances are now 0 for every stored user.", COLOR_LOSE)] });
    }

    /* BALANCE / BANK / PAY */
    if (["bal","balance"].includes(command)) {
      const target = message.mentions.users.first() || message.author, u = getUser(target.id), total = u.cash + u.bank;
      return message.reply({ embeds: [embed(`**${target.username}**\n\n💵 Cash: **${money(u.cash)}** ${db.currency}\n🏦 Bank: **${money(u.bank)}** ${db.currency}\n📊 Total: **${money(total)}** ${db.currency}`, COLOR_INFO, "💰 Balance")] });
    }
    if (["deposit","dep"].includes(command)) {
      const raw = (args[0] || "").toLowerCase();
      let amount = raw === "all" ? user.cash : raw === "half" ? Math.floor(user.cash / 2) : Number(raw);
      if (!Number.isFinite(amount) || amount <= 0 || amount > user.cash) return message.reply({ embeds: [embed("❌ Usage: `$deposit <amount|half|all>`", COLOR_LOSE)] });
      amount = Math.floor(amount); user.cash -= amount; user.bank += amount; saveData();
      return message.reply({ embeds: [embed(`🏦 Deposited **${money(amount)}** ${db.currency}.`, COLOR_WIN)] });
    }
    if (["withdraw","with","wd"].includes(command)) {
      const raw = (args[0] || "").toLowerCase();
      let amount = raw === "all" ? user.bank : raw === "half" ? Math.floor(user.bank / 2) : Number(raw);
      if (!Number.isFinite(amount) || amount <= 0 || amount > user.bank) return message.reply({ embeds: [embed("❌ Usage: `$withdraw <amount|half|all>`", COLOR_LOSE)] });
      amount = Math.floor(amount); user.bank -= amount; user.cash += amount; saveData();
      return message.reply({ embeds: [embed(`💵 Withdrew **${money(amount)}** ${db.currency}.`, COLOR_WIN)] });
    }
    if (command === "pay") {
      const target = message.mentions.users.first();
      const raw = (args[1] || "").toLowerCase();
      let amount = raw === "all" ? user.cash : raw === "half" ? Math.floor(user.cash / 2) : Number(raw);
      if (!target || target.id === message.author.id || !Number.isFinite(amount) || amount <= 0 || amount > user.cash) return message.reply({ embeds: [embed("❌ Usage: `$pay @user <amount|half|all>`", COLOR_LOSE)] });
      amount = Math.floor(amount); user.cash -= amount; getUser(target.id).cash += amount; saveData();
      return message.reply({ embeds: [embed(`✅ Sent **${money(amount)}** ${db.currency} to <@${target.id}>.`, COLOR_WIN)] });
    }
    if (["lb","leaderboard","top"].includes(command)) {
      const cashOnly = (args[0] || "").toLowerCase() === "cash";
      const list = Object.entries(db.users).sort((a,b) => (cashOnly ? b[1].cash-a[1].cash : (b[1].cash+b[1].bank)-(a[1].cash+a[1].bank))).slice(0,10);
      const text = list.length ? list.map(([id,u],i)=>`**${i+1}.** <@${id}> — **${money(cashOnly?u.cash:u.cash+u.bank)}** ${db.currency}`).join("\n") : "No users yet.";
      return message.reply({ embeds: [embed(text, COLOR_INFO, cashOnly ? "💵 Top Cash" : "🏆 Leaderboard")] });
    }

    /* DAILY SUMMER WHEEL */
    if (command === "summer") return summer(message, user);

    /* ECONOMY */
    if (command === "work") {
      const left = onCooldown(user,"work",4*60*1000); if (left) return message.reply({ embeds:[embed(`⏳ Work again in **${formatDuration(left)}**.`,COLOR_LOSE)] });
      const n=random(4000,12000); user.cash+=n; user.cooldowns.work=Date.now(); saveData();
      return message.reply({ embeds:[embed(`💼 You earned **${money(n)}** ${db.currency}!`,COLOR_WIN)] });
    }
    if (command === "crime") {
      const left=onCooldown(user,"crime",4*60*1000); if(left)return message.reply({embeds:[embed(`⏳ Crime again in **${formatDuration(left)}**.`,COLOR_LOSE)]});
      user.cooldowns.crime=Date.now(); const win=Math.random()<.75;
      if(win){const n=random(6000,15000);user.cash+=n;saveData();return message.reply({embeds:[embed(`🚨 Crime succeeded: **${money(n)}** ${db.currency}!`,COLOR_WIN)]});}
      const fine=random(1000,3000);user.cash=Math.max(0,user.cash-fine);saveData();return message.reply({embeds:[embed(`🚔 Caught. Fine: **${money(fine)}** ${db.currency}.`,COLOR_LOSE)]});
    }
    if (command === "rob") {
      const left=onCooldown(user,"rob",8*60*1000); if(left)return message.reply({embeds:[embed(`⏳ Rob again in **${formatDuration(left)}**.`,COLOR_LOSE)]});
      const target=message.mentions.users.first(); if(!target||target.id===message.author.id)return message.reply({embeds:[embed("❌ Usage: `$rob @user`",COLOR_LOSE)]});
      const t=getUser(target.id); if(t.cash<500)return message.reply({embeds:[embed("❌ Target needs at least 500 cash.",COLOR_LOSE)]});
      user.cooldowns.rob=Date.now(); if(Math.random()<.45){const n=Math.max(1,Math.floor(t.cash*randomFloat(.1,.3)));t.cash-=n;user.cash+=n;saveData();return message.reply({embeds:[embed(`🕵️ Stole **${money(n)}** ${db.currency} from <@${target.id}>.`,COLOR_WIN)]});}
      const fine=random(500,1500);user.cash=Math.max(0,user.cash-fine);saveData();return message.reply({embeds:[embed(`🚔 Rob failed. Fine: **${money(fine)}** ${db.currency}.`,COLOR_LOSE)]});
    }

    /* GAMES */
    if (["bj","blackjack"].includes(command)) return gameRoomCheck(message) && blackjack(message,args,user);
    if (["ht","coinflip"].includes(command)) return gameRoomCheck(message) && coinflip(message,args,user);
    if (["hl","higherlower"].includes(command)) return gameRoomCheck(message) && higherLower(message,args,user);
    if (["cf","cockfight","chickenfight"].includes(command)) return gameRoomCheck(message) && cockfight(message,args,user);
    if (["mines","mine"].includes(command)) return gameRoomCheck(message) && mines(message,args,user);
    if (["gm","goldmine"].includes(command)) return gameRoomCheck(message) && goldmine(message,args,user);
    if (["slots","slot"].includes(command)) return gameRoomCheck(message) && slots(message,args,user);
    if (["roulette","rl"].includes(command)) return gameRoomCheck(message) && roulette(message,args,user);
    if (["wheel"].includes(command)) return gameRoomCheck(message) && wheel(message,args,user);
    if (["crash"].includes(command)) return gameRoomCheck(message) && crash(message,args,user);
    if (["texas","poker"].includes(command)) return gameRoomCheck(message) && texasHoldem(message, args, user);

    if (command === "info") return message.reply({embeds:[buildInfoEmbed()]});
  } catch(e) {
    console.error("Command error:",e);
    message.reply({embeds:[embed("❌ Something went wrong.",COLOR_LOSE)]}).catch(()=>{});
  }
});

/* =========================== BLACKJACK ======================== */
const CARD_VALUES=[["A",11],["2",2],["3",3],["4",4],["5",5],["6",6],["7",7],["8",8],["9",9],["10",10],["J",10],["Q",10],["K",10]];
const TEN_VALUE_CARDS=["10","J","Q","K"];
const CARD_GLYPHS={
  "♠":["🂡","🂢","🂣","🂤","🂥","🂦","🂧","🂨","🂩","🂪","🂫","🂭","🂮"],
  "♥":["🂱","🂲","🂳","🂴","🂵","🂶","🂷","🂸","🂹","🂺","🂻","🂽","🂾"],
  "♦":["🃁","🃂","🃃","🃄","🃅","🃆","🃇","🃈","🃉","🃊","🃋","🃍","🃎"],
  "♣":["🃑","🃒","🃓","🃔","🃕","🃖","🃗","🃘","🃙","🃚","🃛","🃝","🃞"]
};
const SUITS=["♠","♥","♦","♣"];
function rankIndex(v){return CARD_VALUES.findIndex(x=>x[0]===v)}
function makeCard(v,n){const s=SUITS[random(0,3)];return{value:v,number:n,glyph:CARD_GLYPHS[s][rankIndex(v)]}}
function drawStandardCard(){const x=CARD_VALUES[random(0,CARD_VALUES.length-1)];return makeCard(x[0],x[1])}
function handValue(hand){let t=hand.reduce((s,c)=>s+c.number,0),a=hand.filter(c=>c.value==="A").length;while(t>21&&a-- >0)t-=10;return t}
function handText(hand){return hand.map(c=>c.glyph).join(" ")}
function dealPlayerHand(){
  if(Math.random()<.234){const ten=TEN_VALUE_CARDS[random(0,3)], tc=CARD_VALUES.find(x=>x[0]===ten);return shuffle([makeCard("A",11),makeCard(tc[0],tc[1])]);}
  return[drawStandardCard(),drawStandardCard()];
}
async function blackjack(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();
  const player=dealPlayerHand(),dealer=[drawStandardCard(),drawStandardCard()];let totalBet=bet,finished=false;
  const natural=handValue(player)===21;
  const row=new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`bj:hit:${message.author.id}`).setLabel("HIT").setStyle(ButtonStyle.Primary),
    new ButtonBuilder().setCustomId(`bj:stand:${message.author.id}`).setLabel("STAND").setStyle(ButtonStyle.Success),
    new ButtonBuilder().setCustomId(`bj:double:${message.author.id}`).setLabel("DOUBLE").setStyle(ButtonStyle.Secondary).setDisabled(user.cash<bet)
  );
  function gameEmbed(show=false){
    return new EmbedBuilder().setColor(COLOR_NEUTRAL).setTitle("🃏  B L A C K J A C K  🃏")
      .setDescription(`**YOUR HAND**\n${handText(player)}\n**Total: ${handValue(player)}**\n\n**DEALER**\n${show?handText(dealer):handText([dealer[0]])+" 🂠"}\n${show?`**Total: ${handValue(dealer)}**`:"**Total: ?**"}\n\n━━━━━━━━━━━━━━━━━━━━\n💰 **Bet:** ${money(totalBet)} ${db.currency}\n🎯 **Natural chance:** 23.4%`)
      .setFooter({text:"Choose an action below • 120 second timer"});
  }
  if(natural){const payout=Math.floor(totalBet*2.5);user.cash+=payout;saveData();return message.reply({embeds:[embed(`🃏 **BLACKJACK!**\n\nYour hand: ${handText(player)} — **21**\nDealer: ${handText(dealer)} — **${handValue(dealer)}**\n\nPayout: **${money(payout)}** ${db.currency}`,COLOR_WIN,"🃏 Blackjack 🃏")]});}
  const gm=await message.reply({embeds:[gameEmbed()],components:[row]});
  const collector=gm.createMessageComponentCollector({time:120000});
  async function finish(result,payout,color){if(finished)return;finished=true;collector.stop();if(payout>0)user.cash+=payout;saveData();await gm.edit({embeds:[embed(`**YOUR HAND**\n${handText(player)} — **${handValue(player)}**\n\n**DEALER**\n${handText(dealer)} — **${handValue(dealer)}**\n\n${result}${payout?`\nPayout: **${money(payout)}**${db.currency}`:""}`,color,"🃏 Blackjack 🃏")],components:[disabledRow(row)]});}
  collector.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});const a=i.customId.split(":")[1];
    if(a==="double"){if(user.cash<bet)return i.reply({content:"❌ Not enough cash.",ephemeral:true});user.cash-=bet;totalBet+=bet;player.push(drawStandardCard());await i.deferUpdate();if(handValue(player)>21)return finish("💥 Bust!",0,COLOR_LOSE);while(handValue(dealer)<17)dealer.push(drawStandardCard());const p=handValue(player),d=handValue(dealer);if(d>21||p>d)return finish("🎉 You win!",totalBet*2,COLOR_WIN);if(p===d)return finish("🤝 Push!",totalBet,COLOR_INFO);return finish("❌ Dealer wins.",0,COLOR_LOSE);}
    if(a==="hit"){player.push(drawStandardCard());if(handValue(player)>21){await i.deferUpdate();return finish("💥 Bust!",0,COLOR_LOSE)}return i.update({embeds:[gameEmbed()],components:[row]});}
    await i.deferUpdate();while(handValue(dealer)<17)dealer.push(drawStandardCard());const p=handValue(player),d=handValue(dealer);if(d>21||p>d)return finish("🎉 You win!",totalBet*2,COLOR_WIN);if(p===d)return finish("🤝 Push!",totalBet,COLOR_INFO);return finish("❌ Dealer wins.",0,COLOR_LOSE);
  });
  collector.on("end",async()=>{if(finished)return;finished=true;user.cash+=totalBet;saveData();await gm.edit({embeds:[embed(`⏰ Game timed out. Returned **${money(totalBet)}** ${db.currency}.`,COLOR_NEUTRAL,"🃏 Blackjack 🃏")],components:[disabledRow(row)]}).catch(()=>{});});
}

/* ========================== COINFLIP ========================== */
async function coinflip(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();
  const row=new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`ht:h:${message.author.id}`).setLabel("Heads").setStyle(ButtonStyle.Primary),new ButtonBuilder().setCustomId(`ht:t:${message.author.id}`).setLabel("Tails").setStyle(ButtonStyle.Success));
  const msg=await message.reply({embeds:[embed(`**Bet:** ${money(bet)} ${db.currency}\n\nChoose Heads or Tails.`,COLOR_NEUTRAL,"🍀 CoinFlip 🍀")],components:[row]});
  const c=msg.createMessageComponentCollector({time:60000,max:1});c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});const result=Math.random()<.5?"h":"t",choice=i.customId.split(":")[1],win=result===choice;if(win)user.cash+=bet*2;saveData();await i.update({embeds:[embed(`${result==="h"?"🪙 Heads":"🪙 Tails"}\n\n${win?`🎉 Won **${money(bet*2)}**${db.currency}!`:`❌ Lost **${money(bet)}**${db.currency}.`}`,win?COLOR_WIN:COLOR_LOSE,"🍀 CoinFlip 🍀")],components:[disabledRow(row)]});});c.on("end",async col=>{if(col.size)return;user.cash+=bet;saveData();await msg.edit({embeds:[embed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,COLOR_NEUTRAL,"🍀 CoinFlip 🍀")],components:[disabledRow(row)]}).catch(()=>{})});
}

/* ======================= HIGHER / LOWER ====================== */
function hlMultipliers(current){const higher=100-current,lower=current-1;return{higher:Math.round(Math.min(15,Math.max(1.01,(100/higher)*1.02))*100)/100,lower:Math.round(Math.min(15,Math.max(1.01,(100/lower)*1.02))*100)/100,same:8};}
async function higherLower(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();const current=random(2,99),mult=hlMultipliers(current);
  const row=new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`hl:hi:${message.author.id}`).setLabel("Higher").setStyle(ButtonStyle.Primary),new ButtonBuilder().setCustomId(`hl:eq:${message.author.id}`).setLabel("Same").setStyle(ButtonStyle.Primary),new ButtonBuilder().setCustomId(`hl:lo:${message.author.id}`).setLabel("Lower").setStyle(ButtonStyle.Primary));
  const msg=await message.reply({embeds:[embed(`**Betting Amount:** ${money(bet)}\n\n**1:** ${current}\n**2:** ❓\n\nHigher: **${mult.higher}x**\nSame: **${mult.same}x**\nLower: **${mult.lower}x**`,COLOR_NEUTRAL,"🎲 Higher or Lower 🎲")],components:[row]});
  const c=msg.createMessageComponentCollector({time:60000,max:1});c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});const next=random(1,100),choice=i.customId.split(":")[1],win=(choice==="hi"&&next>current)||(choice==="lo"&&next<current)||(choice==="eq"&&next===current),m=choice==="hi"?mult.higher:choice==="lo"?mult.lower:mult.same,payout=win?Math.floor(bet*m):0;if(payout)user.cash+=payout;saveData();await i.update({embeds:[embed(`**1:** ${current}\n**2:** ${next}\n\n${win?`🎉 Won **${money(payout)}**${db.currency}!`:`❌ Lost **${money(bet)}**${db.currency}.`}`,win?COLOR_WIN:COLOR_LOSE,"🎲 Higher or Lower 🎲")],components:[disabledRow(row)]});});c.on("end",async col=>{if(col.size)return;user.cash+=bet;saveData();await msg.edit({embeds:[embed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,COLOR_NEUTRAL,"🎲 Higher or Lower 🎲")],components:[disabledRow(row)]}).catch(()=>{})});
}

/* =========================== COCKFIGHT ======================== */
async function cockfight(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;
  const chance=user.cfStreak||55,win=Math.random()*100<chance;
  let text = "";
  if(win){
    const payout=bet*2;
    user.cash+=payout;
    user.cfStreak=Math.min(82,chance+1);
    saveData();
    text = `Your chicken won the fight, you won ${money(payout)} 💸🐔!\n\nYour chicken's strength (chance of winning): ${chance}%\nYou now have ${money(user.cash)} 💸`;
  } else {
    user.cfStreak=55;
    saveData();
    text = `Your chicken lost the fight... You lost ${money(bet)} 💸🐔.`;
  }
  return message.reply({content: text});
}

/* ============================= MINES ========================== */
const MINES_MULTIPLIERS=[1.1,1.4,1.8,2.1,2.8,4.2,6.2,8.9];
async function mines(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();const bomb=random(0,8),revealed=new Set();let finished=false;
  function mult(){return MINES_MULTIPLIERS[Math.max(0,revealed.size-1)]||8.9}
  function rows(end=false){
    const out=[];
    for(let r=0;r<3;r++){
      const bs=[];
      for(let c=0;c<3;c++){
        const i=r*3+c,isBomb=i===bomb,isRev=revealed.has(i);
        bs.push(new ButtonBuilder()
          .setCustomId(`mn:${message.author.id}:${i}`)
          .setLabel(end?(isBomb?"💣":"💎"):(isRev?"💎":"⬛"))
          .setStyle(end&&isBomb?ButtonStyle.Danger:isRev?ButtonStyle.Success:ButtonStyle.Secondary)
          .setDisabled(isRev||end));
      }
      out.push(new ActionRowBuilder().addComponents(bs));
    }
    out.push(new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId(`mn:${message.author.id}:cash`).setLabel("Cashout").setStyle(ButtonStyle.Success).setDisabled(!revealed.size||end),
      new ButtonBuilder().setCustomId(`mn:${message.author.id}:profit`).setLabel(`Profit: ${money(revealed.size ? Math.floor(bet*mult()) - bet : 0)} 💸`).setStyle(ButtonStyle.Primary).setDisabled(true)
    ));
    return out;
  }
  const msg=await message.reply({content: `**${message.author.username}'s Game**`, components:rows()});
  const c=msg.createMessageComponentCollector({time:120000});
  c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});if(finished)return;const a=i.customId.split(":")[2];
    if(a==="cash"){if(!revealed.size)return i.reply({content:"❌ Reveal a tile first.",ephemeral:true});finished=true;c.stop();const p=Math.floor(bet*mult());user.cash+=p;saveData();return i.update({content:`- You Won ${money(p)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}
    const idx=Number(a);if(idx===bomb){finished=true;c.stop();saveData();return i.update({content:`- You Lost ${money(bet)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}
    revealed.add(idx);if(revealed.size===8){finished=true;c.stop();const p=Math.floor(bet*MINES_MULTIPLIERS[7]);user.cash+=p;saveData();return i.update({content:`- You Won ${money(p)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}return i.update({components:rows()});
  });
  c.on("end",async()=>{if(finished)return;finished=true;user.cash+=bet;saveData();await msg.edit({content:`⏰ Timed out. Returned ${money(bet)} 💸.`,components:rows(true)}).catch(()=>{})});
}

/* ============================ GOLDMINE ======================== */
const GOLDMINE_TREASURE_COUNTS=[{key:"rock",emoji:"🪨",mult:1.2,count:4},{key:"coin",emoji:"🪙",mult:2.5,count:3},{key:"diamond",emoji:"💎",mult:3.5,count:2},{key:"moneybag",emoji:"💰",mult:6.5,count:1},{key:"lantern",emoji:"🏮",mult:20,count:1}];
function buildGoldmineBoard(){const ids=shuffle([...Array(24).keys()]),b=new Array(24);let c=0;for(const i of ids.slice(c,c+12)){b[i]={type:"bomb"};c++;}for(const d of GOLDMINE_TREASURE_COUNTS){for(const i of ids.slice(c,c+d.count)){b[i]={type:"treasure",...d};c++;}}b[ids[c]]={type:"map"};return b}
async function goldmine(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();const board=buildGoldmineBoard(),revealed=new Set();let mult=1,finished=false;
  function label(i,end){const t=board[i];if(end){if(t.type==="bomb")return"💣";if(t.type==="map")return"🗺️";return t.emoji}if(!revealed.has(i))return"⬛";if(t.type==="map")return"🗺️";return t.emoji}
  function rows(end=false){
    const rs=[];
    for(let r=0;r<5;r++){
      const bs=[];
      for(let c=0;c<(r===4?4:5);c++){
        const i=r*5+c;if(i>=24)continue;
        bs.push(new ButtonBuilder()
          .setCustomId(`gm:${message.author.id}:${i}`)
          .setLabel(label(i,end))
          .setStyle(end&&board[i].type==="bomb"?ButtonStyle.Danger:revealed.has(i)?ButtonStyle.Success:ButtonStyle.Secondary)
          .setDisabled(revealed.has(i)||end));
      }
      if(r===4){
        rs.push(new ActionRowBuilder().addComponents(bs));
        rs.push(new ActionRowBuilder().addComponents(
          new ButtonBuilder().setCustomId(`gm:${message.author.id}:cash`).setLabel("Cashout").setStyle(ButtonStyle.Success).setDisabled(!revealed.size||end),
          new ButtonBuilder().setCustomId(`gm:${message.author.id}:profit`).setLabel(`Profit: ${money(revealed.size ? Math.floor(bet*mult) - bet : 0)} 💸`).setStyle(ButtonStyle.Primary).setDisabled(true)
        ));
      } else {
        rs.push(new ActionRowBuilder().addComponents(bs));
      }
    }
    return rs;
  }
  const msg=await message.reply({content: `**${message.author.username}'s Game**`, components:rows()});
  const c=msg.createMessageComponentCollector({time:150000});
  c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});if(finished)return;const a=i.customId.split(":")[2];
    if(a==="cash"){finished=true;c.stop();const p=Math.floor(bet*mult);user.cash+=p;saveData();return i.update({content:`- You Won ${money(p)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}
    const idx=Number(a),t=board[idx];if(t.type==="bomb"){finished=true;c.stop();saveData();return i.update({content:`- You Lost ${money(bet)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}
    if(t.type==="map"){revealed.add(idx);const pool=shuffle([...Array(24).keys()].filter(x=>!revealed.has(x)&&board[x].type!=="bomb")).slice(0,3);for(const x of pool){revealed.add(x);if(board[x].type==="treasure")mult*=board[x].mult;}}else{revealed.add(idx);mult*=t.mult;}
    if(revealed.size>=12){finished=true;c.stop();const p=Math.floor(bet*mult);user.cash+=p;saveData();return i.update({content:`- You Won ${money(p)} 💸\n\nYou now have ${money(user.cash)} 💸.`,components:rows(true)});}return i.update({components:rows()});
  });
  c.on("end",async()=>{if(finished)return;finished=true;user.cash+=bet;saveData();await msg.edit({content:`⏰ Timed out. Returned ${money(bet)} 💸.`,components:rows(true)}).catch(()=>{})});
}

/* ============================== SLOTS ========================= */
const SLOT_SYMBOLS=[{emoji:"🍒",weight:30,triple:3},{emoji:"🍋",weight:25,triple:4},{emoji:"🍊",weight:20,triple:5},{emoji:"🍇",weight:15,triple:6},{emoji:"⭐",weight:8,triple:10},{emoji:"7️⃣",weight:2,triple:20}];
async function slots(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();
  const reels=[weightedPick(SLOT_SYMBOLS),weightedPick(SLOT_SYMBOLS),weightedPick(SLOT_SYMBOLS)];
  let mult=0,line="❌ No match.";if(reels[0].emoji===reels[1].emoji&&reels[1].emoji===reels[2].emoji){mult=reels[0].triple;line=`🎉 Triple ${reels[0].emoji}!`}else if(reels[0].emoji===reels[1].emoji||reels[1].emoji===reels[2].emoji||reels[0].emoji===reels[2].emoji){mult=1.2;line="🙂 Two matching symbols."}
  const msg=await message.reply({embeds:[embed(`🎰 **SPINNING...**\n\n[ ❔ | ❔ | ❔ ]\n\n⏳ Result in **3 seconds**...`,COLOR_NEUTRAL,"🎰 Slots 🎰")]});
  for(let n=2;n>=1;n--){await new Promise(r=>setTimeout(r,1000));await msg.edit({embeds:[embed(`🎰 **SPINNING...**\n\n[ ${n===2?"🍒":"⭐"} | ${n===2?"❔":"🍋"} | ❔ ]\n\n⏳ **${n} second${n===1?"":"s"}**...`,COLOR_NEUTRAL,"🎰 Slots 🎰")] }).catch(()=>{});}
  const payout=Math.floor(bet*mult);if(payout)user.cash+=payout;saveData();return msg.edit({embeds:[embed(`[ ${reels.map(x=>x.emoji).join(" | ")} ]\n\n${line}\n\n${payout?`🎉 Won **${money(payout)}**${db.currency}!`:`❌ Lost **${money(bet)}**${db.currency}.`}`,payout?COLOR_WIN:COLOR_LOSE,"🎰 Slots 🎰")]});
}

/* ============================ ROULETTE ======================== */
const ROULETTE_RED=new Set([1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]);
function rouletteColor(n){return n===0?"green":ROULETTE_RED.has(n)?"red":"black"}
async function roulette(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;const choice=(args[1]||"").toLowerCase(),isNum=/^\d+$/.test(choice);
  if((!isNum&&!['red','black','green'].includes(choice))||(isNum&&(Number(choice)<0||Number(choice)>36)))return message.reply({embeds:[embed("❌ Usage: `$roulette <amount|half|all> <red/black/green/0-36>`",COLOR_LOSE)]});
  user.cash-=bet;saveData();const result=random(0,36),color=rouletteColor(result),win=(isNum?Number(choice)===result:choice===color),mult=isNum?30:(color==="green"?14:2),payout=win?Math.floor(bet*mult):0;
  const msg=await message.reply({embeds:[embed(`🎡 **ROULETTE**\n\nBall is spinning...\n\n🎯 Bet: **${money(bet)}** ${db.currency}\n🎲 Choice: **${choice}**\n\n⏳ Result in **3 seconds**...`,COLOR_NEUTRAL,"🎡 Roulette 🎡")]});
  for(let n=2;n>=1;n--){await new Promise(r=>setTimeout(r,1000));await msg.edit({embeds:[embed(`🎡 **ROULETTE**\n\n🔄 Wheel spinning...\n\n⏳ **${n} second${n===1?"":"s"}**...`,COLOR_NEUTRAL,"🎡 Roulette 🎡")] }).catch(()=>{});}
  if(payout)user.cash+=payout;saveData();
  return msg.edit({embeds:[embed(`🎯 Landed on **${result}** (${color})\n\n${win?`🎉 Won **${money(payout)}**${db.currency}!`:`❌ Lost **${money(bet)}**${db.currency}.`}`,win?COLOR_WIN:COLOR_LOSE,"🎡 Roulette 🎡")]});
}

/* ============================== WHEEL ========================= */
const WHEEL_SEGMENTS=[{mult:0,weight:38,label:"💀 Bust"},{mult:1.2,weight:25,label:"🙂 1.2x"},{mult:1.5,weight:17,label:"😀 1.5x"},{mult:2,weight:12,label:"😃 2x"},{mult:5,weight:6,label:"🤑 5x"},{mult:10,weight:2,label:"🏆 10x"}];
async function wheel(message,args,user){const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;const r=weightedPick(WHEEL_SEGMENTS),p=Math.floor(bet*r.mult);if(p)user.cash+=p;saveData();return message.reply({embeds:[embed(`🎡 The wheel lands on **${r.label}**\n\n${p?`🎉 Won **${money(p)}**${db.currency}!`:`❌ Lost **${money(bet)}**${db.currency}.`}`,p?COLOR_WIN:COLOR_LOSE,"🎡 Wheel of Fortune 🎡")]});}

/* ============================== CRASH ========================= */
function rollCrashPoint(){const r=Math.random(),point=.98/(1-r*.94);return Math.max(1.02,Math.round(point*100)/100)}
async function crash(message,args,user){
  const bet=validBet(message,args);if(bet===null)return;user.cash-=bet;saveData();const crashPoint=rollCrashPoint();let mult=1,finished=false;
  const row=new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`cr:cash:${message.author.id}`).setLabel("💰 Cashout").setStyle(ButtonStyle.Success));
  const ge=()=>embed(`📈 Multiplier: **${mult.toFixed(2)}x**\nCurrent value: **${money(bet*mult)}** ${db.currency}\n\nBet: **${money(bet)}** ${db.currency}\n\nCash out before it crashes!`,COLOR_NEUTRAL,"🚀 Crash 🚀");
  const msg=await message.reply({embeds:[ge()],components:[row]});const c=msg.createMessageComponentCollector({time:30000});const interval=setInterval(async()=>{if(finished)return;mult=Math.round(mult*1.15*100)/100;if(mult>=crashPoint){finished=true;clearInterval(interval);c.stop();saveData();await msg.edit({embeds:[embed(`💥 Crashed at **${crashPoint.toFixed(2)}x**!\n\nLost **${money(bet)}** ${db.currency}.`,COLOR_LOSE,"🚀 Crash 🚀")],components:[disabledRow(row)]}).catch(()=>{});return;}await msg.edit({embeds:[ge()],components:[row]}).catch(()=>{})},1500);
  c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your game.",ephemeral:true});if(finished)return;finished=true;clearInterval(interval);c.stop();const p=Math.floor(bet*mult);user.cash+=p;saveData();await i.update({embeds:[embed(`💰 Cashed out at **${mult.toFixed(2)}x**!\n\nPayout: **${money(p)}** ${db.currency}.`,COLOR_WIN,"🚀 Crash 🚀")],components:[disabledRow(row)]})});
  c.on("end",async()=>{if(finished)return;finished=true;clearInterval(interval);user.cash+=bet;saveData();await msg.edit({embeds:[embed(`⏰ Timed out. Returned **${money(bet)}** ${db.currency}.`,COLOR_NEUTRAL,"🚀 Crash 🚀")],components:[disabledRow(row)]}).catch(()=>{})});
}

/* ============================ TEXAS HOLDEM ==================== */
async function texasHoldem(message, args, user) {
  const bet = validBet(message, args);
  if (bet === null) return;

  const joinRow = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId("texas_join").setLabel("Join Game").setStyle(ButtonStyle.Success)
  );

  const inviteMsg = await message.reply({
    embeds: [embed(`🃏 **Texas Hold'em 1v1**\n\nHost: <@${message.author.id}>\nBet: **${money(bet)}** ${db.currency}\n\nWaiting for another player to join!`, COLOR_INFO, "Texas Hold'em")],
    components: [joinRow]
  });

  const collector = inviteMsg.createMessageComponentCollector({ time: 60000, max: 1 });

  collector.on("collect", async i => {
    if (i.user.id === message.author.id) {
      return i.reply({ content: "❌ You cannot play against yourself.", ephemeral: true });
    }

    const opponentUser = getUser(i.user.id);
    if (opponentUser.cash < bet) {
      return i.reply({ content: `❌ You don't have enough cash. Minimum required is **${money(bet)}** ${db.currency}.`, ephemeral: true });
    }

    // Deduct bets
    user.cash -= bet;
    opponentUser.cash -= bet;
    saveData();

    await i.update({
      embeds: [embed(`🃏 **Texas Hold'em 1v1 Started!**\n\nPlayers: <@${message.author.id}> vs <@${i.user.id}>\nPot: **${money(bet * 2)}** ${db.currency}\n\nCheck your DMs for your private cards!`, COLOR_WIN, "Texas Hold'em")],
      components: []
    });

    // Draw cards for both
    const deck = shuffle(CARD_VALUES.flatMap(([v, n]) => SUITS.map(s => ({ value: v, number: n, glyph: CARD_GLYPHS[s][rankIndex(v)] }))));
    const p1Cards = [deck.pop(), deck.pop()];
    const p2Cards = [deck.pop(), deck.pop()];
    const communityCards = [deck.pop(), deck.pop(), deck.pop()];

    // Send private cards via DM
    try {
      const u1 = await client.users.fetch(message.author.id);
      await u1.send({ embeds: [embed(`Your private cards: ${p1Cards.map(c => c.glyph).join(" ")}`, COLOR_INFO, "Texas Hold'em - Hand")] });
    } catch (e) {
      message.channel.send(`<@${message.author.id}>, please open your DMs to receive your cards!`);
    }

    try {
      const u2 = await client.users.fetch(i.user.id);
      await u2.send({ embeds: [embed(`Your private cards: ${p2Cards.map(c => c.glyph).join(" ")}`, COLOR_INFO, "Texas Hold'em - Hand")] });
    } catch (e) {
      message.channel.send(`<@${i.user.id}>, please open your DMs to receive your cards!`);
    }

    // Game table interaction
    let turn = message.author.id;
    let pot = bet * 2;

    const gameRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId("tx_check").setLabel("Check").setStyle(ButtonStyle.Primary),
      new ButtonBuilder().setCustomId("tx_call").setLabel("Call").setStyle(ButtonStyle.Success),
      new ButtonBuilder().setCustomId("tx_fold").setLabel("Fold").setStyle(ButtonStyle.Danger)
    );

    const tableMsg = await message.channel.send({
      embeds: [embed(`**Community Cards:** ${communityCards.map(c => c.glyph).join(" ")}\n\nPot: **${money(pot)}** ${db.currency}\n\nTurn: <@${turn}>`, COLOR_NEUTRAL, "Texas Hold'em Table")],
      components: [gameRow]
    });

    const gameCollector = tableMsg.createMessageComponentCollector({ time: 120000 });

    gameCollector.on("collect", async gi => {
      if (gi.user.id !== message.author.id && gi.user.id !== i.user.id) {
        return gi.reply({ content: "❌ This is not your game.", ephemeral: true });
      }
      if (gi.user.id !== turn) {
        return gi.reply({ content: "❌ Not your turn.", ephemeral: true });
      }

      const action = gi.customId.split("_")[1];

      if (action === "fold") {
        gameCollector.stop();
        const winnerId = gi.user.id === message.author.id ? i.user.id : message.author.id;
        getUser(winnerId).cash += pot;
        saveData();
        return gi.update({
          embeds: [embed(`🏳️ <@${gi.user.id}> folded!\n\n🎉 Winner: <@${winnerId}> takes **${money(pot)}** ${db.currency}!`, COLOR_WIN, "Texas Hold'em Ended")],
          components: [disabledRow(gameRow)]
        });
      }

      if (action === "check" || action === "call") {
        // Determine winner randomly or simple comparison for 1v1 finish
        gameCollector.stop();
        const p1Val = handValue(p1Cards) + communityCards.reduce((s, c) => s + c.number, 0);
        const p2Val = handValue(p2Cards) + communityCards.reduce((s, c) => s + c.number, 0);

        let winnerId;
        if (p1Val > p2Val) winnerId = message.author.id;
        else if (p2Val > p1Val) winnerId = i.user.id;
        else winnerId = null; // Tie

        if (winnerId) {
          getUser(winnerId).cash += pot;
          saveData();
          return gi.update({
            embeds: [embed(`🃏 **Showdown!**\n\n<@${message.author.id}> Cards: ${p1Cards.map(c => c.glyph).join(" ")}\n<@${i.user.id}> Cards: ${p2Cards.map(c => c.glyph).join(" ")}\n\n🎉 Winner: <@${winnerId}> takes **${money(pot)}** ${db.currency}!`, COLOR_WIN, "Texas Hold'em Showdown")],
            components: [disabledRow(gameRow)]
          });
        } else {
          const half = Math.floor(pot / 2);
          getUser(message.author.id).cash += half;
          getUser(i.user.id).cash += half;
          saveData();
          return gi.update({
            embeds: [embed(`🤝 **It's a Tie!** Pot split evenly (**${money(half)}** ${db.currency} each).`, COLOR_INFO, "Texas Hold'em Showdown")],
            components: [disabledRow(gameRow)]
          });
        }
      }
    });

    gameCollector.on("end", async collected => {
      if (collected.size === 0) {
        getUser(message.author.id).cash += bet;
        getUser(i.user.id).cash += bet;
        saveData();
        await tableMsg.edit({
          embeds: [embed(`⏰ Game timed out. Bets returned.`, COLOR_NEUTRAL, "Texas Hold'em")],
          components: [disabledRow(gameRow)]
        }).catch(() => {});
      }
    });
  });

  collector.on("end", async collected => {
    if (collected.size === 0) {
      getUser(message.author.id).cash += bet;
      saveData();
      await inviteMsg.edit({
        embeds: [embed(`⏰ Game invitation timed out. Bet returned.`, COLOR_NEUTRAL, "Texas Hold'em")],
        components: [disabledRow(joinRow)]
      }).catch(() => {});
    }
  });
}

/* ============================== SUMMER ======================== */
const SUMMER_PRIZES=[
  {amount:1750000,weight:45,label:"1,750,000"},
  {amount:25000000,weight:30,label:"25,000,000"},
  {amount:65000000,weight:15,label:"65,000,000"},
  {amount:100000000,weight:5,label:"100,000,000 JACKPOT"}
];
async function summer(message,user){
  const last=db.summer[message.author.id]||0,left=24*60*60*1000-(Date.now()-last);if(left>0)return message.reply({embeds:[embed(`⏳ Your Summer wheel is ready again in **${formatDuration(left)}**.`,COLOR_LOSE,"☀️ Summer ☀️")]});
  const result=weightedPick(SUMMER_PRIZES);db.summer[message.author.id]=Date.now();saveData();
  const row=new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId(`summer:spin:${message.author.id}`).setLabel("☀️ SPIN").setStyle(ButtonStyle.Primary));
  const msg=await message.reply({embeds:[embed(`☀️ **SUMMER DAILY WHEEL** ☀️\n\n🎁 1,750,000 — 45%\n🎁 25,000,000 — 30%\n🎁 65,000,000 — 15%\n🏆 100,000,000 JACKPOT — 5%\n\nPress **SPIN**. You get one spin every 24 hours.`,COLOR_PURPLE,"☀️ Summer ☀️")],components:[row]});
  const c=msg.createMessageComponentCollector({time:30000,max:1});c.on("collect",async i=>{if(i.user.id!==message.author.id)return i.reply({content:"❌ This isn't your wheel.",ephemeral:true});await i.deferUpdate();for(let n=0;n<8;n++){await new Promise(r=>setTimeout(r,120));await msg.edit({embeds:[embed(`☀️ **SUMMER WHEEL**\n\n🔄 ${["1,750,000","25,000,000","65,000,000","100,000,000 JACKPOT"][n%4]}\n\n🎡 Spinning...`,COLOR_PURPLE,"☀️ Summer ☀️")],components:[]}).catch(()=>{})}user.cash+=result.amount;saveData();await logEvent(message.guild,`☀️ Summer result for <@${message.author.id}>: **${result.label}** ${db.currency}.`,COLOR_WIN);await msg.edit({embeds:[embed(`🎉 **THE WHEEL STOPPED!**\n\n🏆 Prize: **${result.label}** ${db.currency}\n\nYour new cash: **${money(user.cash)}** ${db.currency}.`,COLOR_WIN,"☀️ Summer ☀️")],components:[]}).catch(()=>{})});
}

/* ============================== INFO ========================== */
function buildInfoEmbed(){return embed([
  "**🃏 Blackjack — `$bj <amount|half|all>`**","Natural blackjack chance: **23.4%**. Hit / Stand / Double. Natural pays 2.5x.","",
  "**🐔 Cockfight — `$cf <amount|half|all>`**","Starts at 55% and increases by 1% after wins, up to 82%.","",
  "**🎲 Higher or Lower — `$hl <amount|half|all>`**","Choose Higher, Same or Lower. Same pays 8x.","",
  "**🍀 CoinFlip — `$ht <amount|half|all>`**","Heads/Tails, pays 2x.","",
  "**💣 Mines — `$mines <amount|half|all>`**","3x3, one bomb. Multipliers: 1.1x → 8.9x. Cash out anytime.","",
  "**⛏️ Goldmine — `$gm <amount|half|all>`**","24 tiles, 12 bombs, treasure multipliers compound.","",
  "**🎰 Slots — `$slots <amount|half|all>`**","3 reels. Triple 7️⃣ = 20x, ⭐ = 10x, 🍇 = 6x, 🍊 = 5x, 🍋 = 4x, 🍒 = 3x. Two matching = 1.2x. 3-second reveal.","",
  "**🎡 Roulette — `$roulette <amount|half|all> <red/black/green/0-36>`**","Red/Black = 2x, Green = 14x, exact number = 30x. 3-second reveal.","",
  "**🎡 Wheel — `$wheel <amount|half|all>`**","0x, 1.2x, 1.5x, 2x, 5x or 10x.","",
  "**🚀 Crash — `$crash <amount|half|all>`**","Cash out before the multiplier crashes.","",
  "**🃏 Texas Hold'em — `$texas <amount>`**","1v1 poker game with secret DM hands, check, call and fold actions.","",
  "**☀️ Summer — `$summer`**","One free spin every 24 hours: 1.75M / 25M / 65M / 100M JACKPOT.","",
  `_Minimum bet: ${money(MIN_BET)} ${db.currency}. ${amountHelp()}`
].join("\n"),COLOR_INFO,"📖 Casino Bot — Rules");}

/* ============================= LOGIN ========================== */
if(!process.env.DISCORD_TOKEN) console.error("❌ DISCORD_TOKEN is missing.");
else client.login(process.env.DISCORD_TOKEN).catch(e=>console.error("❌ Discord login failed:",e));