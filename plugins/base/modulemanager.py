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
            print("[Module Manager] Warning: This bot architecture does not support blacklists. Add the SelectiveBot mixin to enable blacklist support.", file=sys.stderr)

    # Disable/Enable plugins

    def sync(self, server):
        with open(self.bfile, "w") as f:
            f.write(json.dumps(server.blacklist))

    @Callback.inline
    @command("disable", "([^ ]+)", private="", public=":", admin=True,
                usage="12Module Manager│ Usage: :disable <modname>")
    def disable_module(self, server, message, module):
        blacklisted = server.blacklist.setdefault(server.lower(message.context), server.blacklist[None])
        if module not in blacklisted:
            blacklisted.append(module)
            return "12Module Manager│ Module %s disabled." % module
        else:
            return "12Module Manager│ %s is already blacklisted." % module
        self.sync(server)

    @Callback.inline
    @command("enable", "([^ ]+)", private="", public=":", admin=True,
                usage="12Module Manager│ Usage: :enable <modname>")
    def enable_module(self, server, message, module):
        blacklisted = server.blacklist.setdefault(server.lower(message.context), server.blacklist[None])
        if module in blacklisted:
            blacklisted.remove(module)
            return "12Module Manager│ Module %s re-enabled." % module
        else:
            return "12Module Manager│ %s is not blacklisted." % module
        self.sync(server)

    @command("disabled")
    def list_disabled(self, server, message):
        blacklisted = server.blacklist.get(server.lower(message.context), [])
        if blacklisted:
            table = namedtable(blacklisted, size=72, header="Disabled modules ")
            for i in table:
                yield
        else:
            yield "12Module Manager│ Blacklist is empty."

    # Module management plugins

    def remove_modules(self, server, module):
        removed = []
        for i in server.callbacks:
            for cb in [x for x in server.callbacks[i] if x.name.startswith(module)]:
                removed.append(cb)
                server.callbacks[i].remove(cb)
        return removed


    @command(["modules", "plugins"], "(.*)", 
                admin=True) # NTS: Figure out how this function signature works
    def list_modules(self, server, message, filter):
        modules = set()
        for key, ls in list(server.callbacks.items()):
            modules |= {i.module.__name__ for i in ls}
        table = namedtable([i for i in modules if i.startswith(filter)] or ["No matches."],
                           size=72,
                           header="Loaded modules ")
        for i in table:
            yield i

    @Callback.inline
    @command("unload", "(.+)", 
                admin=True, 
                usage="12Module Manager│ Usage: [!@]unload <module>")
    def unregister_modules(self, server, message, module):
        removed = {x.module for x in self.remove_modules(server, module)}
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
    @command("reload", "(.+)", 
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
                yield "12Module Manager│ %s reloaded." % (list(reloaded)[0])
            else:
                table = namedtable(reloaded,
                                   size=72,
                                   header="Reloaded modules ")
                for i in table:
                    yield i
        else:
            yield "05Module Manager│ Module not found."

    @Callback.inline
    @command("load", "(.+)", 
                admin=True, 
                usage="12Module Manager│ Usage: [!@]load <module>",
                error="12Module Manager│ Module failed to load.")
    def load_modules(self, server, message, module):
        path = module.split(".")
        try:
            module = __import__(path[0])
            for i in path[1:]:
                module = module.__dict__[i]
        except:
            return "05Module Manager│ Module failed to load."
        else:
            server.loadplugin(module)
            return "12Module Manager│ %s loaded." % module.__name__


__initialise__ = ModManager