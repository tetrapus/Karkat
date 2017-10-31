import re
import json

from bot.events import command, Callback
from util.irc import Message
from util.text import ircstrip, minify, generate_vulgarity

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
           "fface": "(ง ° ل °)ง",
           "hug": "c(˘⌣˘)ↄ", 
           "yayy": r"º╲˚\╭ᴖ_ᴖ╮/˚╱º", 
           "palette": ' '.join(['\x03,{0:02}  \x0f\x03{0:02} {0:02}\x0f'.format(i) for i in range(16)])}

mapping.update(json.load(open("data/Unicode/unimath.js")))

thicker = {"╮": "┓", "╭":"┏", "╰": "┗", "╯":"┛", '╿': '┃', '╾': '━', '╽': '┃', '╼': '━', '╷': '╻', '╶': '╺', '╵': '╹', '╴': '╸', '╊': '╋', '╉': '╋', '╈': '╋', '╎': '╏', '╌': '╍', '╃': '╋', '╂': '╋', '╁': '╋', '╀': '╋', '╇': '╋', '╆': '╋', '╅': '╋', '╄': '╋', '┺': '┻', '┹': '┻', '┸': '┻', '┿': '╋', '┾': '╋', '┽': '╋', '┼': '╋', '┲': '┳', '┱': '┳', '┰': '┳', '┷': '┻', '┶': '┻', '┵': '┻', '┴': '┻', '┪': '┫', '┩': '┫', '┨': '┫', '┯': '┳', '┮': '┳', '┭': '┳', '┬': '┳', '┢': '┣', '┡': '┣', '┠': '┣', '┧': '┫', '┦': '┫', '┥': '┫', '┤': '┫', '┚': '┛', '┙': '┛', '┘': '┛', '┟': '┣', '┞': '┣', '┝': '┣', '├': '┣', '┒': '┓', '┑': '┓', '┐': '┓', '┖': '┗', '┕': '┗', '└': '┗', '┊': '┋', '┈': '┉', '┎': '┏', '┍': '┏', '┌': '┏', '│': '┃', '─': '━', '┆': '┇', '┄': '┅'}
reverse = {'⎛':'⎞','⎞':'⎛','⎠':'⎝','⎝':'⎠','⚞':'⚟','⚟':'⚞','3':'Ɛ','Ɛ':'3','Ↄ':'C','C':'Ↄ','Ǝ':'E','E':'Ǝ','N':'ᴎ','ᴎ':'N','q':'p','p':'q','⁅':'⁆','⁆':'⁅','c':'ɔ','ɔ':'c','؟':'?','?':'؟','>':'<','<':'>','[':']',']':'[','{':'}','}':'{','(':')',')':'(','/':'\\','\\':'/','d':'b','b':'d','╉': '╊', '╊': '╉', '╃': '╄', '╄': '╃', '╅': '╆', '╆': '╅', '╘': '╛', '╙': '╜', '╚': '╝', '╛': '╘', '╜': '╙', '╝': '╚', '╞': '╡', '╟': '╢', '╒': '╕', '╓': '╖', '╔': '╗', '╕': '╒', '╖': '╓', '╗': '╔', '╭': '╮', '╮': '╭', '╯': '╰', '╠': '╣', '╡': '╞', '╢': '╟', '╣': '╠', '╸': '╺', '╺': '╸', '╼': '╾', '╾': '╼', '╰': '╯', '╱': '╲', '╲': '╱', '╴': '╶', '╶': '╴', '┌': '┐', '┍': '┑', '┎': '┒', '┏': '┓', '┘': '└', '┙': '┕', '┚': '┖', '┛': '┗', '├': '┤', '┝': '┥', '┞': '┦', '┟': '┧', '┐': '┌', '┑': '┍', '┒': '┎', '┓': '┏', '└': '┘', '┕': '┙', '┖': '┚', '┗': '┛', '┨': '┠', '┩': '┡', '┪': '┢', '┫': '┣', '┭': '┮', '┮': '┭', '┠': '┨', '┡': '┩', '┢': '┪', '┣': '┫', '┤': '├', '┥': '┝', '┦': '┞', '┧': '┟', '┹': '┺', '┺': '┹', '┽': '┾', '┾': '┽', '┱': '┲', '┲': '┱', '┵': '┶', '┶': '┵'}
upturned = {'⎞':'⎠','⎠':'⎞','⎝':'⎛','⎛':'⎝','/':'\\','\\':'/','9':'6','6':'9','!':'¡','¡':'!','¿':'؟','؟':'¿','`':',',',':'`','‾':'_','_':'‾','^':'v','v':'^','"':'„','„':'"','⅋':'&','&':'⅋',';':'؛','؛':';','∀':'A','A':'∀','Ⅎ':'F','F':'Ⅎ','L':'⅂','⅂':'L','M':'W','W':'M','G':'⅁','⅁':'G','Y':'⅄','⅄':'Y','P':'b','b':'P','p':'b','b':'p','Q':'Ό','Ό':'Q','R':'ᴚ','ᴚ':'R','T':'⊥','⊥':'T','U':'∩','∩':'U','V':'ᴧ','ᴧ':'V','h':'ɥ','ɥ':'h','j':'ɾ','ɾ':'j','k':'ʞ','ʞ':'k','l':'ʃ','ʃ':'l','m':'ɯ','ɯ':'m','n':'u','u':'n','a':'ɐ','ɐ':'a','d':'q','q':'d','e':'ǝ','ǝ':'e','f':'ɟ','ɟ':'f','g':'ƃ','ƃ':'g','y':'ʎ','ʎ':'y','t':'ʇ','ʇ':'t','∴':'∵','∵':'∴','v':'ʌ','ʌ':'v','w':'ʍ','ʍ':'w','‿':'⁀','⁀':'‿','.':'˙','˙':'.','╈': '╇', '╀': '╁', '╁': '╀', '╃': '╅', '╄': '╆', '╅': '╃', '╆': '╄', '╇': '╈', '╘': '╒', '╙': '╓', '╚': '╔', '╛': '╕', '╜': '╖', '╝': '╗', '╒': '╘', '╓': '╙', '╔': '╚', '╕': '╛', '╖': '╜', '╗': '╝', '╨': '╥', '╩': '╦', '╭': '╰', '╮': '╯', '╯': '╮', '╤': '╧', '╥': '╨', '╦': '╩', '╧': '╤', '╹': '╻', '╻': '╹', '╽': '╿', '╿': '╽', '╰': '╭', '╱': '╲', '╲': '╱', '╵': '╷', '╷': '╵', '┌': '└', '┍': '┕', '┎': '┖', '┏': '┗', '┘': '┐', '┙': '┑', '┚': '┒', '┛': '┓', '┞': '┟', '┟': '┞', '┐': '┘', '┑': '┙', '┒': '┚', '┓': '┛', '└': '┌', '┕': '┍', '┖': '┎', '┗': '┏', '┩': '┪', '┪': '┩', '┬': '┴', '┭': '┵', '┮': '┶', '┯': '┷', '┡': '┢', '┢': '┡', '┦': '┧', '┧': '┦', '┸': '┰', '┹': '┱', '┺': '┲', '┻': '┳', '┰': '┸', '┱': '┹', '┲': '┺', '┳': '┻', '┴': '┬', '┵': '┭', '┶': '┮', '┷': '┯'}


