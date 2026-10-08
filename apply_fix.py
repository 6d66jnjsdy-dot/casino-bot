# =====================================================================
#  bot_fixes.py  -  כל השינויים לקוד השני (הגרסה עם heist + lottery)
#  כל בלוק מסומן: איפה למחוק ואיפה להדביק
# =====================================================================


# ---------------------------------------------------------------------
# 1) שקט מוחלט כשאין ריפליי פינג ON
#    ב-on_command_error: מצא את השורות
#        if isinstance(err, ReplyPingOff):
#            return await reply(ctx, "Turn the reply ping **ON** ...", RED)
#    והחלף ב:
# ---------------------------------------------------------------------
    if isinstance(err, ReplyPingOff):
        return                      # reply ping is OFF: the bot does not answer at all


# ---------------------------------------------------------------------
# 2) בלאקג'ק - קלפים כמו בתמונות
#    א. מחק לגמרי את הפונקציה _face_layer
#    ב. מחק את get_card הישנה (עם @lru_cache מעליה) ואת הבלוק:
#         try:
#             from cards_art import get_card ...
#         except ...
#       (get_back נשארת!)
#    ג. הדבק במקומם את get_card החדשה:
# ---------------------------------------------------------------------
@lru_cache(maxsize=None)
def get_card(card):
    """Simple card: white, big rank letter in the middle, small suit in the top-left and bottom-right corners."""
    r, s = card
    K = _CK
    W, H = SW * K, SH * K
    col = SUIT_COLOR[s]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=10 * K, fill=(255, 255, 255, 255),
                        outline=(120, 120, 128, 255), width=2 * K)
    size = int(H * (.40 if len(r) == 2 else .56))
    d.text((W / 2, H * .52), r, font=get_font(size), fill=col, anchor="mm")
    draw_suit(d, s, .19 * W, .11 * H, .07 * H)
    draw_suit(d, s, .81 * W, .89 * H, .07 * H, flip=True)
    return im.resize((SW, SH), Image.LANCZOS)


# ---------------------------------------------------------------------
# 3) setup_card_emojis - שלוש שורות לשנות (כדי שייווצרו אימוג'ים חדשים והישנים יימחקו)
#    א. השורה:  if e.name.startswith(("c_", "k_", "d_")):
#       ->      if e.name.startswith(("c_", "k_", "d_", "p_")):
#    ב. "p_back"          ->  "q_back"
#    ג. f"p_{r}{SUIT_LETTER[s]}"  ->  f"q_{r}{SUIT_LETTER[s]}"
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# 4) גודל הקלפים + פסיקים בין הקלפים
#    מחק את שתי השורות הישנות של CARD_HEADER ו-cards_text והדבק:
# ---------------------------------------------------------------------
CARD_HEADER = ""      # small inline cards, exactly like the screenshots

def cards_text(cards):
    return ", ".join(card_text(c) for c in cards)


# ---------------------------------------------------------------------
# 5) BlackjackView.render - החלף את כל הפונקציה:
# ---------------------------------------------------------------------
    def render(self):
        """Text-only embed (no image): instant to build and to send."""
        c, color, head = cur(), YELLOW, None
        if self.done:
            color, head = ((GREEN, f"You Won! +{fmt(self.net)} {c}") if self.net > 0 else
                           (RED, f"You Lost! -{fmt(-self.net)} {c}") if self.net < 0 else
                           (YELLOW, f"Push! +0 {c}"))
        lines = ["🃏 **Blackjack** 🃏" + "\u2800" * BJ_WIDTH, ""] + ([f"**{head}**", ""] if head else [])
        multi = len(self.hands) > 1
        for i, h in enumerate(self.hands):
            mark = " ◀" if multi and not self.done and i == self.active else ""
            lines.append(f"**Your Hand{f' {i + 1}' if multi else ''}**{mark}")
            lines.append(cards_text(h["cards"]))
            lines += ["", f"Value: **{hand_value(h['cards'])}**"]
        if self.done:
            dealer_cards, dealer_val = cards_text(self.dealer), hand_value(self.dealer)
        else:
            dealer_cards, dealer_val = f"{card_text(self.dealer[0])}, {back_text()}", card_value(self.dealer[0][0])
        lines += ["**Dealer**", dealer_cards, "", f"Value: **{dealer_val}**"]
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        return e


