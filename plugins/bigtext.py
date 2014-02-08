import re

from bot.events import command, Callback
from util.text import ircstrip, minify

def parse(btf):
    data = open(btf).read().split("\n")
    num = None
    ds = {}
    for i in data:
        if i.startswith("#"):
            num = chr(int(i[1:]))
        else:
            ds.setdefault(num, []).append(i)
    return ds

def big(f, ds):
    if "\n" in f:
        return "\n".join(big(i, ds) for i in f.split("\n"))
    return "\n".join("".join(p) for p in zip(*[expand(i, ds) for i in re.split(r"(\x03(?:\d{0,2}(?:,\d{1,2})?)?|\x1f|\x0f|\x16|\x02|.)", f) if i]))

def expand(char, ds):
    backup = ds[None]
    if re.match(r"(\x03(\d{0,2}(,\d{1,2})?)?|\x0f|\x16|\x02)", char):
        return [char] * len(backup)
    elif char == "\x1f":
        return [""] * (len(backup) - 1) + [char]
    else:
        return ds.get(char, backup)

colors = [13, 4, 8, 12, 13, 9, 11, 12]
k = len(colors)

mapping = {"dong":"₫",
           "snowman": "☃",
           "lovehotel": "🏩",
           "bear": "༼ つ ◕_◕ ༽つ",
           "bface": "(｡◕‿‿◕｡)",
           "gface":"( ≖‿≖)",
           "dface":"ಠ_ಠ",
           "gay": "👬",
           "flower": "✿",
           "poo": "💩",
           "man": "👨",
           "lion": "🐱",
           "kface":"(◕‿◕✿)",
           "finn":"| (• ◡•)|",
           "jake": "(❍ᴥ❍ʋ)",
           "wface":"(⊙▂⊙)",
           "cface":"(╥﹏╥)",
           "goface":"ʕ ◔ϖ◔ʔ",
           "eface":"(ケ≖‿≖)ケ",
           "hface": "┐('~` ;)┌",
           "lhoof": "/)",
           "rhoof": "(\\",
           "brohoof": "/) (\\",
           "omega": "ω",
           "doge": "🐶",
           "denko": "(´・ω・`)",
           "chownface": "( ´· ‿ ·`)",
           "shrug": "¯\_(ツ)_/¯",
           "dongers": "ヽ༼ຈل͜ຈ༽ﾉ",
           "lenny": "( ͡° ͜ʖ ͡°)",
           "sface": "눈_눈",
           "fface": "(ง ° ل °)ง"}

thicker = {"╮": "┓", "╭":"┏", "╰": "┗", "╯":"┛", '╿': '┃', '╾': '━', '╽': '┃', '╼': '━', '╷': '╻', '╶': '╺', '╵': '╹', '╴': '╸', '╊': '╋', '╉': '╋', '╈': '╋', '╎': '╏', '╌': '╍', '╃': '╋', '╂': '╋', '╁': '╋', '╀': '╋', '╇': '╋', '╆': '╋', '╅': '╋', '╄': '╋', '┺': '┻', '┹': '┻', '┸': '┻', '┿': '╋', '┾': '╋', '┽': '╋', '┼': '╋', '┲': '┳', '┱': '┳', '┰': '┳', '┷': '┻', '┶': '┻', '┵': '┻', '┴': '┻', '┪': '┫', '┩': '┫', '┨': '┫', '┯': '┳', '┮': '┳', '┭': '┳', '┬': '┳', '┢': '┣', '┡': '┣', '┠': '┣', '┧': '┫', '┦': '┫', '┥': '┫', '┤': '┫', '┚': '┛', '┙': '┛', '┘': '┛', '┟': '┣', '┞': '┣', '┝': '┣', '├': '┣', '┒': '┓', '┑': '┓', '┐': '┓', '┖': '┗', '┕': '┗', '└': '┗', '┊': '┋', '┈': '┉', '┎': '┏', '┍': '┏', '┌': '┏', '│': '┃', '─': '━', '┆': '┇', '┄': '┅'}


def subs(g):
    key = g.group(0)[1:].lower()
    if key in mapping:
        return mapping[key]
    else:
        return "$" + key

def thicken(text):
    ans = ""
    for i in text:
        if i in thicker:
            i = thicker[i]
        ans += i
    return ans

@Callback.threadsafe
@command("big", "(?:-([rbclt!]*)([1-5])?\s+)?(.+)")
def bigtext(server, message, flags, lines, text):
    lines = int(lines or 3)
    if not flags: flags = ""
    if "!" not in flags:
        text = re.sub(r"\$[a-z]+", subs, text, flags=re.IGNORECASE)
    if len(text * lines) > 90:
        text = text[:int(90/lines)] + "..."
    if "c" in flags:
        text = text.upper()
    if "l" in flags:
        text = text.lower()
    if lines == 1:
        text = "│ " + text
    else:
        ds = parse("data/bigtext/%d.txt" % lines)
        text = big(text, ds)
    if "t" in flags:
        text = thicken(text)
    if "r" in flags:
        text = "\n".join("".join("\x03%.2d%s" % (colors[(n+int(m/2))%k], i[2*m:2*(m+1)]) if i[2*m:2*(m+1)].strip() else i[2*m:2*(m+1)] for m in range(int((len(i)+1)/2))) for n, i in enumerate(map(ircstrip, text.split("\n"))))
    if "b" in flags:
        text = "\n".join("\x02" + x for x in text.split("\n"))
    return minify(text)

@Callback.threadsafe
@command("bigvars")
def bigvars(server, message):
    return "│ " + (", ".join("$" + x for x in mapping))

__callbacks__ = {"privmsg":[bigtext, bigvars]}