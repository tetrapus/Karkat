import functools


class Address(object):
    def __init__(self, addr):
        self.nick, self.ident, self.mask = (
            addr[ : addr.find( "!" ) ][ 1 : ],
            addr.split( "@" )[ 0 ][ addr.find( "!" )+1 : ],
            addr.split( "@" )[ 1 ]
           )
        self.hostmask = addr


class Message(object):
    def __init__(self, raw_message):
        address, method, target, message = raw_message.split(" ", 3)
        message = message[1:]
        self.address = Address(address)
        self.method = method
        self.context = target
        if not target.startswith("#"):
            self.context = self.address.nick
        self.text = message
        self.message = raw_message


class Command(Message):
    def __init__(self, raw_message):
        super(Command, self).__init__(raw_message)
        command = self.text.split(" ", 1)[0]
        self.prefix, self.command = command[0], command[1:]

class Callback(object):
    @staticmethod
    def threadsafe(funct):
        funct.isThreadsafe = True
        return funct
    
    @staticmethod
    def isThreadsafe(funct):
        return hasattr(funct, "isThreadsafe") and funct.isThreadsafe
    
    @staticmethod
    def background(funct):
        funct.isBackground = True
        return funct
    
    @staticmethod
    def isBackground(funct):
        return hasattr(funct, "isBackground") and funct.isBackground

    @staticmethod
    def xchat(funct):
        """
        Generates the xchat version of funct's args.
        """
        @functools.wraps(funct)
        def _(words, line):
            word_eol = [line.split(" ", n)[-1] for n in range(line.count(" ") + 1)]
            return funct(words, word_eol)
        return _

    @staticmethod
    def msghandler(funct):
        """
        A message handler is a callback that responds to lines of the form
            :NICK!USER@HOST METHOD TARGET :DATA
        These callbacks have the function signature
            User, Context, Message
        """
        @functools.wraps(funct)
        def _(words, line):
            user = Address(words[0])
            message = Message(line)
            return funct(user, words[2], message) # TODO: actually make these fucking classes
        return _