import imp
import json
import sys
import os

from irc import Callback
from text import namedtable
from threads import loadplugin, SelectiveBot

cb = Callback()


class ModManager(object):

    BLACKLIST = "blacklist.json"

    def __init__(self, name, bot, stream):
        self.bot = bot
        self.stream = stream
        self.name = name
        cb.initialise(name, bot, stream)
        bot.register("privmsg", self.list_modules)
        bot.register("privmsg", self.unregister_modules)
        bot.register("privmsg", self.reload_modules)
        bot.register("privmsg", self.load_modules)
        if isinstance(bot, SelectiveBot):
            self.bfile = bot.get_config_dir(self.BLACKLIST)
            try:
                bot.blacklist.update(json.load(open(self.bfile, "r")))
            except:
                # File doesn't exist
                os.makedirs(bot.get_config_dir(), exist_ok=True)
            self.sync()

            bot.register("privmsg", self.enable_module)
            bot.register("privmsg", self.disable_module)
            bot.register("privmsg", self.list_disabled)
        else:
            print("[Module Manager] Warning: This bot architecture does not support blacklists. Add the SelectiveBot mixin to enable blacklist support.", file=sys.stderr)

    # Disable/Enable plugins

    def sync(self):
        with open(self.bot.get_config_dir(self.BLACKLIST), "w") as f:
            f.write(json.dumps(self.bot.blacklist))

    @cb.inline
    @cb.command("disable", "([^ ]+)", private="", public=":", 
                usage="12Module Manager⎟ Usage: :disable <modname>")
    def disable_module(self, message, module):
        blacklisted = self.bot.blacklist.setdefault(message.context.lower(), [])
        if module not in blacklisted:
            blacklisted.append(module)
            return "12Module Manager⎟ Module %s disabled." % module
        else:
            return "12Module Manager⎟ %s is already blacklisted." % module
        self.sync()

    @cb.inline
    @cb.command("enable", "([^ ]+)", private="", public=":", 
                usage="12Module Manager⎟ Usage: :enable <modname>")
    def enable_module(self, message, module):
        blacklisted = self.bot.blacklist.setdefault(message.context.lower(), [])
        if module in blacklisted:
            blacklisted.remove(module)
            return "12Module Manager⎟ Module %s re-enabled." % module
        else:
            return "12Module Manager⎟ %s is not blacklisted." % module
        self.sync()

    @cb.command("disabled")
    def list_disabled(self, message):
        blacklisted = self.bot.blacklist.get(message.context.lower(), [])
        if blacklisted:
            table = namedtable(blacklisted, size=72, header="Disabled modules ")
            for i in table:
                yield
        else:
            yield "12Module Manager⎟ Blacklist is empty."

    # Module management plugins

    def remove_modules(self, module):
        removed = []
        for i in self.bot.callbacks:
            for cb in [x for x in self.bot.callbacks[i] if x.name.startswith(module)]:
                removed.append(cb)
                self.bot.callbacks[i].remove(cb)
        return removed


    @cb.command(["modules", "plugins"], "(.*)", 
                admin=True) # NTS: Figure out how this function signature works
    def list_modules(self, message, filter):
        modules = set()
        for key, ls in list(self.bot.callbacks.items()):
            modules |= {i.module.__name__ for i in ls}
        table = namedtable([i for i in modules if i.startswith(filter)] or ["No matches."],
                           size=72,
                           header="Loaded modules ")
        for i in table:
            yield i

    @cb.inline
    @cb.command("unload", "(.+)", 
                admin=True, 
                usage="12Module Manager⎟ Usage: [!@]unload <module>")
    def unregister_modules(self, message, module):
        removed = {x.module for x in self.remove_modules(module)}
        if not removed:
            yield "05Module Manager⎟ Module not found."
        elif len(removed) == 1:
            yield "12Module Manager⎟ %s unloaded." % (list(removed)[0])
        else:
            table = namedtable(removed,
                               size=72,
                               header="Unregistered modules ")
            for i in table:
                yield i

    @cb.inline
    @cb.command("reload", "(.+)", 
                admin=True, 
                usage="12Module Manager⎟ Usage: [!@]reload <module>",
                error="12Module Manager⎟ Module failed to load.")
    def reload_modules(self, message, module):
        # Find and remove all callbacks
        removed = self.remove_modules(module)
        reloaded = []

        if removed:
            for i in removed:
                mod = i.module
                if mod.__name__ in reloaded: 
                    continue
                if "__destroy__" in dir(mod):
                    mod.__destroy__()
                imp.reload(mod)
                loadplugin(mod, self.name, self.bot, self.stream)
                reloaded.append(mod.__name__)
            if len(reloaded) == 1:
                yield "12Module Manager⎟ %s reloaded." % (list(reloaded)[0])
            else:
                table = namedtable(reloaded,
                                   size=72,
                                   header="Reloaded modules ")
                for i in table:
                    yield i
        else:
            yield "05Module Manager⎟ Module not found."

    @cb.inline
    @cb.command("load", "(.+)", 
                admin=True, 
                usage="12Module Manager⎟ Usage: [!@]load <module>",
                error="12Module Manager⎟ Module failed to load.")
    def load_modules(self, message, module):
        path = module.split(".")
        try:
            module = __import__(path[0])
            for i in path[1:]:
                module = module.__dict__[i]
        except:
            return "05Module Manager⎟ Module failed to load."
        else:
            loadplugin(module, self.name, self.bot, self.stream)
            return "12Module Manager⎟ %s loaded." % module.__name__


__initialise__ = ModManager