"""
Usage:  python apply_pay_rob_bal_only.py bot.py      (run on the ORIGINAL bot.py, not the one patched before)

Only $pay, $rob and $bal a: when the tag / reply / user ID is missing or does not resolve,
the bot says nothing and does nothing (no cooldown message either).
Every other command is untouched. Writes bot.py.bak first; if any snippet is not found, nothing changes.
"""
import re
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "bot.py"
src = open(path, encoding="utf-8").read()


def rep(old, new, n=1):
    global src
    found = src.count(old)
    if found != n:
        sys.exit(f"PATCH FAILED (expected {n} match, found {found}) for:\n{old[:160]}")
    src = src.replace(old, new)


def rx(pattern, repl, n=1):
    global src
    src, done = re.subn(pattern, repl, src)
    if done != n:
        sys.exit(f"PATCH FAILED (expected {n} match, found {done}) for regex:\n{pattern[:160]}")


rep('''class ReplyPingOff(commands.CommandError):
    pass
''', '''class ReplyPingOff(commands.CommandError):
    pass

class SilentIgnore(commands.CheckFailure):
    """Used only by $pay, $rob, $bal: no tag / reply = no answer at all."""
''')
rep('''async def on_command_error(ctx, err):
    if isinstance(err, NotStaff):''', '''async def on_command_error(ctx, err):
    if isinstance(err, SilentIgnore):
        return
    if isinstance(err, NotStaff):''')

rep('''@bot.command(name="bal"''', '''async def resolve_silent(ctx, arg):
    """Like resolve_target, but any failure (no reply, ping off, unknown user) is completely silent."""
    try:
        member = await resolve_target(ctx, arg)
    except Exception:
        raise SilentIgnore()
    if member is None:
        raise SilentIgnore()
    return member

async def _check_target(ctx):
    """Runs before the cooldown and before the command."""
    args = ctx.view.buffer[ctx.view.index:].split()
    await resolve_silent(ctx, args[0] if args else None)
    return True

require_target = commands.check(_check_target)

@bot.command(name="bal"''')

# $bal
rx(r'        member = await resolve_target\(ctx, target\)\n        if member is None:\n            return await reply\(ctx, "Usage: `\$bal[^\n]*\n',
   '        member = await resolve_silent(ctx, target)\n')
# $pay
rep('''    member = await resolve_target(ctx, target)
    if member is None or amount is None:''', '''    member = await resolve_silent(ctx, target)
    if amount is None:''')
# $rob
rep('''    try:
        member = await resolve_target(ctx, target)
    except Exception:
        ctx.command.reset_cooldown(ctx)
        raise''', '''    try:
        member = await resolve_silent(ctx, target)
    except Exception:
        ctx.command.reset_cooldown(ctx)
        raise''')
rx(r'    if member is None:\n        ctx\.command\.reset_cooldown\(ctx\)\n        return await reply\(ctx, "Usage: `\$rob[^\n]*\n', '')

rx(r'(@bot\.command\(name="(?:pay|rob)"[^\n]*\)\n)', r'\1@require_target\n', 2)

shutil.copyfile(path, path + ".bak")
open(path, "w", encoding="utf-8").write(src)
print("OK - bot.py patched (backup: bot.py.bak)")
