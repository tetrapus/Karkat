import requests

from bot.events import Callback, command
from util.text import namedtable, striplen

def suggest(query):
    return requests.get("http://suggestqueries.google.com/complete/search?output=firefox&client=firefox&hl=en&q=%(searchTerms)s"%{"searchTerms":query}).json()[1]

@Callback.threadsafe
@command(["complete", "suggest"], "(.+)", 
         templates={Callback.USAGE: "12Google suggest│  Usage: [!@](complete|suggest) <query>"})
def complete_trigger(server, message, query):
    """
    - Syntax: [!@](complete|suggest) 03query
    - Description: Ask Google for similar search queries.
    """
    result = suggest(query)
    q = query.lower().strip().strip("\"'")

    if result:
        if message.prefix == ".":
            parsed = []
            for i in result:
                if i.startswith(q):
                    i = i.replace(q, "" if i.startswith(q) else "\x0315%s\x03" % q, 1).rstrip()
                    if not i.startswith(" "):
                        i = "\x0315%s\x03%s" % (q, i)
                    else:
                        i = i.strip()
                else:
                    i = i.replace(q, "\x0315%s\x03" % q) 
                parsed.append(i)
            line = parsed.pop(0)
            while parsed and striplen(line + parsed[0]) + 3 < 60:
                line += " \x0312·\x03 " + parsed.pop(0)
            yield "12│ %s 12│ %s" % (query, line)
        else:
            result = [i.replace(q, "\x0315%s\x03" % q) for i in result]
            table = namedtable(result, 
                               size    = 72, 
                               rowmax  = 4 if message.text.startswith("@") else None, 
                               header  = "12G04o08o12g03l04e12 suggest  ", 
                               rheader = "'%s'" % query)
            for line in table:
                yield line
    else:
        yield "05Google suggest│  No results."

__callbacks__ = {"privmsg": [complete_trigger]}