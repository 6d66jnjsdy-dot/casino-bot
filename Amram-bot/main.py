"""Entry point: loads every module in order, shares names between them, runs the bot."""
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Order matters: a module may use names of the modules loaded before it.
MODULES = ['core', 'game_mines', 'game_blackjack', 'game_poker', 'game_slots', 'game_roulette', 'game_coin_chicken',
           'game_higher_lower', 'game_heist', 'game_scratch', 'economy', 'shop', 'staff',
           'game_lottery', 'owner', 'info']

mods = []
for name in MODULES:
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    for prev in mods:                       # give the new module everything loaded so far
        for k, v in vars(prev).items():
            if not k.startswith("__"):
                mod.__dict__.setdefault(k, v)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    mods.append(mod)

# After everything is loaded, share all names both ways (for names used only inside functions).
for m in mods:
    for other in mods:
        if other is m:
            continue
        for k, v in vars(other).items():
            if not k.startswith("__") and k not in vars(m):
                setattr(m, k, v)

if __name__ == "__main__":
    mods[0].bot.run(mods[0].TOKEN)
