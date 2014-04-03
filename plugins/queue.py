import json

from bot.events import Callback, command


class Queue(Callback):
    QFILE = "queues.json"

    def __init__(self, server):
        self.qfile = server.get_config_dir(self.QFILE)
        try:
            with open(self.qfile) as f:
                self.queues = json.load(f)
        except:
            self.queues = {}
        super().__init__(server)

    @command("list")
    def list(self, server, message):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        if not queue:
            yield "06│ Your queue is empty. "
            return
        for i, item in enumerate(queue):
            yield "06│ %d │ %s" % (i+1, item)
            if i > 2 and message.prefix != "!":
                yield "06│ %d of %d items displayed." % (i+1, len(queue))
                return

    @command("queue", r"(.+)")
    def queue(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        queue.append(item)
        self.save()
        return "06│ Added item %d: %s" % (len(queue), item)

    @command("pop", r"(\d*)")
    def pop(self, server, message, number):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        try:
            if not number: number = 1
            item = queue.pop(int(number) - 1)
        except IndexError:
            return "06│ No such item."
        else:
            self.save()
            return "06│ Popped item %s: %s" % (number, item)

    @command("peek")
    def peek(self, server, message):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        if not queue:
            return "06│ Your queue is empty. "
        return "06│ %s" % queue[0]
        
    @command("next", r"(.+)")
    def promote(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        try:
            if item.isdigit():
                item = queue[int(item) - 1]
            elif item in queue:
                queue.remove(item)
            queue.insert(0, item)
        except IndexError:
            return "06│ No such item. "
        else:
            return "06│ Promoted '%s'" % item
            


    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.queues, f)


__initialise__ = Queue