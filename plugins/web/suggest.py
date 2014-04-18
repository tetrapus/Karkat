import requests

from bot.events import Callback, command
from util.text import namedtable

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
    q = query.lower().strip()

    if result:
        if message.prefix == ".":
            result = [i.replace(q, "" if i.startswith(q) else "\x0315%s\x03" % q) for i in result]
            result = [i[1:] if i.startswith(" ") else "\x0315%s\x03%s" % (q, i) for i in map(str.rstrip, result)]
            line = result.pop(0)
            while result and len(line + result[0]) + 3 < 55:
                line += " \x0312·\x03 " + result.pop(0)
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