# ---------------------------------------------------------------------
# 6) פוקר 5-Card Draw
#    הדבק את כל הבלוק הזה מיד אחרי פקודת $hl (לפני "# ===== HEIST").
#    בנוסף:
#      א. ב-MULTI_GAMES הוסף "poker"
#      ב. ב-GAME_NAMES הוסף  "poker": "5-Card Draw Poker",
#      ג. ב-INFO_SECTIONS תחת CARDS AND LUCK הוסף:
#         ("$poker <bet>", "5-card draw poker"),
# ---------------------------------------------------------------------
# ================= 5-CARD DRAW POKER ($poker) =================
POKER_TITLE = "5-Card Draw Poker"
POKER_DRAWS = 2                  # how many times the player may swap cards
POKER_NERF = 0.05                # chance that a winning hand is re-rolled against a new dealer hand (house edge)
POKER_SUIT_BTN = {"♣": "♣️", "♠": "♠️", "♥": "❤️", "♦": "♦️"}

def poker_val(rank):
    return {"A": 14, "K": 13, "Q": 12, "J": 11}.get(rank) or int(rank)

def poker_rank(cards):
    """(category, tie-break list). 0 high card, 1 pair, 2 two pair, 3 trips, 4 straight, 5 flush,
    6 full house, 7 quads, 8 straight flush, 9 royal flush."""
    vals = sorted((poker_val(r) for r, _ in cards), reverse=True)
    flush = len({s for _, s in cards}) == 1
    uniq = sorted(set(vals), reverse=True)
    wheel = uniq == [14, 5, 4, 3, 2]
    straight = len(uniq) == 5 and (uniq[0] - uniq[4] == 4 or wheel)
    top = 5 if wheel else vals[0]
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape, tb = [c for _, c in groups], [v for v, _ in groups]
    if straight and flush:
        return (9 if top == 14 else 8, [top])
    if shape[0] == 4:
        return (7, tb)
    if shape == [3, 2]:
        return (6, tb)
    if flush:
        return (5, vals)
    if straight:
        return (4, [top])
    if shape[0] == 3:
        return (3, tb)
    if shape[:2] == [2, 2]:
        return (2, tb)
    if shape[0] == 2:
        return (1, tb)
    return (0, vals)

def poker_keep(hand):
    """The dealer's strategy: which cards to keep before drawing."""
    cat, _ = poker_rank(hand)
    if cat >= 4:
        return list(hand)
    vals = [poker_val(r) for r, _ in hand]
    cnt = {v: vals.count(v) for v in vals}
    if cat >= 1:
        return [c for c in hand if cnt[poker_val(c[0])] >= 2]
    for s in {s for _, s in hand}:
        same = [c for c in hand if c[1] == s]
        if len(same) == 4:
            return same
    for i in range(5):
        rest = hand[:i] + hand[i + 1:]
        v = sorted(poker_val(r) for r, _ in rest)
        if len(set(v)) == 4 and v[3] - v[0] == 3:
            return rest
    return sorted(hand, key=lambda c: poker_val(c[0]), reverse=True)[:2]

