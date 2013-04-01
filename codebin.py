class Executor(WorkerThread):
    """
    Worker thread which just runs code.
    """
    def __init__(self, namespace={}):
        WorkerThread.__init__(self)
        self.namespace = namespace

    def run(self):
        for code in self.work:
            try:
                exec(code, self.namespace)
            except Exception as err:
                print err


def tabulate(items, maxlen=75, spacer="   ", outliers=0.4, dynamic=True, border=None, compact=False, f_length=striplen):
    avg = sum([f_length(i) for i in items])/len(items)
    wpl = int(maxlen / avg) - 1
    if wpl < 3: wpl = 3
    data = []
    while items:
        data.append(spacer.join(items[-wpl:]))
        items = items[:-wpl]
    return data


class Stop(object):
    def __str__(self):
        printer.clear = True
        s.send("PRIVMSG %s :Printer deactivated for %d seconds.\r\n" % (printer.last, printer.pause))
        return "STOP"
    def __repr__(self):
        return str(self)
stop = Stop()

class mkscript(object):
    scripts = {}
    def __init__(self, name):
        self.data = ""
        self.name = name
        mkscript.scripts[ name ] = self
    def write(self, data):
        self.data += data+"\n"
    def read(self):
        self._data = self.data
        self.data = ""
        return self._data
    def execute(self):
        exec(self.read())

class PasteListener(threading.Thread):
    def __init__(self, port):
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("", self.port))
        self.socket.listen(1)
        print >> sys.__stdout__, "Listening."
        sock, client = self.socket.accept()
        print >> sys.__stdout__, "Connection made."
        paste = ""
        while True:
            data = sock.recv(1024)
            if data:
                paste += data
            else:
                break 
        # code
        try:
            sock.close()
        except:
            pass
        print >> sys.__stdout__, paste
        self.socket.close()

class Pastebin(object):
    connections = {}

    def __init__(self):
        pass

    def trigger(self):
        pass

class SocialSequence(object):
    """
    Start a game of countup.
    """
    
    games = {}
    sequences = {"fib":None}
    lossratio = 0.25
    canstart = lambda x: x[2].lower() in ["#sequence"]
    
    flags = {"start": int, "time": int}
    
    class SequencePlayer(object):
        def __init__(self, name):
            self.name = name
            self.id = name.lower()
            self.points = 0
            self.playing = True
    
    def __init__(self, channel, sequence):
        if channel.lower() in self.games:
            printer.message("「 10Sequence 」 A game is already in progress!")
            return
        
        self.games[channel.lower()] = self
        
        self.players = {} # True is playing, False is out.
        self.number = 0
        self.getnext = sequence
        self.signups = True
        
    def checknum(self, value, player):
        if player not in self.players or self.players[player].playing == False:
            return
        player = self.players[player]
        if self.getnext(self.number, value):
            self.number += 1
            
            
            
    @classmethod
    def parseFlags(flagstring):
        raise NotImplementedError
        
    @classmethod
    def trigger(cls, x, y):
    
        target, msgtype = codify(y)["CONTEXT"], "PRIVMSG"
        if target[0] != "#": 
            return
        nick = Address(x[0]).nick
        
        # Game is in progress, or has started signups.
        if target.lower() in cls.games:
            game = cls.games[target.lower()]

            # Throwaway code / design decision
            if game.signups:
                if not x[3].lower() == ":!join": return
                if nick.lower() in game.players:
                    printer.message("「 10Sequence 」 You're already in this game!", nick, "NOTICE")
                else:
                    game.players[nick.lower()] = SequencePlayer(nick)
                    printer.message("「 10Sequence 」 %s has entered the game." % nick, target, msgtype)
            elif nick.lower() in game.players():
                game.checknum(x[3][1:], nick.lower())
        else:
            if x[3].lower() == ":!sequence":
                if not cls.canstart(x):
                    printer.message("「 10Sequence 」 You cannot start a game.", target, msgtype)
                    return

                flags = cls.parseFlags(codify(y)["MESSAGE"].split(" ", 1)[1])
                    
                SocialSequence(x[2], flags)
                
                printer.message("「 10Sequence 」 A sequence has been chosen. You may !join at any time.")


def linebuilder(stream):
    """
    Mimics behaviour of buffer, with a generator.
    """
    
    data = str()
    while True:
        if "\n" in data:
            pop, data = data.split("\n", 1)
            pop = pop.rstrip("\r")
            yield pop
        else:
            append = stream.recv(1024)
            if not append:
                yield data
                return
            data += append


chanpeople = {} # god this needs to become part of the server socket object so bad
def setUsers(x, y):
    chanpeople[x[4].lower()] = [x[5][1:]] + (x[6:] if len(x) > 6 else [])
    chanpeople[x[4].lower()] = [re.sub("[@%+]", "", i) for i in chanpeople[x[4].lower()]]

    [spellchecker.dictionary.add(i) for i in chanpeople[x[4].lower()] if not spellchecker.dictionary.check(i) and i]
def addUser(x, y):
    if x[2][1:].lower() in chanpeople:
        chanpeople[x[2][1:].lower()] += [Address(x[0]).nick]
    if not spellchecker.dictionary.check(Address(x[0]).nick):
        spellchecker.dictionary.add(Address(x[0]).nick) 
       
def changeUser(x, y):
    for i in chanpeople:
        fnick = Address(x[0]).nick
        if fnick in chanpeople[i]:
            chanpeople[i][chanpeople[i].index(fnick)] = x[2][1:]
        if not spellchecker.dictionary.check(fnick):
            spellchecker.dictionary.add(Address(x[0]).nick) 

