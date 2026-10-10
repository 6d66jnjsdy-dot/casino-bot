"""Entry point. Imports every module, links their names together (same behaviour as the old single file), runs the bot."""
import sys, importlib
import os; print("FILES:", sorted(os.listdir(os.path.dirname(os.path.abspath(__file__)))))
MODULES = ['core', 'game_mines', 'game_blackjack', 'game_slots', 'game_roulette', 'game_coin_chicken', 'game_higher_lower', 'game_heist', 'game_scratch', 'economy', 'shop', 'staff', 'lottery', 'owner', 'info']
mods = [importlib.import_module(n) for n in MODULES]

# Share every top-level name between all modules, so cross references work exactly as in one file.
for m in mods:
    for other in mods:
        if other is m:
            continue
        for k, v in vars(other).items():
            if not k.startswith("__") and k not in vars(m):
                setattr(m, k, v)

import core
if __name__ == "__main__":
    core.bot.run(core.TOKEN)