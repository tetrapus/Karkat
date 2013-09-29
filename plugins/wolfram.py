from text import striplen, aligntable, justifiedtable
from irc import Callback
import url as URL
import util

import re
import sys
import collections
import difflib
import urllib.parse
import urllib.request
from xml.etree import ElementTree as etree

import yaml 

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

    @classmethod
    def substitute(cls, regex, sub, raw_subset):
        greedy = regex.group(1)
        subset = "".join(sub.keys())

        if greedy.startswith("("):
            expr = cls.getexpr(greedy, subset)
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

    @classmethod
    def parse_supersubs(cls, data):
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
                line = re.sub("\\^(.+)", lambda s: cls.substitute(s, sup, supset), line, flags=re.IGNORECASE)
            subs = ""
            while subs != line:
                subs = line
                line = re.sub("_(.+)", lambda s: cls.substitute(s, sub, subset), line, flags=re.IGNORECASE)
            rval.append(line)
        return rval

    @staticmethod
    def shorten_urls(data):
        jobs = []
        for line in data:
            jobs.append((lambda i: lambda: re.sub("http://[^ ]+", lambda x: URL.format(URL.shorten(x.group(0))), i))(line))

        return util.parallelise(jobs)


class WolframAlpha(WolframParser):

    t_min = 40
    t_max = 62
    cat_outlier = 18 # Maximum width of outlier column.
    timeout = 45
    h_max = 8
    h_max_settings = {"#lgbteens": 3}
    t_lines = 14
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
        hasHeadings = False

        data = self.delete_blank(data)
        data = self.transpose_prepare(data)
        data = self.replace_encoded_chars(data)
        data = self.parse_maths(data)
        data = self.parse_supersubs(data)
        data = self.shorten_urls(data)
        
        data = list(data)

        joined = "\n".join(data)
        meta = re.findall("\n\\s*\\((.+?)\\)\\s*$", joined, flags=re.DOTALL)
        data = re.sub("\n\\s*\\((.+?)\\)\\s*$", "", joined, flags=re.DOTALL).split("\n")
        if len({i.count("|") for i in data if i}) == 1: # fix when matrices are nested in lists.
            # Probably an aligned table!
            isMatrix = len(data) > 1 and data[0].count("(") == data[0].count(")") + 1 and data[-1].count(")") == data[-1].count("(") + 1
            #meta = [(i, string) for i, string in enumerate(data) if string.lstrip().startswith("(") and string.rstrip().endswith(")")]
            #for i, string in meta:
            #    data.remove(string)
            if isMatrix:
                prematrix, data[0] = data[0].split("(", 1)
                data[-1], postmatrix = data[-1].rsplit(")", 1)
            data = [[cell.strip() for cell in row.split("|")] for row in data]

            if data and not data[0][0]:
                hasHeadings = True
            if isMatrix:
                data = aligntable(data, "  ")
                data[0]    =  "⎛%s⎞" % data[0]
                data[1:-1] = ["⎜%s⎟" % i for i in data[1:-1]]
                data[-1]   =  "⎝%s⎠" % data[-1]
                data = [(" "*len(prematrix))+i for i in data]
                data[int(len(data)/2)] = prematrix + data[int(len(data)/2)].lstrip() + postmatrix
            else: 
                data = aligntable(data)
        
        for i in meta:
            data.append("(%s)" % i.replace("\n", ""))
        
        if hasHeadings: data[0] = "%s" % data[0]



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
                    res.append(spacepad(" 04⎜ %s" % first, " 07%s" % category, t_max))
                    # Ignore all the other options.
                    if len(lines) == h_max:
                        truncated = lines[:h_max]
                    else:
                        truncated = lines[:h_max-1]
                    for line in truncated:
                        if line and line == getexpr(line, self.ascii):
                            res.append(" 08‣ 05%s" % line[1:-1])
                        else:
                            res.append(" 08⎜ %s" % line)
                    if len(truncated) != len(lines):
                        omission = "%d more lines omitted" % (len(lines) - h_max)
                        res.append(spacepad(" 08• • •", "07%s" % omission, t_max))
        else:
            res.append(" 08‣ 05No plaintext results. See 12http://www.wolframalpha.com/input/?i=%s05" % urllib.quote_plus(query))
        res = [i.rstrip() for i in res]
        return "\n".join(res)

    def getoutputsettings(self, target):
            if target.lower() in self.h_max_settings:
                return self.h_max_settings[target.lower()]
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

    '''
    @cb.threadsafe
    @cb.msghandler
    def trigger(self, user, context, message):
        """
        - Name: Wolfram|Alpha
        - Identifier: Wolfram
        - Syntax: [~`]03category 03query or [!@]wa 03query (category may be quoted for multiple words)
        - Description: Send a query to 05Wolfram08Alpha. 
        - Access: ALL
        - Type: Command 
        """
        if len(x) > 3 and len(x[3]) > 2 and ((x[3][1] in "!@" and x[3][2:].lower() in ["wolfram", "wa"]) or x[3][1] in "~`" and (len(x) > 4 or (len(x) > 3 and len(x[3]) > 3 and x[3][2] in "`~"))):

            nick, msgtype = (Message(y).context, "PRIVMSG")  if x[3][1] in "@~" else (Address(x[0]).nick, "NOTICE")
            category = None
            if x[3][1] in "~`":
                if x[3][2] not in "({[<":
                    if x[3][1] == x[3][2]:
                        category = False
                        query = " ".join([x[3][3:]] + x[4:])
                    else:
                        category = x[3][2:]
                        query = " ".join(x[4:])
                else:
                    query = Message(y).text
                    category = query[2:query.find({"(":")", "{":"}", "[":"]", "<":">"}[query[1]])]
                    query = str.rstrip(query[len(category)+3:])
            else:
                query = " ".join(x[4:])

            if nick.startswith("#"):
                self.printer.message(self.wolfram_format(query, category, h_max=2), nick, msgtype)
            else:
                self.printer.message(self.wolfram_format(query, category), nick, msgtype)
    '''

__initialise__ = WolframAlpha
