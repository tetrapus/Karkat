from xml.etree import ElementTree as etree
import collections
import difflib
import re
import sys
import urllib.parse
import urllib.request

import yaml 

import url as URL
import util

from irc import Callback
from text import striplen, aligntable, justifiedtable

try:
    apikeys = yaml.safe_load(open("apikeys.conf"))["wolfram"]
except:
    print("Warning: Wolfram module not loaded: invalid or nonexistant api key.", file=sys.stderr)
    print("Request an apikey at https://developer.wolframalpha.com/portal/apisignup.html and place in apikeys.conf as wolfram.key.<key>")
else:
    __initialise__ = None


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
        elif temp not in mapping: return ""
        count += 1
        if brackets <= 0: break
    if brackets or count == 1: return ""
    try:
        assert expr[0] + expr[count-1] == "()" or not expr
    except: 
        print("%s | %s | %s" % (expr, expr[0] + expr[count-1], expr[:count]), file=sys.stderr)
    return expr[:count]

def substitute(regex, sub, raw_subset):
    greedy = regex.group(1)
    subset = "".join(sub.keys())

    if greedy.startswith("("):
        expr = getexpr(greedy, subset)
        if expr:
            result = u"".join(map(lambda x: sub[x], expr[1:-1])).replace(" ", "")
            result += greedy[len(expr):]
        else: result = regex.group(0)[0]+greedy
    else:
        result = u""
        for i in greedy:
            if i in raw_subset:
                result += sub[i]
            else:
                break
        result += greedy[len(result):]
    return result

def spacepad(left, right, length):
    # Glues together the left and the right with the correct amount of padding.
    clength = striplen(left) + striplen(right)
    return left + (" " * (length - clength)) + right