class Abyss:
    """
    Instances of this object implement everything, and do nothing.

    That means you shouldn't use it in stuff like for loops.
    """
    def __getattr__(self, x):
        if x == "__call__":
            return lambda *x, **y: self
        elif x in ["__str__", "__repr__"]:
            return lambda x: None
        else:
            return self

class DontTouchThis(object):
    """
    Instances of this object will fuck your shit.
    """
    def __cmp__(self, x):
        sys.exit(1)
    def __nonzero__(self):
        sys.exit(1)

class LinkGrabber(object):
    
    privelaged = ["goes.rawr"]
    
    def __init__(self):
        self.links = {}
        
    @Callback.background
    def trigger_linkget(self, x, y):
        """
        Please only hook to PRIVMSGs.
        """
        x = list(x)
        if x[2][0] == "#":
            x[3] = x[3][1:]
            self.links.setdefault(x[2].lower(), []).extend([i for i in x[3:] if re.match("^(http|https|ftp)\://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,3}(:[a-zA-Z0-9]*)?/?([a-zA-Z0-9\-\._\?\,\'/\\\+&%\$#\=~])*$", i)])
        
    @Callback.threadsafe
    def trigger_openit(self, x, y):
        """
        Again, a privmsg hook.
        """
        if Address(x[0]).mask in self.privelaged and x[3] == ":.last":
            value = 1
            if len(x) > 4 and x[4].isdigit():
                value = int(x[4])
            #import webbrowser
            #webbrowser.open(self.links[x[2].lower()][-value])

lg = LinkGrabber()

def tabulate(items, maxlen=80, spacer="   ", outliers=0.4, dynamic=True, border=None, compact=False, f_length=striplen):
    """
    Creates a space separated dynamically sized table.
    
        maxlen specifies the maximum width of the table, in characters.
        spacer defines a string to insert between entries.
        outliers specifies the threshhold where entries are considered 'outliers' and break formatting, as a percentage of the maximum length.
                Outlier rows have columns which align in some way to previous columns.
        dynamic is a bool describing whether columns can be of variable size.
        border defines a set of strings to place in corners and edges
        compact is a bool describing whether to order items into columns by length to preserve space.
        f_length is a function which generates keys to determine the effective display length of a string.
    """
    
    def getwidth(data, colnum, spacer_width):
        width = 0
        for i in range(colnum):
            width += max(data[i::colnum], key=f_length)
        width += spacer_width * (colnum - 1)
        
        return width
        
    
    table = []
    outliers = []
    data = []
    
    
    for i in items:
        if f_length(i) > int(outliers*maxlen):
            outliers.append(i)
        else:
            data.append(i) 
    
    spacer_width = f_length(spacer)
    border_width = 2*f_length(border or "")
    max_width = maxlen - border_width
    
    if not dynamic:
        col_width = f_length(max(data, key=f_length))
        numcols = int((max_width + spacer_width) / (col_width + spacer_width))
        
    else:
        if compact:
            pass
        numcols = 1
        while getwidth(data, numcols, spacer_width) <= max_width:
            numcols += 1
            
    table = [data[i*numcols:(i+1)*numcols] for i in range(int(math.ceil(float(len(data)) / numcols)))]
            
        
    return [spacer.join(items)] # Placeholder
    # TODO: Loop to determine outliers and have variable columns if only one row exists.

@Callback.threadsafe
def ajoinoi(l, sl):
    if Address(l[0]).nick in ["Lyucit","Lukion","Hexadecimal", "Lion"] or l[3][1:].lower() in server.channels:
        bot.join(":%s" % l[3][1:])



class Weather(object):

    locationdata = shelve.open("weather/defaults", writeback=True)
    locationhistory = shelve.open("weather/history", writeback=True)
    countryformats = ["%(city)s, %(region_name)s", "%(city)s, %(country_name)s"]

    api_key = apikeys["wunderground"]["key"]

    @classmethod
    def guess_location(cls, user):
        if user in cls.locationdata:
            return cls.locationdata["user"]
        elif user in cls.locationhistory:
            return max(cls.locationhistory[user], key=list.count) + ".json"
        elif user in ipscan.known:
            return "autoip.json?geo_ip=" + ipscan.known[user]

    def get_weatherdata(self, user):
        location = self.guess_location(user)
        if location:
            data = "http://api.wunderground.com/api/%s/conditions/q/%s" % (self.api_key, location)
            data = json.loads(urllib.urlopen(data).read())
            data = data["current_observation"]
            station = data["station_id"]
            # Store history.
            self.locationhistory.setdefault("user", []).append(station)
            conditions = {"location"     : data["display_location"]["full"],
                          "time"         : pretty_date(int(data["local_epoch"]) - int(data["observation_epoch"])),
                          "weather"      : data["weather"],
                          "temperature"  : data["temperature_string"],
                          "feels_like"   : data["feelslike_string"],
                          "wind"         : data["wind_string"],
                          "windchill"    : data["windchill_string"],
                          "humidity"     : data["relative_humidity"],
                          "visibility"   : data["visibility_km"],
                          "precipitation": data["precip_today_metric"],
                          "UV"           : data["UV"]
                          }
            format = u"""12%(location)s (%(time)s)                  Wunderground
⎜%(weather)s, %(temperature)s                   Feels like %(feels_like)s⎟
⎜%(wind)s                                       Wind chill %(windchill)s⎟
⎜%(humidity)s humidity, visibility %(visibility)skm, %(precipitation)smm of precipitation. UV Index %(UV)s⎟
⎜Monday:       ⎟""" % conditions
        printer.message(format.encode("utf-8"))