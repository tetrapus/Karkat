import json
import shlex
import re
import random
import math
import requests

from bot.events import Callback, command
from util.text import strikethrough, smallcaps


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
            return sorted([q[int(i)-1] for i in set(query.replace(",", " ").split())])
        elif re.match(r"^\d*-\d*$", query):
            start, stop = [int(i) if i else None for i in query.split('-')]
            if start: start -= 1
            return q[start:stop]
        else:
            exact = [i for i in q if i[1].lower() == query.lower()]
            if exact:
                return exact
            else:
                try:
                    query = set(shlex.split(query.lower()))
                except:
                    query = set(query.lower().split())
                hidden = {"hidden", "done"} - query
                exclude = {i for i in query if i.startswith("-")} | {'-' + i for i in hidden}
                include = query - exclude
                q = [i for i in q if all(k.lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in include)]
                q = [i for i in q if not any(k[1:].lstrip("#") in [j.lstrip("#") for j in i[1].lower().split()] for k in exclude)]

                return q


    def display(self, num, line):
        points = re.split(r"\s*(\[(?:\d+/)?\d+\])\s*", line, maxsplit=1)
        vis = "│"
        if len(points) == 3:
            line = "%s %s" % (points[0], points[-1])
            points = [float(x) for x in points[1][1:-1].split("/")]
            align = math.ceil(points[-1]/5) * 5
            total = points[-1]
            if len(points) > 1:
                done = points[0]
            else:
                done = 0
            vis = '┝' + "━" * math.ceil(total - done) + '15' + "─" * math.ceil(done) + " " * (align - math.ceil(total))
        return "06│ %s %s %s" % (num, vis, re.sub(r"#(\S+)", lambda x: r"15%s" % smallcaps(x.group(1)), line))

    def displayAll(self, lines, max=25):
        for count, i in enumerate(lines):
            if max - 1 <= count and max != len(lines):
                yield "06│ %d of %d items displayed." % (count, len(lines))
                return
            yield self.display(*i)

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

        return self.display(*random.choice(q))

    @command("queue todo", r"(.+)")
    def queue(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        queue.append(item)
        self.save()
        return self.display(len(queue), item)

    @command("edit replace", r"(\d+)\s+(.+)")
    def edit(self, server, message, index, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        index = int(index)
        if index > len(queue):
            queue.append("")
            index = len(queue)
        queue[index - 1] = item
        self.save()
        return self.display(index, item)

    @command("push prepend", r"(.+)")
    def push(self, server, message, item):
        nick = message.address.nick
        queue = self.queues.setdefault(server.lower(nick), [])
        queue.insert(0, item)
        self.save()
        return self.display(1, item)

    @command("pop", r"(.*)")
    def pop(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])

        if not queue:
            yield "06│ Your queue is empty. "
            return

        if not query: 
            query = "1"

        q = self.find(queue, query)

        if not q:
            yield "06│ No matching items."
            return

        for i in sorted(q, key=lambda x:-x[0]):
            queue.pop(i[0]-1)

        yield from self.displayAll([('✓' if len(q) == 1 else i[0], strikethrough(i[1])) for i in q], 25 if msg.prefix == '!' else 5)

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

        return self.display(*q[0])
        
    @command("next promote", r"(.+)")
    def promote(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])

        q = self.find(queue, query)

        if not q:
            queue.append(query)
            q = [(len(queue), query)]

        q.reverse()

        for i, item in q:
            queue.pop(i-1)
        for i, item in q:
            queue.insert(0, item)

        q.reverse()

        yield from self.displayAll([(i+1, item[1]) for i, item in enumerate(q)], 25 if msg.prefix == '!' else 5)

        self.save()
            
    @command("last demote", r"(.+)")
    def demote(self, server, msg, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])

        q = self.find(queue, query)

        if not q:
            queue.append(query)
            q = [(len(queue), query)]

        updated = []

        q.reverse()

        for i, item in q:
            queue.pop(i-1)
        q.reverse()
        for i, item in q:
            queue.append(item)
            updated.append((len(queue), item))

        yield from self.displayAll(updated, 25 if msg.prefix == '!' else 5)

        self.save()

    @command("insert", "(\d+)\s+(.+)")
    def insert(self, server, msg, index, query):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])

        q = self.find(queue, query)

        if not q:
            queue.append(query)
            q = [(len(queue), query)]

        updated = []

        index = int(index)
        if len(queue) - len(q) + 1 < index:
            index = len(queue) - len(q)
        index -= 1

        q.reverse()

        for i, item in q:
            queue.pop(i-1)
            queue.insert(index, item)
        q.reverse()
        for i, item in enumerate(q):
            updated.append((index + i+1, item[1]))

        yield from self.displayAll(updated, 25 if msg.prefix == '!' else 5)

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
            fixed = re.sub("( ?(%s))" % ("|".join(re.escape(x) for x in tags)), "", queue[i-1], re.IGNORECASE)
            if queue[i-1] != fixed:
                queue[i-1] = fixed
                tagged.append((i, fixed))

        yield from self.displayAll(tagged, 25 if msg.prefix == '!' else 5)

        self.save()

    @command("score", r"((?:\d+/)?\d+|[+-]\d+)\s+(.+)")
    def score(self, server, msg, score, query):
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
            split = re.split(r"(\[(?:\d+/)?\d+\])", item, maxsplit=1)
            if len(split) == 3:
                queue[i-1] = split[0] + '[' + score + ']' + split[2]
            else:
                queue[i-1] = item + ' ' + '[' + score + ']'
            # TODO: relative scoring and velocity

        yield from self.displayAll([(i[0], queue[i[0]-1]) for i in q], 25 if msg.prefix == '!' else 5)

        self.save()

    # TODO: Alter hidden tags
    @command("hide", r"(.+)")
    def hide(self, server, msg, query):
        yield from self.tag.funct(self, server, msg, "#hidden", query)

    # TODO: Alter hidden tags
    @command("unhide", r"(.+)")
    def unhide(self, server, msg, query):
        yield from self.untag.funct(self, server, msg, "#hidden", query)        

    @command
    def qexport(self, server, msg):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        data = "\n".join(queue)
        postres = requests.post("https://api.github.com/gists", data=json.dumps({"files": {"%s-todo.txt" % (msg.address.nick): {"content": data}}}))
        response = postres.json()
        return "06│ Exported to %s." % response["html_url"]

    @command("qimport", "(\S+)")
    def qimport(self, server, msg, url):
        nick = server.lower(msg.address.nick)
        queue = self.queues.setdefault(nick, [])
        qlen = len(queue)
        data = requests.get(url).text.split("\n")
        if len(data) > 500:
            return "06│ Queue too large. Upgrade to Karkat Premium to raise your storage limit."
        queue.extend(data)
        self.save()
        yield from self.displayAll([(i+qlen+1, v) for i, v in enumerate(data)], 25 if msg.prefix == '!' else 5)


    def save(self):
        with open(self.qfile, "w") as f:
            json.dump(self.queues, f)


__initialise__ = Queue