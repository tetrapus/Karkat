"""
This module contains functions that format text.
"""

import re
import time
import math
from datetime import timedelta
import html.entities


def average(x): return float(sum(x))/len(x) if x else 0.00

def lineify(data, max_size=400):
    """ Split text up into IRC-safe lines. """
    
    lines = [item.rstrip() for item in data.split('\n')]
    for item in lines:
        if len(item) > max_size:
            index = lines.index(item)
            lines[index] = item[:item.rfind(' ',0,400)]
            lines.insert(index+1, item[item.rfind(' ',0,400)+1:])
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
    suffixes = {1:"st", 2:"nd", 3:"rd"}
    if value % 100//10 != 1 and value % 10 in suffixes:
        suffix = suffixes[value % 10]
    else:
        suffix = "th"

    return "%d%s" % (value, suffix)

def ircstrip(data):
    return re.sub("(\x03(\d{0,2}(,\d{1,2})?)?|\x1f|\x0f|\x16)", "", data)

def unescape(text):
    def fixup(m):
        text = m.group(0)
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
    return re.sub("&#?\w+;", fixup, text)
    

def striplen(data):
    return len(ircstrip(data))


def namedtable(results, size=100, rowmax=None, header="", rheader=""):
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
    data = ["%s\x0312%s%s%s" % (header, 
                                   rownum, 
                                   " "*((columns * (biggest+3)) -1 - striplen(header) - striplen(rheader) - len(rownum)), 
                                   rheader)]
    # If the header is too big, expand the table. TODO: verify this.
    cellsize = int((striplen(data[0])-1) / columns) - 1 if columns*(biggest+3) - 1 < striplen(data[0]) else biggest
    #cellsize = biggest
    for i in range(rows):
        line = results[i*columns:(i+1)*columns if len(results) > (i+1)*columns else len(results)]
        line = ["%s%s"%((x, " "*(cellsize-striplen(x))) if y == 0 or y + 1 < columns else (" "*(cellsize-striplen(x)), x)) for y, x in enumerate(line)]
        data.append("%s%s%s" %("\x0312⎢\x03", " \x0312⎪\x03 ".join(line), "\x0312⎥\x03"))
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
    result = [[]]
    table = []
    for data in array:
        if sum(len(x) + minsep for x in result[-1]) + len(data) <= width:
            result[-1].append(data)
        else:
            result.append([data])
    for row in result:
        if len(row) > 1:
            table.append(row[0])
            sepwidth, spares = divmod(width - sum(len(x) for x in row), len(row) - 1) 
            for i, string in enumerate(row[1:]):
                table[-1] += " "*sepwidth
                if i < spares:
                    table[-1] += " "
                table[-1] += string
        elif row:
            table.append(row[0])
    return table

# TODO: space-saving version

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
        width = max(len(x) for x in col)
        for j, cell in enumerate(col):
            rows[j][i] = cell + (" "*(width - len(cell)))
    rows = [separator.join(x) for x in rows]
    return rows

def tree(tree, separator=" 08⎪ "):
    "│  ├───" # treechars
    tree = sorted(tree)
    # Determine the maximum depth and the width for each column
    # TODO

def generate_tree(ls): pass


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
            timeTook = time.time() - self.start
            if timeTook > self.threshhold:
                print("!!! Warning: Loop executed in %r seconds." % (time.time() - self.start))
                self.log.append(timeTook)
        try:
            nextVal = super(TimerBuffer, self).next()
        except StopIteration:
            self.start = None
            raise
        else:
            self.start = time.time()
            return nextVal
