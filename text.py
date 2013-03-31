"""
This module contains functions that format text.
"""

import re
from datetime import timedelta
import htmlentitydefs


def lineify(data, max_size=400):
    """
    Split text up into IRC-safe lines.
    """
    lines = []
    for i in data.split("\n"):
        line = [[]]
        words = i.split(" ")
        for word in words:
            if len(" ".join(line[-1])) < max_size:
                line[-1].append(word)
            else:
                line.append([word])
        lines.extend(" ".join(x) for x in line)
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
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff/7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff/30) + " months ago"
    return str(day_diff/365) + " years ago"

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
                    result = unichr(int(text[3:-1], 16))
                else:
                    result = unichr(int(text[2:-1]))
                result = result.encode("utf-8")
            except ValueError:
                pass
            else:
                return result
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]]).encode("utf-8")
            except KeyError:
                if text == "&apos;":
                    text = "'"
            except UnicodeDecodeError:
                pass
                
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)
    

def striplen(data):
    return len(ircstrip(data).decode("utf-8"))

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
    
def aligntable(rows, separator=" 08| "):
    """
    Column-align a table of rows.
    """
    assert len({len(x) for x in rows}) == 1
    columns = zip(*rows)
    for i, col in enumerate(columns):
        width = max(len(x.decode("utf-8")) for x in col)
        for j, cell in enumerate(col):
            rows[j][i] = cell + (" "*(width - len(cell.decode("utf-8"))))
    rows = [separator.join(x) for x in rows]
    return rows

class Buffer(object):
    """
    Represents an iterable buffer that returns completed lines.

    Note: This object is not thread safe.
    """

    def __init__(self):
        self.buffer = ""

    def __iter__(self):
        return self

    def next(self):
        if "\n" not in self.buffer:
            raise StopIteration
        else:
            data, self.buffer = tuple(self.buffer.split("\n", 1))
            return data
        
    def append(self, data):
        self.buffer += data
        return data