class WolframParser(object):
    
    @staticmethod
    def delete_blank(data):
        return (i for i in data if i.strip())

    @staticmethod
    def transpose_prepare(data):
        return (i.replace("^transpose", "^T") for i in data)

    @staticmethod
    def replace_encoded_chars(data):
        getchar = lambda x: chr(int(x.group(1), 16))
        return (re.sub(r"\\:([a-f0-9]{4})", getchar, i) for i in data)

    @staticmethod
    def is_maths(line):
        # A line is probably mathematical if:
        # 1. The greatest contiguous sequence of alpha characters is 3.
        # 2. The average contiguous sequence of alpha characters is < 1.5
        # 3. At least 25% of characters are non-alphanumeric
        alpha_seq = re.split("[^a-zA-Z]+", line)
        rule1 = max(len(x) for x in alpha_seq) <= 3
        rule2 = sum(len(i) for i in alpha_seq) / len(alpha_seq) < 1.5
        rule3 = len([i for i in line if not i.isalpha()]) / len(line) > 0.25
        return rule1 and rule2 and rule3

    @staticmethod
    def replace_symbol_words(line):
        symbols = {"lambda"      :"λ", 
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
        replace_symbol = lambda x: symbols[x.group(0).lower()] if x.group(0) in symbols else x.group(0)
        return re.sub(r"[a-z]+", replace_symbol, line, flags=re.IGNORECASE)

    @classmethod
    def parse_maths(cls, data):
        return (cls.replace_symbol_words(i) if cls.is_maths(i) else i for i in data)

    @staticmethod
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

    @staticmethod
    def substitute(regex, sub, raw_subset):
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

    @staticmethod
    def parse_supersubs(data):
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

    @staticmethod
    def shorten_urls(data):
        jobs = []
        for line in data:
            jobs.append((lambda i: lambda: re.sub("http://[^ ]+", lambda x: URL.format(URL.shorten(x.group(0))), i))(line))

        return util.parallelise(jobs)

    @staticmethod
    def tableise_equalities(data):
        return (re.sub("^= ", "| 15= ", i) for i in data)

    @classmethod
    def rechunk(cls, data):
        chunks = []
        multibracket = False
        tension = 0
        lastpipe = 0
        for i in data:
            pdg = cls.get_parenthetic_degree(i)
            if i.startswith("(") and not i.endswith(")") and pdg > 0:
                multibracket = True
                chunks.append("")

            if i.endswith(")") and multibracket and pdg < 0:
                multibracket = False

            if i.startswith("= "):
                chunks.append("| "*lastpipe + "15= ")
            elif lastpipe and lastpipe == i.count("|"):
                chunks[-1] += "\n" + i
                if tension and tension + pdg == 0:
                    i = "" # Split off- we resolved a matrix!
            elif lastpipe and lastpipe + 1 == i.count("|"):
                chunk, split = i.rsplit("|", 1)
                chunks[-1] += "\n" + chunk
                i = split
                chunks.append(i)
            else:
                if multibracket:
                    chunks[-1] += i
                else:
                    chunks.append(i)
            lastpipe = i.count("|")
            tension += pdg

        return chunks

    @staticmethod
    def get_parenthetic_degree(line):
        return line.count("(") - line.count(")")

    @classmethod
    def is_parenthetic(cls, chunk):
        return chunk.startswith("(") and chunk.endswith(")") and not cls.is_matrix(chunk)

    @classmethod
    def is_matrix(cls, chunk):
        # It's a matrix if all lines have equal pipe counts, all middle brackets are balanced but the first and last are - of each other.
        is_matrix = bool(chunk)                                                          # Empty lines are not matrices
        is_matrix = is_matrix and len({i.count("|") for i in chunk.split("\n")}) == 1    # Matrices have equal number of columns for all columns
        lines = chunk.split("\n")
        is_matrix = is_matrix and cls.get_parenthetic_degree(lines[0]) == cls.get_parenthetic_degree(lines[-1]) + 2
        for i in lines[1:-1]:
            is_matrix = is_matrix and not cls.get_parenthetic_degree(i)
        return is_matrix

    @classmethod
    def is_table(cls, chunk):
        # It's a table if all lines have equal pipe counts, pipes exist and all brackets are balanced
        is_table = bool(chunk)                                                          # Empty lines are not tables
        is_table = is_table and len({i.count("|") for i in chunk.split("\n")}) == 1     # Tables have equal number of columns for all columns
        is_table = is_table and "|" in chunk                                            # Tables have more than 1 column
        for i in chunk.split("\n"):
            is_table = is_table and not cls.get_parenthetic_degree(i)
        return is_table

    @staticmethod
    def format_brackets(chunk):
        return "05⤷ %s" % chunk[1:-1]

    @staticmethod
    def format_normal(chunk):
        # TODO: split into lines maybe?
        return chunk

    @staticmethod
    def format_matrix(chunk):
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

    @staticmethod
    def format_table(chunk):
        data = [[cell.strip() for cell in row.split("|")] for row in chunk.split("\n")]

        table = aligntable(data)

        if data and not data[0][0]:
            if any(i[0] for i in data):
                table[0] = "%s" % table[0]
        return table

    @classmethod
    def format(cls, data):
        newdata = []
        for i in data:
            if cls.is_parenthetic(i):
                newdata.append(cls.format_brackets(i))
            elif cls.is_table(i):
                newdata.extend(cls.format_table(i))
            elif cls.is_matrix(i):
                newdata.extend(cls.format_matrix(i))
            else:
                newdata.append(cls.format_normal(i))
        return newdata


class WolframAlpha(WolframParser):

    t_min = 40
    t_max = 62
    cat_outlier = 18 # Maximum width of outlier column.
    timeout = 45
    h_max = 8
    h_max_settings = {"#lgbteens": 3, "lion":50}
    t_lines = 10
    nerf = ["implosion"]
    ascii = [chr(i) for i in range(128)]

    results = ["Result", "Response", "Infinite sum", "Decimal approximation", "Decimal form", "Limit", "Definition", "Definitions", "Description", "Balanced equation", "Chemical names and formulas", "Conversions to other units", "Roots", "Root", "Definite integral", "Plot", "Plots"]
    cb = Callback()

    # TODO: Implement timeout.
    
    def __init__(self, name, bot, printer):
        self.name = name
        self.bot = bot
        self.printer = printer
        self.cb.initialise(name, bot, printer)
        bot.register("privmsg", self.trigger)
        bot.register("privmsg", self.shorthand_trigger)

        
    def breakdown(self, data, width):
        """
        Uses heuristics to guess the data type of a piece of data, then generates an appropriate representation.
        Parses meta, lists, numbers, URLs, numbered lists and tables.
        Truncates long or multiple lines.
        """

        data = self.delete_blank(data)
        data = self.transpose_prepare(data)
        data = self.replace_encoded_chars(data)
        data = self.parse_maths(data)
        data = self.parse_supersubs(data)
        data = self.tableise_equalities(data)
        data = self.shorten_urls(data)
        data = self.rechunk(data)
        data = self.format(data)

        return data
        
    def wolfram(self, query):
        response = urllib.request.urlopen("http://api.wolframalpha.com/v2/query?"+urllib.parse.urlencode({"appid": apikeys["key"], "input":query, "scantimeout":str(self.timeout)}), timeout=self.timeout)
        response = etree.parse(response)
        data = collections.OrderedDict()
        for pod in response.findall("pod"):
            title = pod.get("title")
            data[title] = "\n".join([i.findtext("plaintext") or i.find("img").get("src") for i in pod.findall("subpod")])
            if not data[title].strip(): 
                del data[title]
        return data
        
    def wolfram_format(self, query, category=None, h_max=None):

        try:
            answer = self.wolfram(query)
        except urllib.error.URLError:
            return "05Wolfram08Alpha failed to respond. Try again later or go to " + URL.format(URL.shorten("http://www.wolframalpha.com/input/?i=%s" % urllib.parse.quote_plus(query)))
            
        if not answer:
            return "05Wolfram08Alpha returned no results for '07%s'" % query
        
        if "Input interpretation" in answer: 
            topthing = answer["Input interpretation"]
            remove = "Input interpretation"
        elif "Input" in answer: 
            topthing = answer["Input"]
            remove = "Input"
        else: 
            topthing ="'%s'"%query
            remove = False
        
        topthing = str.join(" ", topthing.split())
        
        t_max = self.t_max
        h_max = h_max or self.h_max

        
        if category is None:
            results = answer
            if remove:
                results = collections.OrderedDict([(k, v) for k, v in results.items() if k != remove])
        elif not category:
            for i in self.results:
                if i in answer:
                    category = i
                    break
            else:
                category = "res"

        if category:
            results = max(answer, key=lambda x:difflib.SequenceMatcher(None, category, x).ratio())
            results = {results:answer[results]}

            # TODO: add a thing to automatically detect if it's small enough. Else:
        
        if t_max - 15 - striplen(topthing) < 0:
            t_max = striplen(topthing) + 15
        
        results = collections.OrderedDict([(k, self.breakdown(v.split("\n"), t_max - 3)) for k, v in results.items()])
        
        total_lines = sum([min([len(results[x]), h_max]) for x in results])
        
        if total_lines > self.t_lines:
            # Too many lines, print the available categories instead.
            res = [spacepad("05Wolfram08Alpha 04 ", " %s" % topthing, t_max)]
            z = justifiedtable(sorted(results.keys(), key=len), t_max-3)
            for i in z:
                res.append(" 04⎜ %s" % i)
            res.append(spacepad(" 04‣ ‣ ‣","05Available Categories", t_max))
        elif results:
            if len(results) == 1 and len(list(results.values())[0]) == 1:
                # I've lost track of the namespace, god help me.
                the_answer = list(results.values())[0][0]
                the_category = list(results.keys())[0]
                if len(the_answer) + len(the_category) + 17 > t_max:
                    # Case 1: 1 long line
                    res = ["05Wolfram08Alpha04⎟ %s 04⎜07%s" % (the_answer, the_category)]
                else:
                    # Case 2: 1 short line
                    res = [spacepad("05Wolfram08Alpha04⎟ %s " % the_answer, "07%s" % the_category, t_max)]
            else:
                # Case 3: n aribtrary length lines
                res = [spacepad("05Wolfram08Alpha 04 ", " %s" % topthing, t_max)]
                for category in results:
                    lines = [x.rstrip() for x in results[category]]
                    # Figure out where to put the category.
                    #if striplen(category) + striplen(lines[0]) + 4 <= t_max:
                    #    # If we can fit everything in nicely
                    first = lines.pop(0)
                    res.append(spacepad(" 08⎨ %s " % first, " 07%s" % category, t_max))
                    # Ignore all the other options.
                    if len(lines) == h_max:
                        truncated = lines[:h_max]
                    else:
                        truncated = lines[:h_max-1]
                    for line in truncated:
                        res.append(" 08⎪ " + line)

                    if len(truncated) != len(lines):
                        omission = "%d more lines" % (len(lines) - h_max)
                        length = t_max - len(omission) - 5
                        res.append(" 08⎬✁" + ("-"*int(length)) + " 07%s" % omission)
        else:
            res.append(" 08‣ 05No plaintext results. See " + URL.format(URL.shorten("http://www.wolframalpha.com/input/?i=%s" % urllib.quote_plus(query))))
        res = [i.rstrip() for i in res]
        return "\n".join(res)

    def getoutputsettings(self, target):
            if self.bot.isIn(target, self.h_max_settings):
                return self.h_max_settings[self.bot.lower(target)]
            else:
                return self.h_max

    @cb.threadsafe
    @Callback.msghandler
    def shorthand_trigger(self, user, context, message):
        pattern = re.match(r"([~`])(.*?\1 ?|([\"']).*?\3 ?|[^ ]+ )(.+)", message.text)
        if pattern:
            prefix, category, quoted, query = pattern.groups()
            category = category.rstrip()
            if quoted:
                category = category[1:-1]
            elif category and category[-1] == prefix:
                category = category[:-1]

            target, msgtype = {"~": (context,   "PRIVMSG"),
                             "`": (user.nick, "NOTICE")}[prefix]

            self.printer.message(self.wolfram_format(query, category, h_max=self.getoutputsettings(target)), target, msgtype)

    @cb.threadsafe
    @cb.command(["wa", "wolfram"], "(.+)",
                usage="05Wolfram08Alpha04⎟ Usage: [.@](wa|wolfram) 03query")
    def trigger(self, message, query):
        return self.wolfram_format(query, h_max=self.getoutputsettings(message.context))

__initialise__ = WolframAlpha
