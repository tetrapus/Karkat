import collections
import re

import util

from util.services import url
from util.text import aligntable


symbols = {"~~"          :"≈";
           "lambda"      :"λ", 
           "e"           :"ℯ", 
           "theta"       :"θ", 
           "infinity"    :"∞", 
           "pi"          :"π", 
           "integral"    :"∫", 
           "element"     :"∈", 
           "intersection":"∩", 
           "union"       :"∪", 
           "IMPLIES"     :"⇒", 
           "sqrt"        :"√‾", 
           "sum"         :"∑", 
           "product"     :"∏", 
           "constant"    :"08 Constant"}

sub = {"0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇",
       "8":"₈","9":"₉","+":"₊","-":"₋","=":"₌","(":"₍",")":"₎","a":"ₐ",
       "e":"ₑ","h":"ₕ","i":"ᵢ","k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ",
       "p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ","u":"ᵤ","v":"ᵥ","x":"ₓ"," ": "",
       }

sup = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷",
       "8":"⁸","9":"⁹","+":"⁺","-":"⁻","=":"⁼","(":"⁽",")":"⁾","a":"ᵃ",
       "b":"ᵇ", "c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","i":"ⁱ",
       "j":"ʲ","k":"ᵏ","l":"ˡ","m":"ᵐ","n":"ⁿ","o":"ᵒ","p":"ᵖ","r":"ʳ",
       "s":"ˢ","t":"ᵗ","u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ",
       " ":" ", "_":"-", "T":"ᵀ",
       }

supset = "abcdefghijklmnoprstuvwxyz0123456789_T"
subset = "aehiklmnoprstuvx0123456789"

def delete_blank(data):
    """ Remove blank lines from the data. """
    return (i for i in data if i.strip())

def transpose_prepare(data):
    """ Prepare all transposes with a more parseable format. """
    return (i.replace("^transpose", "^T") for i in data)

def replace_encoded_chars(data):
    """ Replace escaped characters with their proper value. """
    getchar = lambda x: chr(int(x.group(1), 16))
    return (re.sub(r"\\:([a-f0-9]{4})", getchar, i) for i in data)

def is_maths(line):
    """
    Check if a line is mathematical.
    A line is probably mathematical if:
        1. The greatest contiguous sequence of alpha characters is 3.
        2. The average contiguous sequence of alpha characters is < 1.5
        3. At least 25% of characters are non-alphanumeric
    """
    alpha_seq = re.split("[^a-zA-Z]+", line)
    rule1 = max(len(x) for x in alpha_seq) <= 3
    rule2 = sum(len(i) for i in alpha_seq) / len(alpha_seq) < 1.5
    rule3 = len([i for i in line if not i.isalpha()]) / len(line) > 0.25
    return rule1 and rule2 and rule3

def replace_symbol_words(line):
    """ Replace symbolic names for symbols with the mapped symbol. """
    replace_symbol = lambda x: symbols[x.group(0).lower()] if x.group(0) in symbols else x.group(0)
    return re.sub(r"[a-z~]+", replace_symbol, line, flags=re.IGNORECASE)

def respace_expression(line):
    """ Re-space expressions to be more mathematical """
    line = re.sub(r"(\d) ([a-z]\b)", r"\1\2", line)
    line = re.sub(r"([^a-z][-+].|.[-+][^a-z])", lambda x: " ".join(x), line)
    return line

def parse_maths(data):
    """ Parse all mathematical lines into a unicodier format. """
    symbolic = (replace_symbol_words(i) for i in data)
    return (respace_expression(i) if is_maths(i) else i for i in data)

def getexpr(expr, mapping):
    """ 
    Tries to balance the brackets of an expression.
    Will return the empty string or an expression wrapped in brackets.
    """
    count = 0
    brackets = 0
    queue = collections.deque(expr)

    while queue:
        temp = queue.popleft()
        if temp == "(":
            brackets += 1
        elif temp == ")":
            brackets -= 1
        elif temp not in mapping: 
            return ""
        
        count += 1

        if brackets <= 0: 
            break
    
    if brackets or count == 1: 
        return ""

    assert expr[0] + expr[count-1] == "()" or not expr
    
    return expr[:count]

def substitute(regex, sub, raw_subset):
    """ Replace in superscripts and subscripts. """
    greedy = regex.group(1)
    subset = "".join(sub.keys())

    if greedy.startswith("("):
        expr = getexpr(greedy, subset)
        if expr:
            result = "".join(map(lambda x: sub[x], expr[1:-1])).replace(" ", "")
            result += greedy[len(expr):]
        else: result = regex.group(0)[0]+greedy
    else:
        result = ""
        for i in greedy:
            if i in raw_subset:
                result += sub[i]
            else:
                break
        result += greedy[len(result):]
    return result

def parse_supersubs(data):
    """ Parse the superscripts and subscripts. """
    rval = []
    for line in data:
        sups = ""
        while sups != line:
            sups = line
            line = re.sub("\\^(.+)", lambda s: substitute(s, sup, supset), line, flags=re.IGNORECASE)
        subs = ""
        while subs != line:
            subs = line
            line = re.sub("_(.+)", lambda s: substitute(s, sub, subset), line, flags=re.IGNORECASE)
        rval.append(line)
    return rval

