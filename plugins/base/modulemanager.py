import imp

from irc import Callback
from text import namedtable
from threads import loadplugin

cb = Callback()


class ModManager(object):
    def __init__(self, name, bot, stream):
        self.bot = bot
        self.stream = stream
        self.name = name
        cb.initialise(name, bot, stream)
        bot.register("privmsg", self.list_modules)
        bot.register("privmsg", self.unregister_modules)
        bot.register("privmsg", self.reload_modules)
        bot.register("privmsg", self.load_modules)

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