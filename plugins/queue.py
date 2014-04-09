import json
import shlex

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

    @command("list", r"(.*)")
    def list(self, server, message, query):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        if not queue:
            yield "06│ Your queue is empty. "
            return

        q = enumerate(queue)
        
        if query:
            query = shlex.split(query.lower())

            q = [i for i in queue if all(k.lower() in i[1].lower().split() for k in query)]

        if not q:
            yield "06│ No matching items."
            return

        for i, item in q:
            yield "06│ %d │ %s" % (i+1, item)
            if i > 2 and message.prefix != "!":
                yield "06│ %d of %d items displayed." % (i+1, len(q))
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
            if item in queue:
                queue.remove(item)
            queue.insert(0, item)
        except IndexError:
            return "06│ No such item. "
        else:
            return "06│ Promoted '%s'" % item
            
    @command("tag", r"(#\S+)\s+(.+)")
    def tag(self, server, message, tag, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        try:
            if item.isdigit():
                item = queue[int(item) - 1]
            else:
                queue.index(item)
        except:
            return "06│ No such item."
        queue[index] = queue[index] + " " + tag
        self.save()
        return "06│ Added tag."

    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.queues, f)


__initialise__ = Queue