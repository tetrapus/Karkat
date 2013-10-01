import requests

from util.irc import Callback
from util.text import namedtable

cb = Callback()

def suggest(query):
    return requests.get("http://suggestqueries.google.com/complete/search?output=firefox&client=firefox&hl=en&q=%(searchTerms)s"%{"searchTerms":query}).json()[1]

@cb.threadsafe
@cb.command(["complete", "suggest"], "(.+)", 
            usage = "12Google suggest⎟  Usage: [!@](complete|suggest) <query>")
def complete_trigger(message, query):
    """
    - Syntax: [!@](complete|suggest) 03query
    - Description: Ask Google for similar search queries.
    """
    result = suggest(query)
    if result:
        table = namedtable(result, 
                           size    = 72, 
                           rowmax  = 3 if message.text.startswith("@") else None, 
                           header  = "12G04o08o12g03l04e12 suggest  ", 
                           rheader = "'%s'" % query)
        for line in table:
            yield line
    else:
        yield "05Google suggest⎟  No results."

__initialise__ = cb.initialise
__callbacks__ = {"privmsg": [complete_trigger]}