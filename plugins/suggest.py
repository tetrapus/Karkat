import json
import requests
from text import namedtable

from irc import Callback

cb = Callback()

def suggest(query):
    data = requests.get("http://suggestqueries.google.com/complete/search?output=firefox&client=firefox&hl=en&q=%(searchTerms)s"%{"searchTerms":query}).text
    data = json.loads(data)[1]
    return data

@cb.threadsafe
@cb.command(triggers = ["complete", "suggest"], 
            args     = "(.+)", 
            help     = "12Google suggest⎟  Usage: [!@](complete|suggest) QUERY.")
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