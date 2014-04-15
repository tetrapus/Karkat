import json
import shlex
import re

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
            query = set(shlex.split(query.lower()))
            exclude = {i for i in query if i.startswith("-")}
            include = query - exclude
            q = [i for i in q if all(k.lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in include)]
            q = [i for i in q if not any(k[1:].lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in exclude)]

        if not q:
            yield "06│ No matching items."
            return

        count = 0
        for i, item in q:
            count += 1
            yield "06│ %d │ %s" % (i+1, re.sub("(#\S+)", r"15\1", item))
            if count > 3 and message.prefix != "!":
                yield "06│ %d of %d items displayed." % (count, len(queue))
                return


    @command("queue", r"(.+)")
    def queue(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        queue.append(item)
        self.save()
        return "06│ Added item %d: %s" % (len(queue), re.sub("(#\S+)", r"15\1", item))

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
            return "06│ Popped item %s: %s" % (number, re.sub("(#\S+)", r"15\1", item))

    @command("peek")
    def peek(self, server, message):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        if not queue:
            return "06│ Your queue is empty. "
        return "06│ %s" % re.sub("(#\S+)", r"15\1", queue[0])
        
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
            return "06│ Promoted '%s'" % (re.sub("(#\S+)", r"15\1", item))
            
    @command("tag", r"(#\S+(?:\s+#\S+)*)\s+(.+)")
    def tag(self, server, message, tag, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        try:
            if all(i.isdigit() for i in item.split()):
                items = [int(i) - 1 for i in item.split()]
            else:
                items = [queue.index(item)]
        except:
            return "06│ No such item."
        for i in items:
            queue[i] = queue[i] + " " + tag
        self.save()
        return "06│ Added tags."

    @command("untag", r"(#\S+(?:\s+#\S+)*)\s+(.+)")
    def untag(self, server, message, tags, items):
        pass

    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.queues, f)


__initialise__ = Queue