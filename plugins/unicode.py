from bot.events import command, Callback

database = open("data/UnicodeData.txt").read().split("\n")
database = [i.split(";") for i in database if i]
database = {int(i[0], 16): i for i in database}
blocks = open("data/Blocks.txt").read().split("\n")
blocks = [i.split(";") for i in blocks if i.strip() and not i.startswith("#")]
blocks = [([int(x, 16) for x in i[0].split("..")], i[1].strip()) for i in blocks]
categories = {
"Cc": "Other, Control",
"Cf": "Other, Format",
"Cn": "Other, Not Assigned",
"Co": "Other, Private Use",
"Cs": "Other, Surrogate",
"LC": "Letter, Cased",
"Ll": "Letter, Lowercase",
"Lm": "Letter, Modifier",
"Lo": "Letter, Other",
"Lt": "Letter, Titlecase",
"Lu": "Letter, Uppercase",
"Mc": "Mark, Spacing Combining",
"Me": "Mark, Enclosing",
"Mn": "Mark, Nonspacing",
"Nd": "Number, Decimal Digit",
"Nl": "Number, Letter",
"No": "Number, Other",
"Pc": "Punctuation, Connector",
"Pd": "Punctuation, Dash",
"Pe": "Punctuation, Close",
"Pf": "Punctuation, Final quote",
"Pi": "Punctuation, Initial quote",
"Po": "Punctuation, Other",
"Ps": "Punctuation, Open",
"Sc": "Symbol, Currency",
"Sk": "Symbol, Modifier",
"Sm": "Symbol, Math",
"So": "Symbol, Other",
"Zl": "Separator, Line",
"Zp": "Separator, Paragraph",
"Zs": "Separator, Space"
}

template = {Callback.USAGE: "\x0304Unicode│\x03 .unicode (character|query)",
            KeyError: "\x0304Unicode│\x03 Character not found."}

@command("unicode", "(.+)", templates=template)
def search(server, message, data):
    if len(data) == 1:
        results = [database[ord(data)]]
    else:
        data = data.upper()
        results = [i for i in database.values() if any(data == x for x in i)]
        if not results:
            results = [i for i in database.values() if any(data in x for x in i)]
    if not results:
        raise KeyError("Character not found.")
    nresults, show = (len(results), 4) if message.prefix != "." else (1, 1)
    for r in results[:show]:
        code = int(r[0], 16)
        for b in blocks:
            if b[0][0] <= code <= b[0][1]:
                block = b[1]
                break
        else:
            block = "Unknown"
        info = {"module": "Unicode" if message.prefix != "." else "",
                "symbol": chr(code),
                "code": r[0],
                "name": r[1],
                "block": block,
                "category": categories[r[2]] if r[2] in categories else "Unknown"
                }
        yield "\x0310%(module)s│\x03 %(symbol)s \x0310│\x03 U+%(code)s %(name)s \x0310│\x03 %(block)s · %(category)s" % info
    if nresults > 4:
        yield "\x0310Unicode│\x03 %d of %d results shown." % (4, nresults)

__callbacks__ = {"privmsg":[search]}