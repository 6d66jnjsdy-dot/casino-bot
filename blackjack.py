import random
money = 250
while money > 0:
   print(f"\nיש לך ${money}")
   bet = int(input("כמה להמק "))
  if bet <= 0 or bet > money
     print("הימור לא חוקי ")
     continue 
deck = [
  "2" "3" "4" "5" "6" "7" "8" 9" "10" 
  "J" "Q" "K" "A"
  ] * 4
  random/shuffle(deck)
  player = [deck.pop(), deck.pop()]
  dealer = [deck.pop(), deck.pop()]

def card_value(cards):
    value = 0
    aces = 0
    for card in cards:
if card in cards:
if card in ["J", "Q", "K"]:
value += 10
elif card == "A":
value += 11
aces += 1
else:
     לא סוים
    
  
