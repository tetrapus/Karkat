from collections import deque
import re

# For axis declarations, [top, right, bottom, left]

GRAPH_BLOCK = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█', '\x16 \x16']

GRAPH_FILLED_DOTS = ['\x0300⋅\x0300', '\x0315⋅\x0315', '\x0314⋅\x0314', '\x0301⋅\x0301']
GRAPH_DOTS = [' ', '\x0315⋅\x0315', '\x0314⋅\x0314', '\x0301⋅\x0301']

GRAPH_FILLED_DOS = ["─", "┬", "│"]
GRAPH_DOS = [" ", "╷", "│"]

GRAPH_FILLED_UNICODE = ['│', '╽', '┃']
GRAPH_UNICODE = [' ', '╻', '┃']


def minify(string):
    """
    Gets rid of redundant irc codes.
    """
    foreground, background = None, None
    bold, italics, reverse, underline = False, False, False, False
    minified = ""
    string = deque(string)
    while string:
        char = string.popleft()
        minified += char
        # TODO

    # warning: ONLY WORKS FOR CURRENT PURPOSES REPLACE WITH FULL LEXER
    minified = re.sub(r"(\x16|\x03\d\d)\1", "", minified)
    return minified

def cmp(a, b):
    return (a > b) - (a < b)

def graph(values, height, symbols=GRAPH_BLOCK):
    assert not any(x < 0 for x in values)

    n = len(symbols) - 1
    values = [round(i * height * n) for i in values]
    output = []

    for i in range(height):
        output.append("".join(symbols[min(i, n)] for i in values))
        values = [i - min(i, n) for i in values]

    output = [minify(i) for i in output[::-1]]
    return "\n".join(output)

def graph_dos(values, height, top=False, right=False, bottom=True, left=True):
    t, b, l, r = [], [], "", ""
    if bottom:
        delta = 2*height + 1
        values = [round(i * delta) for i in values]
        axis = [min(1, i) for i in values]
        values = [(i - axis[z])/(delta-1) for z, i in enumerate(values)]
        height -= 1
        if not left:
            b.append("═╘"[axis[0]])
        b.extend("═╧"[i] for i in axis[not left:-(not right) or None])
        if not right:
            b.append("═╛"[axis[-1]])
        b = ["" + "".join(b) + ""]
    if top:
        t = ["═" * len(values)]
        height -= 1

    graphed = graph(values, height, symbols=GRAPH_FILLED_DOS)
    fullgraph = t + graphed.split("\n") + b
    if left:
        # TODO: fix hanging -s
        l = "╔" * top + "╟" * height + "╚" * bottom
        fullgraph = [l + i for l, i in zip(l, fullgraph)]
    if right:
        r = "╗" * top + "╢" * height + "╝" * bottom
        fullgraph = [i + r for i, r in zip(fullgraph, r)]

    return "\n".join(fullgraph)


def normalise(values, minval=0, maxval=None):
    """ Normalise an array of numbers to the range [0, 1] """ 
    if not values: 
        return values
    
    if minval is None:
        minval = min(values)
    if maxval is None:
        maxval = max(values)

    vrange = maxval - minval

    # Shift the values up so that 0 = minval
    values = [i - minval for i in values]

    # Scale the values
    values = [i/vrange for i in values]

    return values

