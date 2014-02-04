import imp
import json
import os
import sys

from util.irc import Callback, command
from util.text import namedtable
from bot.threads import SelectiveBot


class ModManager(object):

    BLACKLIST = "blacklist.json"

    def __init__(self, server):
        server.register("privmsg", self.list_modules)
        server.register("privmsg", self.unregister_modules)
        server.register("privmsg", self.reload_modules)
        server.register("privmsg", self.load_modules)
        if isinstance(server, SelectiveBot):
            self.bfile = server.get_config_dir(self.BLACKLIST)
            try:
                server.blacklist.update(json.load(open(self.bfile, "r")))
            except:
                # File doesn't exist
                os.makedirs(server.get_config_dir(), exist_ok=True)
            self.sync(server)

            server.register("privmsg", self.enable_module)
            server.register("privmsg", self.disable_module)
            server.register("privmsg", self.list_disabled)
        else:
            print("[Module Manager] Warning: This bot architecture does not "
                  "support blacklists. Add the SelectiveBot mixin to enable "
                  "blacklist support.", file=sys.stderr)

    # Disable/Enable plugins

    def sync(self, server):
        with open(self.bfile, "w") as bf:
            bf.write(json.dumps(server.blacklist))

    @Callback.inline
    @command("disable", "([^ ]+)", private="", public=":", admin=True,
                usage="12Module Manager│ Usage: :disable <modname>")
    def disable_module(self, server, message, mod):
        blacklisted = server.blacklist.setdefault(server.lower(message.context), 
                                                  list(server.blacklist[None]))
        if mod not in blacklisted:
            blacklisted.append(mod)
            return "12Module Manager│ Module %s disabled." % mod
        else:
            return "12Module Manager│ %s is already blacklisted." % mod
        self.sync(server)

    @Callback.inline
    @command("enable", "([^ ]+)", private="", public=":", admin=True,
                usage="12Module Manager│ Usage: :enable <modname>")
    def enable_module(self, server, message, mod):
        blacklisted = server.blacklist.setdefault(server.lower(message.context), 
                                                  list(server.blacklist[None]))
        if mod in blacklisted:
            blacklisted.remove(mod)
            return "12Module Manager│ Module %s re-enabled." % mod
        else:
            return "12Module Manager│ %s is not blacklisted." % mod
        self.sync(server)

    @command("disabled")
    def list_disabled(self, server, message):
        blacklisted = server.blacklist.get(server.lower(message.context), [])
        if blacklisted:
            table = namedtable(blacklisted, size=72, header="Disabled modules ")
            for i in table:
                yield i
        else:
            yield "12Module Manager│ Blacklist is empty."

    # Module management plugins

    def remove_modules(self, bot, mod):
        removed = []
        destroyed = []
        for i in bot.callbacks:
            for cb in [x for x in bot.callbacks[i] if x.name.startswith(mod)]:
                removed.append(cb)
                bot.callbacks[i].remove(cb)
                if (hasattr(cb.funct, "__self__") 
                    and hasattr(cb.funct.__self__, "__destroy__")
                    and cb.funct.__self__ not in destroyed):
                    cb.funct.__self__.__destroy__(bot)
                    destroyed.append(cb.funct.__self__)
        return removed


    @command(["modules", "plugins"], "(.*)", 
                admin=True) # NTS: Figure out how this function signature works
    def list_modules(self, server, message, mask):
        modules = set()
        for ls in server.callbacks.values():
            modules |= {i.module.__name__ for i in ls if i.module}
        table = namedtable([i.split(".")[-1] for i in modules 
                              if i.startswith(mask)] or ["No matches."],
                           size=72,
                           header="Loaded modules ")
        for i in table:
            yield i

    @Callback.inline
    @command("unload", "(.+)", private="", public=":",
                admin=True, 
                usage="12Module Manager│ Usage: [!@]unload <module>")
    def unregister_modules(self, server, message, module):
        removed = {x.module.__name__ for x in self.remove_modules(server, module)}
        if not removed:
            yield "05Module Manager│ Module not found."
        elif len(removed) == 1:
            yield "12Module Manager│ %s unloaded." % (list(removed)[0])
        else:
            table = namedtable(removed,
                               size=72,
                               header="Unregistered modules ")
            for i in table:
                yield i

    @Callback.inline
    @command("reload", "(.+)", private="", public=":",
                admin=True, 
                usage="12Module Manager│ Usage: [!@]reload <module>",
                error="12Module Manager│ Module failed to load.")
    def reload_modules(self, server, message, module):
        # Find and remove all callbacks
        removed = self.remove_modules(server, module)
        reloaded = []

        if removed:
            for i in removed:
                mod = i.module
                if mod.__name__ in reloaded: 
                    continue
                if "__destroy__" in dir(mod):
                    mod.__destroy__()
                imp.reload(mod)
                server.loadplugin(mod)
                reloaded.append(mod.__name__)
            if len(reloaded) == 1:
                yield "12Module Manager│ %s reloaded." % (reloaded[0])
            else:
                table = namedtable(reloaded,
                                   size=72,
                                   header="Reloaded modules ")
                for i in table:
                    yield i
        else:
            yield "05Module Manager│ Module not found."

    @Callback.inline
    @command("load", "(.+)", private="", public=":",
                admin=True, 
                usage="12Module Manager│ Usage: [!@]load <module>",
                error="05Module Manager│ Module failed to load.")
    def load_modules(self, server, message, module):
        path = module.split(".")
        try:
            if module in sys.modules:
                del sys.modules[module]
            module = __import__(path[0])
            for i in path[1:]:
                module = module.__dict__[i]
        except:
            return "05Module Manager│ Module failed to load."
        else:
            server.loadplugin(module)
            return "12Module Manager│ %s loaded." % module.__name__


__initialise__ = ModManager
