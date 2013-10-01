from threads import Connection as IRCConnection
from utility import *

import re
import threading
import urllib


class Server(object):
    """
    Provides a higher level interface to the IRCConnection threading model.
    """
    
    class Channel(object):
        """
        Represents a channel.
        Each server may register exactly one objective representation of a channel.
        """
    
        channels = {}
        
        class Modes(object):
            """
            Stores a manipulatable representation of a modestring.
            """
        
            rawmap = {346:"I", 348:"e", 367:"b", 386:"q", 388:"a"}
            rawmap_flags = {y:x for x, y in rawmap.iteritems()}     
        
            def __init__(self, format="beIqa,kfL,lj,psmntirRcOAQKVCuzNSMTGHFEB"):
                """
                Creates a modes object for storing and manipulating channel modes.
                
                CHANMODES=A,B,C,D
                    This is a list of channel modes according to 4 types.
                    A = Mode that adds or removes a nick or address to a list. Always has a parameter.
                    B = Mode that changes a setting and always has a parameter.
                    C = Mode that changes a setting and only has a parameter when set.
                    D = Mode that changes a setting and never has a parameter.

                    Note: Modes of type A return the list when there is no parameter present.
                    Note: Some clients assumes that any mode not listed is of type D.
                    Note: Modes in PREFIX are not listed but could be considered type B. 
                
                Private modes supported: Iebaq
                """
                
                self.format = format.split(",")
                
                assert len(self.format) == 4
                
                self.flags = {}
                for i in self.format[0]:
                    self.flags[i] = PrivateList(rawmap_flags[i])
                    
                for i in format.split(",", 1)[1].replace(",",""):
                    self.flags[i] = False
                
                
            def hasArgument(self, mode):
                assert mode.isalpha() and mode in self.flags
                return mode not in self.format[3]
                
            def parseFlagString(self, flags):
                add = True
                flags, arguments = flags.split(" ", 1) if " " in flags else flags, ""
                arguments = arguments.split()
                
                while flags:
                    flag = flags.pop(0)
                    if flag in "+-":
                        add = flag == "+"
                    elif hasArgument(flag):
                        self.flags[i] = add and arguments.pop(0)
                    else:
                        self.flags[i] = add
                assert not arguments
                
            
                
        def __init__(self, name):
        
            self.topic = ""
            self.modes = Modes(settings["CHANMODES"]) # NB: Probably won't work.
            self.users = []
            self.name = name
            self.logs = [] # ???
            self._building = []
            
            self.channels[name] = self
            
        @classmethod
        def getChannel(cls, name):
            name = name.lower()
            matching = [i for i in cls.channels if i.name.lower() == name]
            try:
                return matching[0]
            except IndexError:
                return None
                
        def addUsers(self, users):
            self._building += users
            
        def endUsers(self):
            self.users = list(self._building)
            self._building = []
            

    class User(object):
        """ Represents a single user. """
    
        ial = []
        
        def __init__(self, address, channels=None):
            if not getUser(nick):
                self.nick, self.hostmask = hostmask.split("!", 1)
                self.channels = channels or [] # Only stores common channels.
                self.ial.append(self) 
            # TODO: Send out whois request
            
        @classmethod
        def getUser(cls, nick):
            matching = [i for i in cls.ial if i.nick.lower() == nick.lower()]
            try:
                return matching[0]
            except IndexError:
                return None
    
        
    @property
    def handlers(self):
        return [self.__dict__[i] for i in self.__dict__ if i.startswith("on")]
        
    @property
    def name(self):
        try:
            if self.settings:
                return self.settings["NETWORK"]
        except: pass
        
        return self.connection.server[0]
        
    
    def __init__(self, connection):
        """ Initialise a blank server. """
        ## TODO:
        ## # Support multiple connections
        ## # Thread Safety

        self.connection = connection
        
        self.users = []
        self.channels = {}
        self.settings = {}
    
        
    @EventHandler(Event.NUMERIC)
    def onModeList(self, bot, event):
        """ Handles mode listings """
        raise NotImplementedError
        
    @EventHandler("005")
    def onServerSettings(self, bot, event):
        """ Implements server settings on connect """
        for i in event.arguments:
            if "=" not in i:
                self.settings[i] = True
            else:
                key, value = i.split("=", 1)
                self.settings[key] = value
        
    @EventHandler("353")
    def onNames(self, bot, event):
        raise NotImplementedError
        
    @EventHandler("366")
    def onNamesEOL(self, bot, event):
        """ Commit changes to the channel userlist. """
        Channel.getChannel(event.arguments[-1]).endUsers()
        
    @EventHandler("NICK")
    def onNick(self, bot, event):
        """ Implements nick changes """
        User.getUser(event.nick).nick = event.data
        
    @EventHandler("QUIT")
    def onQuit(self, bot, event):
        """ Implements user removal through quit events """
        user = User.getUser(event.nick)
        for i in user.channels:
            channels.users.remove(user)
        User.ial.remove(user)
        
    @EventHandler("PART")
    def onPart(self, bot, event):
        """ Implements parts """
        User.getUser(event.nick).channels.remove(Channel.getChannel(event.context))
        Channel.getChannel(event.context).users.remove(User.getUser(event.nick))
        
    @EventHandler("TOPIC")
    def onTopic(self, bot, event):
        """ Implements topic monitoring """
        channel = Channel.getChannel(event.context)
        channel.topic = "topic"
        
        

class Translator(object):
    """ Translates a message using Google Translate """
    
    api_key = None
    
    @classmethod
    def translate(cls, data, input="fr", out="en"):
        
        if not api_key:
            raise Exception("API key needed for this service.")
        raise NotImplementedError
        


class Checker(threading.Thread):

    interval = 150
    
    def __init__(self, *args):
    
        self.checking = True
        
        try:
            self.mspaData = open("C:\\Python26\\mspaFile").read()
        except IOError:
            self.mspaData = ""
        self.mspaData = tuple([[i.strip() for i in i.split(" ", 2)] for i in self.mspaData.split("\n") if i.strip()])
        self.mspaFile = open("C:\\Python26\\mspaFile", "w")
        
        threading.Thread.__init__(self, *args)
        
        
    def run(self):
        while self.checking:
            self.ircFormat()
            for _ in xrange(self.interval):
                if self.checking:
                    time.sleep(1)
        self.mspaFile.close()
        print "Stopped checking."
        
        
    def checkMSPA(self):
        try:
            page = urllib.urlopen("http://mspaintadventures.com/").read()
        except:
            return
        results = re.findall("(\d\d/\d\d/\d\d)\s+- <a href=\"(.+?)\">(.+?)</a><br>", page)
        
        if results != self.mspaData:
            self.mspaFile.write("")
            for i in results:
                print >> self.mspaFile, str.join(" ", i)
            
            try:
                index  = results.index(self.mspaData[0])
            except:
                index = None
            
            self.mspaData = results
            return results[:index] if index else results
        
        
    def ircFormat(self):
        x = self.checkMSPA()
        if x:
            message("[ \x0307MSPA Update\x0f )  \x0303%s\x0f [\x1f\x0312http://mspaintadventures.com/%s\x0f\x1f] %s" % (x[-1][-1], x[-1][1], ("and \x0307%s more\x0f" % len(x)) if len(x) - 1 else ""), "#homestuck")
            if "[S]" not in x[-1][1]:
                webbrowser.open_new_tab("http://mspaintadventures.com/"+x[-1][1])
                

