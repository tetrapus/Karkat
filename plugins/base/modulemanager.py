import inspect
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

    @cb.command("modules", "(.*)", admin=True) # NTS: Figure out how this function signature works
    def list_modules(self, message, filter):
        modules = set()
        for key, ls in list(self.bot.callbacks.items()) + list(self.bot.inline_cbs.items()):
            modules |= {inspect.getmodule(i).__name__ for i in ls}
        table = namedtable([i for i in modules if i.startswith(filter)] or ["No matches."],
                           size=72,
                           header="Loaded modules ")
        for i in table:
            yield i

    @staticmethod
    def fname(funct):
        return inspect.getmodule(funct).__name__ + "." + funct.__name__

    @cb.command("unregister", "(.+)", admin=True, help="12Module System⎟ Usage: [!@]unregister <modulename>")
    def unregister_modules(self, message, module):
        removed = []
        for i in self.bot.callbacks:
            for cb in [x for x in self.bot.callbacks[i] if fname(i).startswith(module)]:
                removed.append(fname(cb))
                self.bot.callbacks[i].remove(cb)
        for i in self.bot.inline_cbs:
            for cb in [x for x in self.bot.inline_cbs[i] if fname(i).startswith(module)]:
                removed.append(fname(cb))
                self.bot.inline_cbs[i].remove(cb)
        table = namedtable(removed or ["No matches."],
                           size=72,
                           header="Unregistered modules ")
        for i in table:
            yield i

    @cb.command("reload", "(.+)", admin=True, help="12Module System⎟ Usage: [!@]reload <module>")
    def reload_modules(self, message, module):
        # Find and remove all callbacks
        removed = []
        for i in self.bot.callbacks:
            for cb in [x for x in self.bot.callbacks[i] if inspect.getmodule(x).__name__ == module]:
                removed.append(cb)
                self.bot.callbacks[i].remove(cb)
        for i in self.bot.inline_cbs:
            for cb in [x for x in self.bot.inline_cbs[i] if inspect.getmodule(x).__name__ == module]:
                removed.append(cb)
                self.bot.inline_cbs[i].remove(cb)

        if removed:
            mod = inspect.getmodule(removed[0])
            if "__destroy__" in dir(mod):
                module.__destroy__()
            imp.reload(mod)
            loadplugin(mod, self.name, self.bot, self.stream)
            return "12Module System⎟ Reloaded %s." % mod.__name__
        else:
            return "12Module System⎟ Module not found."


    @cb.command("load", "(.+)", admin=True, help="12Module System⎟ Usage: [!@]load <module>")
    def load_modules(self, message, module):
        try:
            module = __import__(module)
        except ImportError:
            return "12Module System⎟ Module failed to load."
        loadplugin(module, self.name, self.bot, self.stream)
        return "12Module System⎟ Loaded %s." % module.__name__


__initialise__ = ModManager