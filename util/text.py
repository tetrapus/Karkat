"""
This module contains functions that format text.
"""

import re
import time
import math
from datetime import timedelta
import html.entities


def lineify(data, max_size=400):
    """ Split text up into IRC-safe lines. """

    lines = [item.rstrip() for item in data.split('\n')]
    for item in lines:
        if len(item) > max_size:
            index = lines.index(item)
            lines[index] = item[:item.rfind(' ', 0, 400)]
            lines.insert(index+1, item[item.rfind(' ', 0, 400) + 1:])
    return lines


def pretty_date(delta):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    diff = timedelta(seconds=delta)
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(int(second_diff)) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str(int(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(int(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(int(day_diff/7)) + " weeks ago"
    if day_diff < 365:
        return str(int(day_diff/30)) + " months ago"
    return str(int(day_diff/365)) + " years ago"

def ordinal(value):
    """ Return the ordinal representation of an integer (e.g 1 => 1st) """
    suffixes = {1:"st", 2:"nd", 3:"rd"}
    if value % 100//10 != 1 and value % 10 in suffixes:
        suffix = suffixes[value % 10]
    else:
        suffix = "th"

    return "%d%s" % (value, suffix)

def ircstrip(data):
    """ Strip irc control characters from a string """
    return re.sub(r"(\x03(\d{0,2}(,\d{1,2})?)?|\x1f|\x0f|\x16|\x02|\u0305)", "", data)

def unescape(text):
    """ Parse html encoded characters """
    def fixup(match):
        text = match.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    result = chr(int(text[3:-1], 16))
                else:
                    result = chr(int(text[2:-1]))
            except ValueError:
                pass
            else:
                return result
        else:
            # named entity
            try:
                text = chr(html.entities.name2codepoint[text[1:-1]])
            except KeyError:
                if text == "&apos;":
                    text = "'"
            except UnicodeDecodeError:
                pass

        return text # leave as is
    return re.sub(r"&#?\w+;", fixup, text)


def striplen(data):
    """ Calculate the display length of a string """
    return len(ircstrip(data))


def spacepad(left, right, length):
    """ Glues together left and right with the correct amount of padding. """
    clength = striplen(left) + striplen(right)
    return left + (" " * (length - clength)) + right


def namedtable(results, size=100, rowmax=None, header="", rheader="", color=12):
    """ Create a bordered table. """
    border_left  =  "\x03%.2d⎢\x03"  % color
    divider      = " \x03%.2d⎪\x03 " % color
    border_right =  "\x03%.2d⎥\x03"  % color

    results = list(results)
    # Calculate the biggest column size
    biggest = len(max(results, key=len))
    # Calculate the maximum number of possible columns
    columns = int((size-2) / (biggest+3))
    # If there are less results than columns, truncate to results
    columns = min(len(results), columns)
    # Calculate how many rows exist
    rows = int(math.ceil(len(results)/float(columns)))
    rownum = ""
    # Try to optimise number of elements within the row limit
    if rowmax and rows > rowmax:
        while rows > rowmax:
            results.remove(max(results, key=len))
            biggest = len(max(results, key=len))
            columns = int((size-2) / (biggest+3))
            columns = min(len(results), columns)
            rows = int(math.ceil(len(results)/float(columns)))
        rownum = "(first %d rows) " % rows
    # Create the header
    data = [spacepad("%s\x03%.2d%s" % (header, color, rownum),
                     rheader,
                     (columns * (biggest+3)) -1)]
    # If the header is too big, expand the table.
    if columns*(biggest+3) - 1 < striplen(data[0]):
        cellsize = int((striplen(data[0])-1) / columns) - 1
    else:
        cellsize = biggest

    for i in range(rows):
        if len(results) > (i+1)*columns:
            line = results[i*columns:(i+1)*columns]
        else:
            line = results[i*columns:]
        padded_line = []
        for index, cell in enumerate(line):
            # Right-align the rightmost row.
            padding = " " * (cellsize-striplen(cell))
            if index + 1 == columns:
                padded_line.append("%s%s" % (padding, cell))
            else:
                padded_line.append("%s%s" % (cell, padding))

        data.append(border_left + divider.join(padded_line) + border_right)

    if len(data) > 2 and len(data[-1]) < len(data[1]):
        replacement = list(data[-2])
        replacement.insert(len(data[-1])-1, "\x1f")
        data[-2] = "".join(replacement)
        data[-1] = data[-1][:-2] + " ⎪\x03"
    data[-1] = ""+data[-1]
    return data

def justifiedtable(array, width, minsep=3):
    """
    Formats a string array into equal-length rows.
    """
    rows = [[]]
    table = []
    for data in array:
        length = sum(striplen(x) + minsep for x in rows[-1]) + striplen(data)
        if length <= width:
            rows[-1].append(data)
        else:
            rows.append([data])
    for row in rows:
        if len(row) > 1:
            table.append(row[0])
            rowlength = sum(striplen(x) for x in row)
            sepwidth, spares = divmod(width - rowlength, len(row) - 1)
            for i, string in enumerate(row[1:]):
                table[-1] += " "*sepwidth
                if i < spares:
                    table[-1] += " "
                table[-1] += string
        elif row:
            table.append(row[0])
    return table


def aligntable(rows, separator=" 08⎪ "):
    """
    Column-align a table of rows.
    """
    # Pad the rows
    maxwidth = len(max(rows, key=len))
    for i in rows:
        if len(i) != maxwidth:
            i.extend([""] * (maxwidth-len(i)))

    # Invert
    columns = list(zip(*rows))
    for i, col in enumerate(columns):
        width = max(striplen(x) for x in col)
        for j, cell in enumerate(col):
            rows[j][i] = cell + (" "*(width - striplen(cell)))
    rows = [separator.join(x) for x in rows]
    return rows

def cmp(a, b):
    return (a > b) - (a < b)

def graph_vertical_DOS(values, minheight=3):
    values = [round(i) for i in values]
    CSTART, CMID, CEND = "╘", "╧", "╧"
    CSZERO, CMZERO, CEZERO = "═", "═", "═"
    CFULL, CHALF, CEMPTY = "│", "┬", "─"

    # Draw the axes
    start = []
    if not values:
        return []

    start.append(CSTART if values[0] else CSZERO)
    for i in values[1:-1]:
        start.append(CMID if i else CMZERO)
    start.append(CEND if values[-1] else CEZERO)
    start.append("╝")

    values = [i-1 for i in values]

    # Create the graph
    height = max(math.ceil(max(values) / 2), minheight)
    data = [[[CHALF, CEMPTY, CFULL][cmp(y, (x-1) / 2)]
             for x in values] + ["╢"]
            for y in range(height)][::-1]

    return ["".join(x).replace("", "") for x in data + [start]]


def graph_vertical(values, filled=False, minheight=3):
    """
    >>> print(graph_vertical([8, 1, 2, 3, 0, 8.2]))
    ╻    ┃
    ┃    ┃
    ┃    ┃
    ┃ ╻┃ ┃
    ┖┸┸┸─┚
    >>> print(graph_vertical([8, 1, 2, 3, 0, 8.2], True))
    ╽││││┃
    ┃││││┃
    ┃││││┃
    ┃│╽┃│┃
    ┖┸┸┸┴┚
"""
    values = [round(i) for i in values]
    CSTART, CMID, CEND = tuple("┖┸┚")
    if filled:
        CSZERO, CMZERO, CEZERO = tuple("└┴┘")
        CFULL, CHALF, CEMPTY = tuple("┃╽│")
        CONE, COZERO = tuple("╹╵")
    else:
        CSZERO, CMZERO, CEZERO = tuple("╶─╴")
        CFULL, CHALF, CEMPTY = tuple("┃╻ ")
        CONE, COZERO = tuple("╹·")

    # Draw the axes
    start = []
    if not values:
        return []

    if len(values) == 1:
        start.append(CONE if values[0] else COZERO)
    else:
        start.append(CSTART if values[0] else CSZERO)
        for i in values[1:-1]:
            start.append(CMID if i else CMZERO)
        start.append(CEND if values[-1] else CEZERO)

    values = [i-1 for i in values]

    # Create the graph
    height = max(math.ceil(max(values) / 2), minheight)
    data = [[[CHALF, CEMPTY, CFULL][cmp(y, (x-1) / 2)] 
             for x in values] 
            for y in range(height)][::-1]

    return ["".join(x) for x in data + [start]]

def graph_vertical_DOS(values, minheight=3):
    """
    >>> print(graph_vertical([8, 1, 2, 3, 0, 8.2]))
    ╻    ┃
    ┃    ┃
    ┃    ┃
    ┃ ╻┃ ┃
    ┖┸┸┸─┚
    >>> print(graph_vertical([8, 1, 2, 3, 0, 8.2], True))
    ╽││││┃
    ┃││││┃
    ┃││││┃
    ┃│╽┃│┃
    ┖┸┸┸┴┚
"""
    CSTART, CMID, CEND = tuple("╧╧╛")
    CSZERO, CMZERO, CEZERO = tuple("═══")
    CFULL, CHALF, CEMPTY = ("04│", "04┬", "─")

    # Draw the axes
    start = ["04╚"]
    if not values:
        return []

    start.append(CSTART if values[0] else CSZERO)
    for i in values[1:-1]:
        start.append(CMID if i else CMZERO)
    start.append(CEND if values[-1] else CEZERO)

    values = [i-1 for i in values]

    # Create the graph
    height = max(math.ceil(max(values) / 2), minheight)
    data = [["04╟"] + [[CHALF, CEMPTY, CFULL][cmp(y, (x-1) / 2)] 
             for x in values] 
            for y in range(height)][::-1]

    return ["".join(x) for x in data + [start]]

def graph_horizontal(values, filled=False, minheight=3):
    """
    >>> print(graph_horizontal([8, 1, 12, 3, 0, 22]))
    ┍━━━╸       
    ┝           
    ┝━━━━━╸     
    ┝━          
    │           
    ┕━━━━━━━━━━╸
    >>> print(graph_horizontal([8, 1, 12, 3, 0, 22], True))
    ┍━━━╾───────
    ┝───────────
    ┝━━━━━╾─────
    ┝━──────────
    ├───────────
    ┕━━━━━━━━━━╾
    """
    values = [round(i) for i in values]
    CSTART, CMID, CEND = tuple("┍┝┕")
    if filled:
        CSZERO, CMZERO, CEZERO = tuple("┌├└")
        CFULL, CHALF, CEMPTY = tuple("━╾─")
        CONE, COZERO = tuple("╺╶")
    else:
        CSZERO, CMZERO, CEZERO = tuple("╷│╵")
        CFULL, CHALF, CEMPTY = tuple("━╸ ")
        CONE, COZERO = tuple("╺·")

    # Draw the axes
    start = []
    if not values:
        return []

    if len(values) == 1:
        start.append(CONE if values[0] else COZERO)
    else:
        start.append(CSTART if values[0] else CSZERO)
        for i in values[1:-1]:
            start.append(CMID if i else CMZERO)
        start.append(CEND if values[-1] else CEZERO)

    values = [i-1 for i in values]

    # Create the graph
    height = max(math.ceil(max(values) / 2), minheight)
    data = [[start[i]] 
            + [[CHALF, CEMPTY, CFULL][cmp(y, (x-1) / 2)] 
               for y in range(height)] 
            for i, x in enumerate(values)]

    return ["".join(x) for x in data]

graph = graph_vertical_DOS

class Buffer(object):
    """
    Represents an iterable buffer that returns completed lines.

    Note: This object is not thread safe.
    """

    def __init__(self):
        self.buffer = b''

    def __iter__(self):
        return self

    def next(self):
        if b"\n" not in self.buffer:
            raise StopIteration
        else:
            data, self.buffer = tuple(self.buffer.split(b"\r\n", 1))
            return data.decode("utf-8", "replace")

    def __next__(self):
        return self.next()

    def append(self, data):
        self.buffer += data
        return data

class LineReader(object):
    """
    Iterates over lines from a socket.
    """

    def __init__(self, sock, recv=1024):
        self.recv = recv
        self.sock = sock
        self.buffer = ""

    def __iter__(self):
        return self

    def refill(self):
        """ Refill the buffer. Return False on closed connection. """
        while "\n" not in self.buffer:
            data = self.sock.recv(self.recv)
            if not data:
                return False
            self.buffer += data

    def next(self):
        if not self.refill():
            raise StopIteration
        data, self.buffer = tuple(self.buffer.split("\r\n", 1))
        return data


class TimerBuffer(Buffer):
    """
    Prints out the time between loop iterations.
    """

    def __init__(self, threshhold):
        super(TimerBuffer, self).__init__()
        self.start = None
        self.threshhold = threshhold
        self.log = []

    def next(self):
        if self.start is not None:
            time_taken = time.time() - self.start
            if time_taken > self.threshhold:
                print("!!! Warning: Loop executed in %r seconds." % time_taken)
                self.log.append(time_taken)
        try:
            nextval = super(TimerBuffer, self).next()
        except StopIteration:
            self.start = None
            raise
        else:
            self.start = time.time()
            return nextval

def overline(text):
    return "\u0305".join(text) + "\u0305"

def strikethrough(text):
    return "\u0336".join(text) + "\u0336"

def underline(text):
    return "\u0332".join(text) + "\u0332"