class PokerView(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.token = user, bet, token
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        self.hand = [self.deck.pop() for _ in range(5)]
        self.dealer = []
        self.draws, self.selected = POKER_DRAWS, set()
        self.done, self.net, self.message = False, 0, None
        DB["poker_log"] = DB.get("poker_log", 3000) + 1
        self.log_id = DB["poker_log"]
        save()
        self.build()

    def build(self):
        self.clear_items()
        for i, (r, s) in enumerate(self.hand):
            b = discord.ui.Button(label=r, emoji=POKER_SUIT_BTN[s], row=0, disabled=self.done,
                                  style=discord.ButtonStyle.success if i in self.selected else discord.ButtonStyle.secondary)
            b.callback = self.toggle(i)
            self.add_item(b)
        draw = discord.ui.Button(label="Draw", style=discord.ButtonStyle.primary, row=1, disabled=self.done or self.draws <= 0)
        draw.callback = self.do_draw
        fin = discord.ui.Button(label="Finish", style=discord.ButtonStyle.danger, row=1, disabled=self.done)
        fin.callback = self.do_finish
        self.add_item(draw)
        self.add_item(fin)

    def toggle(self, i):
        async def cb(interaction):
            if self.done:
                return await interaction.response.defer()
            self.selected.symmetric_difference_update({i})
            self.build()
            await interaction.response.edit_message(embed=self.embed(), view=self)
        return cb

    async def do_draw(self, interaction):
        if self.done:
            return await interaction.response.defer()
        if not self.selected:
            return await interaction.response.send_message("Click on the cards you want to swap first.", ephemeral=True)
        for i in self.selected:
            self.hand[i] = self.deck.pop()
        self.draws -= 1
        self.selected.clear()
        if self.draws <= 0:
            self.settle()
            self.stop()
        self.build()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def do_finish(self, interaction):
        if self.done:
            return await interaction.response.defer()
        self.settle()
        self.stop()
        self.build()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    def make_dealer(self):
        deck = self.deck[:]
        random.shuffle(deck)
        hand = [deck.pop() for _ in range(5)]
        for _ in range(POKER_DRAWS):
            keep = poker_keep(hand)
            hand = keep + [deck.pop() for _ in range(5 - len(keep))]
        return hand

    def player_wins(self, dealer):
        return poker_rank(self.hand) > poker_rank(dealer)     # identical hands go to the dealer: there are no ties

    def settle(self):
        self.done = True
        self.selected.clear()
        dealer = self.make_dealer()
        if self.player_wins(dealer) and random.random() < POKER_NERF:
            for _ in range(5):
                d2 = self.make_dealer()
                if not self.player_wins(d2):
                    dealer = d2
                    break
        for _ in range(luck_attempts(self.user.id) - 1):
            if self.player_wins(dealer):
                break
            dealer = self.make_dealer()
        self.dealer = dealer
        returned = self.bet * 2 if self.player_wins(dealer) else 0
        returned += multi_extra("poker", returned - self.bet)
        self.net = returned - self.bet
        pending_done(self.token)
        user_data(self.user.id)["cash"] += returned
        save()
        log_game(self.user, "poker", self.bet, self.net)
        BUSY.discard(self.user.id)

    def embed(self):
        c = cur()
        mine = " ".join(card_text(x) for x in self.hand)
        if not self.done:
            color = BLUE
            desc = (f"**{POKER_TITLE}**\n\nClick on cards to swap (max {POKER_DRAWS} times). Draws left: {self.draws}\n\n"
                    f"**Your Hand**\n{mine}")
        else:
            color = GREEN if self.net > 0 else RED
            head = f"You Won! +{fmt(self.net)} {c}" if self.net > 0 else f"You Lost! -{fmt(-self.net)} {c}"
            theirs = " ".join(card_text(x) for x in self.dealer)
            desc = f"**{POKER_TITLE}**\n\n{head}\n\n**Your Hand**\n{mine}\n\n**Dealer Hand**\n{theirs}"
        e = discord.Embed(description=desc, color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        e.set_footer(text=f"Poker Log: {self.log_id}")
        return e

    async def on_timeout(self):
        if self.done:
            return
        self.settle()
        self.build()
        if self.message:
            try:
                await self.message.edit(embed=self.embed(), view=self)
            except Exception:
                pass

@bot.command(name="poker", aliases=["pk"], usage="poker <amount | half | all>")
async def poker(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "poker <amount | half | all>", track=True)
    if not bet:
        return
    view = PokerView(ctx.author, bet, str(ctx.message.id))
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise
