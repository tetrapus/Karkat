from collections import deque
import minify

# For axis declarations, [top, right, bottom, left]

GRAPH_BLOCK = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█', '\x16 \x16']

GRAPH_FILLED_DOTS = ['\x0300⋅', '\x0315⋅', '\x0314⋅', '\x0301⋅']
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
    return re.sub(r"(\x16|\x03\d{0,2}(,\d{1,2}})?|\x02)\1", "", minified)
    
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

def graph_dos(values, height):
    delta = 2*height + 1
    values = [round(i * delta) for i in values]
    axis = [min(1, i) for i in values]
    values = [(i - axis[z])/(delta-1) for z, i in enumerate(values)]
    graphed = graph(values, height-1, symbols=GRAPH_FILLED_DOS)
    bottom = ["" + "═╘"[axis[0]]]
    bottom.extend("═╧"[i] for i in axis[1:])
    bottom = "".join(bottom)
    graphed = graphed.replace("\n", "╢\n")
    return "%s╢\n%s╝" % (graphed, bottom)


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