def subs(g):
    key = g.group(0)[1:]
    if key in mapping:
        return mapping[key]
    elif key == "insult":
        return generate_vulgarity().lower()
    elif key == "INSULT":
        return generate_vulgarity().upper()
    else:
        return "\\" + key

def thicken(text):
    return "".join(thicker.get(i, i) for i in text)

def flip(text):
    return "\n".join("".join(reverse.get(i, i) for i in line[::-1]) for line in text.split("\n"))

def upside_down(text):
    return "\n".join("".join(upturned.get(i, i) for i in line) for line in text.split("\n")[::-1])


@Callback.threadsafe
@command("big bigger", "(?:-([rbclt!fu]*)([1-5])?\s+)?(.+)?")
def bigtext(server, message, flags, lines, text):
    if lines:
        lines = int(lines)
    elif message.command == "bigger":
        lines = 5
    else:
        lines = 3
    if not flags: flags = ""
    if "!" not in flags:
        text = re.sub(r"(\$|\\)[a-z]+", subs, text, flags=re.IGNORECASE)
    if len(text * lines) > 90:
        text = text[:int(90/lines)] + "..."
    if "c" in flags:
        text = text.upper()
    if "l" in flags:
        text = text.lower()
    if lines > 1:
        ds = parse("data/bigtext/%d.txt" % lines)
        text = big(text, ds)
    if "t" in flags:
        text = thicken(text)
    if "f" in flags:
        text = flip(text)
    if "u" in flags:
        text = upside_down(text)
    if "r" in flags:
        text = "\n".join("".join("\x03%.2d%s" % (colors[(n+int(m/2))%k], i[2*m:2*(m+1)]) if i[2*m:2*(m+1)].strip() else i[2*m:2*(m+1)] for m in range(int((len(i)+1)/2))) for n, i in enumerate(map(ircstrip, text.split("\n"))))
    if "b" in flags:
        text = "\n".join("\x02" + x for x in text.split("\n"))
    if lines == 1:
        text = "│ " + text
    return minify(text)

@Callback.threadsafe
@command("bigvars")
def bigvars(server, message):
    return "│ " + (", ".join("$" + x for x in mapping))

def smallvars(server, line):
    msg = Message(line)
    text = re.sub(r"\\[a-z]+", subs, msg.text, flags=re.IGNORECASE)
    if text != msg.text and msg.text[0] not in ".!@:":
        server.message("│ "+text, msg.context)

__callbacks__ = {"privmsg":[bigtext, bigvars, smallvars]}