def shorten_urls(data):
    """ Shorten and format all URLs. """
    jobs = []
    for line in data:
        jobs.append((lambda i: lambda: re.sub("http://[^ ]+", lambda x: url.format(url.shorten(x.group(0))), i))(line))

    return util.parallelise(jobs)

def bracket_chunk(data):
    """ Join all the lines with unbalanced brackets. """
    tension = 0
    chunks = []
    for i in data:
        if tension == 0:
            chunks.append(i)
        else:
            chunks[-1] += "\n" + i
        tension += get_parenthetic_degree(i)
    return chunks

def table_chunk(data):
    dangling = 0
    chunks = []
    for i in data:
        if "\n" in i:
            # Already chunked: skip.
            chunks.append(i)
            dangling = 0
            continue
        elif i.startswith("= "):
            # Dangling equality
            chunks[-1] += "\n" + ("| "*dangling + "15" + i)
            continue
        elif dangling and dangling == i.count("|"):
            # Table continuation
            chunks[-1] += "\n" + i

        elif dangling and dangling + 1 == i.count("|"):
            # Intertable split
            chunk, split = i.rsplit("|", 1)
            chunks[-1] += "\n" + chunk
            i = split
            chunks.append(i)
        else:
            chunks.append(i)
        dangling = i.count("|")

    return chunks

def rechunk(data):
    """ Split up the data into a series of 'typed' chunks with different formats. """

    chunks = bracket_chunk(data)
    chunks = table_chunk(chunks)
    return chunks

def get_parenthetic_degree(line):
    """ Checks the parenthesis balance. """
    return line.count("(") - line.count(")")

def is_parenthetic(chunk):
    """
    Checks if a chunk is metadata.
    i.e it's bracketed and isn't a matrix.
    """
    return chunk.startswith("(") and chunk.endswith(")") and not is_matrix(chunk)

def is_matrix(chunk):
    """
    Checks if a chunk is a matrix.
    A chunk is a matrix if all lines have equal pipe counts, all middle brackets are balanced and the last resolves the first.
    """
    is_matrix = bool(chunk)                                                          # Empty lines are not matrices
    is_matrix = is_matrix and len({i.count("|") for i in chunk.split("\n")}) == 1    # Matrices have equal number of columns for all columns
    is_matrix = is_matrix and "|" in chunk                                           # Matrices have more than 1 column

    lines = chunk.split("\n")
    is_matrix = is_matrix and get_parenthetic_degree(lines[0]) == get_parenthetic_degree(lines[-1]) + 2
    for i in lines[1:-1]:
        is_matrix = is_matrix and not get_parenthetic_degree(i)
    return is_matrix

def is_table(chunk):
    """ 
    Checks if a chunk is a table.
    A chunk is a table if  all lines have equal pipe counts, pipes exist and all brackets are balanced.
    """
    is_table = bool(chunk)                                                          # Empty lines are not tables
    is_table = is_table and len({i.count("|") for i in chunk.split("\n")}) == 1     # Tables have equal number of columns for all columns
    is_table = is_table and "|" in chunk                                            # Tables have more than 1 column
    for i in chunk.split("\n"):
        is_table = is_table and not get_parenthetic_degree(i)
    return is_table

def format_brackets(chunk):
    """ Formats metadata (brackets) """
    return "05⤷ %s" % chunk[1:-1].replace("\n", "")

def format_normal(chunk):
    """ Formats normal lines. """
    return chunk

def format_matrix(chunk):
    """ Takes a matrix and formats/aligns it. """
    data = chunk.split("\n")
    prematrix, data[0] = data[0].split("(", 1)
    data[-1], postmatrix = data[-1].rsplit(")", 1)
    data = [[cell.strip() for cell in row.split("|")] for row in data]
    data = aligntable(data, "  ")
    data[0]    =  "⎛%s⎞" % data[0]
    data[1:-1] = ["⎜%s⎟" % i for i in data[1:-1]]
    data[-1]   =  "⎝%s⎠" % data[-1]
    data = [(" "*len(prematrix))+i for i in data]
    data[int(len(data)/2)] = prematrix + data[int(len(data)/2)].lstrip() + postmatrix

    return data

def format_table(chunk):
    """ Takes a pipe-separated table and aligns the columns. """
    data = [[cell.strip() for cell in row.split("|")] 
                          for row in chunk.split("\n")]

    table = aligntable(data)

    if data and not data[0][0]:
        if any(i[0] for i in data):
            # Blank top-left cell implies first row is headings.
            table[0] = "%s" % table[0]
    return table

def format(data):
    """ Takes a series of 'typed' chunks and formats them. """
    newdata = []
    for i in data:
        if is_parenthetic(i):
            newdata.append(format_brackets(i))
        elif is_table(i):
            newdata.extend(format_table(i))
        elif is_matrix(i):
            newdata.extend(format_matrix(i))
        else:
            newdata.append(format_normal(i))
    return newdata
