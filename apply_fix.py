"""
Usage:  python apply_fix.py bot.py
Fixes (a backup of your file is saved as <file>.bak):
  1. Data wipe on restart (backup restore picked an empty/old backup and overwrote the good one)
  2. Leftover bomb tiles stay clickable after all diamonds are found (mines / S$mines / gm)
  3. A corrupt economy.json is no longer silently replaced by an empty database
"""
import sys, shutil

path = sys.argv[1] if len(sys.argv) > 1 else "bot.py"
src = open(path, encoding="utf-8").read()
shutil.copy(path, path + ".bak")

NEW_BACKUP = '''BEST_USERS = 0   # the most players ever seen in a backup (protects against saving an empty database)

async def backup_candidates(ch):
    pins = ch.pins()
    if hasattr(pins, "__aiter__"):
        async for m in pins:
            yield m
    else:
        for m in await pins:
            yield m
    async for m in ch.history(limit=1000):
        yield m

async def restore_backup():
    global backup_msg, synced, BEST_USERS
    try:
        best = None   # (players, message id, message, data)
        async for m in backup_candidates(await get_backup_channel()):
            if m.author.id != bot.user.id:
                continue
            att = next((a for a in m.attachments if a.filename == "economy.json"), None)
            if not att:
                continue
            try:
                data = json.loads(await att.read())
            except ValueError:
                continue
            n = len(data.get("users") or {})
            if best is None or (n, m.id) > (best[0], best[1]):
                best = (n, m.id, m, data)
        if best:
            n, _, m, data = best
            backup_msg = m
            BEST_USERS = n
            if n > len(DB.get("users", {})):      # restore only if the backup has MORE players than we have now
                DB.clear()
                DB.update(data)
                write_db()
                print(f"Restored {n} players from backup")
        BEST_USERS = max(BEST_USERS, len(DB.get("users", {})))
        synced = True
    except Exception as e:
        print("Backup restore failed (backups disabled to protect data). Are the owner's DMs open to the bot?", repr(e))

async def backup_now():
    global backup_msg, dirty, BEST_USERS
    if not (dirty and synced):
        return
    async with backup_lock:
        if not dirty:
            return
        dirty = False
        if len(DB.get("users", {})) < BEST_USERS * 0.5:
            print("Backup skipped: the database has far fewer players than the last backup (protecting your data)")
            return
        try:
            if backup_msg:
                try:
                    backup_msg = await backup_msg.edit(attachments=[backup_file()])
                    BEST_USERS = max(BEST_USERS, len(DB["users"]))
                    return
                except discord.NotFound:
                    backup_msg = None
            backup_msg = await (await get_backup_channel()).send("💾 Database backup - do not delete this message", file=backup_file())
            BEST_USERS = max(BEST_USERS, len(DB["users"]))
            try:
                await backup_msg.pin()
            except Exception:
                pass
        except Exception as e:
            dirty = True
            print("Backup failed:", repr(e))

'''

a = src.index("async def backup_candidates(ch):")
b = src.index("@tasks.loop(seconds=10)\nasync def backup_loop")
src = src[:a] + NEW_BACKUP + src[b:]

OLD_LOAD = '''def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except Exception:
        return {"currency": "💸", "users": {}}
'''
NEW_LOAD = '''def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"currency": "💸", "users": {}}
    except Exception as e:
        print("economy.json is unreadable, keeping a copy as economy.corrupt.json:", repr(e))
        try:
            shutil.copy(DB_FILE, DB_FILE.replace(".json", ".corrupt.json"))
        except Exception:
            pass
        return {"currency": "💸", "users": {}}
'''
assert OLD_LOAD in src, "load() not found"
src = src.replace(OLD_LOAD, NEW_LOAD)
if "import shutil" not in src:
    src = src.replace("import discord, random,", "import shutil, discord, random,", 1)

LOCK = '''    def lock_leftovers(self):
        # every safe tile found: lock the remaining (bomb) tiles, same colour, nothing revealed
        if all(k == "bomb" or i in self.revealed for i, k in enumerate(self.board)):
            for i in range(len(self.board)):
                if i not in self.revealed:
                    self.tiles[i].disabled = True

'''
anchor = "    async def edit_ui(self, interaction, **kw):"
assert src.count(anchor) == 1, "edit_ui anchor not found"
src = src.replace(anchor, LOCK + anchor)

OLD_CLICK = "        self.after(kind)\n        await self.push(interaction)\n"
assert src.count(OLD_CLICK) == 1, "click anchor not found"
src = src.replace(OLD_CLICK, "        self.after(kind)\n        self.lock_leftovers()\n        await self.push(interaction)\n")

open(path, "w", encoding="utf-8").write(src)
print("Done. Backup of the old file:", path + ".bak")
