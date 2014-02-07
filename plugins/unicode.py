"""
Unicode character database search module.
"""

import unicodedata
import json

from bot.events import command, Callback


# Load unicode database
database = open("data/Unicode/UnicodeData.txt").read().split("\n")
database = [i.split(";") for i in database if i]
database = {int(i[0], 16): i for i in database}
# Load character block ranges
blocks = open("data/Unicode/Blocks.txt").read().split("\n")
blocks = [i.split(";") for i in blocks if i.strip() and not i.startswith("#")]
blocks = [([int(x, 16) for x in i[0].split("..")], i[1].strip()) 
            for i in blocks]
# Load category codes
categories = json.load(open("data/Unicode/Categories.json"))

# Callback templates
template = {Callback.USAGE: "\x0304Unicode│\x03 .unicode (character|query)",
            KeyError:       "\x0304Unicode│\x03 Character not found."}
template_sym = {Callback.USAGE: "\x0304Unicode│\x03 .symbols (query)",
                KeyError:       "\x0304Unicode│\x03 Character not found."}

def getdata(char):
    """
    Check if character is recognised by the python unicodedata module.
    """
    try:
        return ("%X" % ord(char), 
                unicodedata.name(char), 
                unicodedata.category(char))
    except:
        raise KeyError("Character not found.")

@Callback.threadsafe
@command("unicode", "(.+)", templates=template)
def search(server, message, data):
    """
    Search for a specific unicode character and show related information.
    """
    if len(data) == 1:
        # Single character, search for the specific character
        try:
            results = [database[ord(data)]]
        except KeyError:
            results = [getdata(data)]
    else:
        # Check other fields
        data = data.upper()
        results = [i for i in database.values() if any(data == x for x in i)]
        results += [i for i in database.values() 
                      if any(data in x for x in i) and not any(data == x 
                                                                for x in i)]
        if not results:
            # If we can't find it, see if unicodedata has it
            results = [getdata(unicodedata.lookup(data))]

    nresults, show = (len(results), 4) if message.prefix != "." else (1, 1)

    for result in results[:show]:
        code = int(result[0], 16)
        # Figure out which block it's in
        for block in blocks:
            if block[0][0] <= code <= block[0][1]:
                charblock = block[1]
                break
        else:
            charblock = "Unknown"

        info = {"module": "Unicode" if message.prefix != "." else "",
                "symbol": repr(chr(code))[1:-1],
                "code": result[0],
                "name": result[1],
                "block": charblock,
                "category": categories.get(result[2], "Unknown")
                }

        yield "\x0306%(module)s│\x03 %(symbol)s \x0306│\x03"\
              " U+%(code)s %(name)s \x0306│\x03"\
              " %(block)s · %(category)s" % info
 
    # If the user requested more than 4 results, inform them of omitted results
    if nresults > 4:
        yield "\x0306Unicode│\x03 %d of %d results shown." % (4, nresults)

@Callback.threadsafe
@command("symbols", "(.+)")
def symbols(server, msg, data):
    """
    List unicode characters matching a search string.
    """
    data = data.upper()

    # Search main database
    results = [i for i in database.values() if any(data in x for x in i)]
    # Search category names
    if data in [i.upper() for i in categories.values()]:
        category = {v.upper(): k for k, v in categories.items()}[data]
        results += [i for i in database.values() if i[2] == category]
    # Check category symbols
    if data in [i.upper() for i in categories.keys()]:
        results += [i for i in database.values() if i[2].upper() == data]
    # Search blocks
    for block in [x[0] for x in blocks if data == x[1].upper()]:
        results += ["%X" % i for i in range(block[0], block[1])]

    results = [repr(chr(int(i[0], 16)))[1:-1] for i in results]
    results.sort(key=lambda x:x.startswith("\\"))

    # Truncate results
    size = -1
    chars = []
    while results and size < 400:
        char = results.pop(0)
        chars.append(char)
        size += len(char.encode("utf-8", errors="replace")) + 1

    if results:
        chars.append("and %d more." % (len(results)))

    if not chars:
        chars = ["No results."]

    return "\x0306%s│\x03 %s" % ("Unicode" if msg.prefix != "." else "",
                                 " ".join(chars))

__callbacks__ = {"privmsg":[search, symbols]}
