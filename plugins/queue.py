import json
import shlex
import re
import random

from bot.events import Callback, command
from util.text import strikethrough


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
        

    def find(self, queue, query=None):
        q = [(i[0] + 1, i[1]) for i in enumerate(queue)]

        if query is None:
            return q
        elif re.match(r"^\d+((,|\s)+\d+)*$", query):
            return [q[int(i)-1] for i in query.replace(",", " ").split()]
        elif re.match(r"^\d*-\d*$", query):
            start, stop = [int(i) - 1 if i else None for i in query.split('-')]
            return q[start:stop]
        else:
            exact = [i for i in q if i[1].lower() == query.lower]
            if exact:
                return exact
            else:
                query = set(shlex.split(query.lower()))
                hidden = {"hidden"} - query
                exclude = {i for i in query if i.startswith("-")} | {'-' + i for i in hidden}
                include = query - exclude
                q = [i for i in q if all(k.lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in include)]
                q = [i for i in q if not any(k[1:].lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in exclude)]

                return q


    def display(self, line):
        return "06│ %d │ %s" % (line[0], re.sub(r"(#\S+)", r"15\1", line[1]))

    def displayAll(self, lines, max=25):
        for count, i in enumerate(lines):
            if max - 1 <= count and max != len(lines):
                yield "06│ %d of %d items displayed." % (count, len(lines))
                return
            yield self.display(i)

    @command("list", r"(.*)")
    def list(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            yield "06│ Your queue is empty. "
            return

        q = self.find(queue, query)

        if not q:
            yield "06│ No matching items."
            return

        yield from self.displayAll(q, 25 if msg.prefix == '!' else 5)


    @command("choose", r"^([^\d,]*)$")
    def choose(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            return "06│ Your queue is empty. "

        q = self.find(queue, query)

        if not q:
            return "06│ No matching items."

        return self.display(random.choice(q))

    @command("queue todo append", r"(.+)")
    def queue(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        queue.append(item)
        self.save()
        return self.display((len(queue), item))

    @command("pop", r"(.*)")
    def pop(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            yield "06│ Your queue is empty. "
            return

        q = self.find(queue, query)

        if not q:
            yield "06│ No matching items."
            return

        for i in q:
            queue.pop(i[0]-1)

        yield from self.displayAll([('✓', strikethrough(i)) for i in q], 25 if msg.prefix == '!' else 5)

        self.save()

    @command("peek", r"(.*)")
    def peek(self, server, message, query):
        nick = server.lower(message.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            return "06│ Your queue is empty. "

        q = self.find(queue, query)

        if not q:
            return "06│ No matching items."

        return self.display(q[0])
        
    @command("next promote push", r"(.+)")
    def push(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            yield "06│ Your queue is empty. "
            return
        q = self.find(queue, query)

        if not q:
            queue.append(query)
            q = [(len(q)-1, query)]

        for i, item in q[::-1]:
            queue.pop(i-1)
            queue.insert(0, item)

        yield from self.displayAll([(i+1, item[1]) for i, item in enumerate(q)], 25 if msg.prefix == '!' else 5)

        self.save()
            
    @command("tag", r"(#\S+(?:\s+#\S+)*)\s+(.+)")
    def tag(self, server, msg, tag, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        if not queue:
            yield "06│ Your queue is empty. "
            return
        q = self.find(queue, query)

        if not q:
            yield "06│ No matching items."
            return

        for i, item in q:
            tags = [i for i in tag.split() if i.lower() not in item.lower()]
            queue[i-1] = item + ' ' + ' '.join(tags)

        yield from self.displayAll([(i[0], queue[i[0]-1]) for i in q], 25 if msg.prefix == '!' else 5)

        self.save()

    @command("untag", r"(#\S+(?:\s+#\S+)*)(?:\s+(.+))?")
    def untag(self, server, msg, tags, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        tags = tags.split()
        if not queue:
            yield "06│ Your queue is empty. "
            return
        q = self.find(queue, query)

        if not q:
            yield "06│ No matching items."
            return

        tagged = []

        for i, item in q:
            fixed = re.sub("( ?#(%s))" % ("|".join(re.escape(x) for x in tags)), "", queue[i], re.IGNORECASE)
            if queue[i-1] != fixed:
                queue[i-1] = fixed
                tagged.append((i, fixed))

        yield from self.displayAll(tagged, 25 if msg.prefix == '!' else 5)

        self.save()

    # TODO: Alter hidden tags
    @command("hide", r"(.+)")
    def hide(self, server, msg, query):
        yield from self.tag.funct(self, server, msg, "#hidden", query)

    # TODO: Alter hidden tags
    @command("unhide", r"(.+)")
    def unhide(self, server, msg, query):
        yield from self.untag.funct(self, server, msg, "#hidden", query)        

    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.queues, f)


__initialise__ = Queue