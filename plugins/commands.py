import random
import difflib

from bot.events import Callback, command


class CommandIndex(Callback):
    def __init__(self, server):
        super().__init__(server)
        self._index = None
        self._callbacks = None
        self.server = server

    @property
    def index(self):
        if self._index is None:
            self._build_index()
        return self._index

    @property
    def callbacks(self):
        if self._callbacks is None:
            self._build_index()
        return self._callbacks
    
    def _build_index(self):
        self._index = {}
        self._callbacks = []
        handlers = self.server.callbacks['privmsg']
        for handler in handlers:
            cb = handler.funct
            metadata = {
                'module': handler.module,
                'path': handler.name,
                'description': self.parse_description(cb.__doc__)
            }
            if hasattr(handler.funct, 'triggers'):
                metadata.update({
                    'name': cb.triggers[0].lower(),
                    'aliases': cb.triggers
                })
                for trigger in cb.triggers:
                    self._index[trigger] = metadata
            self._callbacks.append(metadata)
            

    def parse_description(self, text: str):
        return text.strip().split("\n")[0] if text else None
    
    @command("help", "(.*)")
    def help(self, server, msg, cmd):
        """
        Print information about Karkat.
        """
        if not cmd or server.eq(cmd, server.nick):
            return "12│ 🛈 │ Type \x0312.command \x1dname\x0f for information about a command, or visit the docs at http://tetrapus.github.io/Karkat/docs.html. For any inquiries, message the developer at \x1djoey@tetrap.us\x0f."
        elif cmd.lower() in self.index:
            return "12│ 🛈 │ Type \x0312.command \x02%s\x0f for information about this command, or visit the docs at http://tetrapus.github.io/Karkat/docs.html. For any inquiries, message the developer at \x1djoey@tetrap.us\x0f." % cmd

    @command("command", "(.*)")
    def command_info(self, server, msg, cmd):
        if not cmd:
            meta = random.choice([i for i in self.callbacks if i['description']])
        elif cmd.lower() in self.index:
            meta = self.index[cmd.lower()]
        else:
            suggestion = difflib.get_close_matches(cmd.lower(), self.index.keys(), 1, 0)
            return "12│ 🛈 │ I don't have information about that command. Perhaps you meant \x1d%s\x0f?" % suggestion[0]
        return "12│ %(name)s 12│ %(description)s" % meta

__initialise__ = CommandIndex