import functools
import re
import inspect

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
        if "#" not in target:
            self.context = self.address.nick
        self.text = message
        self.words = message.split(" ")
        self.message = raw_message


class Command(Message):
    def __init__(self, raw_message, prefixes=None):
        super(Command, self).__init__(raw_message)
        text = self.text.split(" ", 1)
        if prefixes is None:
            self.prefix, self.command = text[0][0], text[0][1:]
        else:
            for i in prefixes:
                if text[0].startswith(i):
                    self.prefix, self.command = i, text[0][len(i):]
                    break
            else:
                self.prefix, self.command = None, text[0]

        if len(text) > 1:
            self.arg = text[1]
            self.argv = text[1].split(" ")
        else:
            self.arg, self.argv = None, None

class Callback(object):
    """ This class defines decorators for callbacks. """
    # TODO: turn into a module.

    @staticmethod
    def threadsafe(funct):
        funct.isThreadsafe = True
        return funct

    @staticmethod
    def inline(funct):
        funct.isInline = True
        return funct

    @staticmethod
    def isInline(funct):
        return hasattr(funct, "isInline") and funct.isInline 
    
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
        def _(server, line):
            word_eol = [line.split(" ", n)[-1] for n in range(line.count(" ") + 1)]
            return funct(line.split(), word_eol)
        return _

    ''' !!DEPRECATED!!
    @staticmethod
    def msghandler(funct):
        """
        A message handler is a callback that responds to lines of the form
            :NICK!USER@HOST METHOD TARGET :DATA
        These callbacks have the function signature
            User, Context, Message
        """
        @functools.wraps(funct)
        def _(*args): 
            message = Message(args[-1])
            fargs = args[:-1] + (message.address, message.context, message)
            return funct(*fargs)
        return _
    '''


def command(triggers, args=None, key=str.lower, usage=None, error=None, admin=False, private=".", public="@"):
    if type(triggers) == str:
        triggers = [triggers]
    triggers = [key(i) for i in triggers]
    def decorator(funct):
        @functools.wraps(funct)
        def _(*argv):
            try:
                message = Command(argv[-1])
                server = argv[-2]
                user = message.address

                if len(argv) == 3:
                    fargs = [argv[0], server, message]
                else:
                    fargs = [server, message]

                # Check admin permissions
                if admin and not server.is_admin(user.hostmask):
                    return

            except IndexError:
                return
            else:
                if message.prefix in private + public and key(message.command) in triggers:
                    # Triggered.
                    # Set up output
                    if message.prefix in private:
                        output = server.printer.buffer(user.nick, "NOTICE")
                    else:
                        output = server.printer.buffer(message.context, "PRIVMSG")

                    # Check arguments
                    if args is not None:
                        try:
                            argument = message.text.split(" ", 1)
                            if len(argument) == 1:
                                argument = ""
                            else:
                                argument = argument[1]
                            if callable(args):
                                fargs.extend(list(args(argument)))
                            else:
                                fargs.extend(list(re.match(args, argument).groups()))
                        except (AttributeError, IndexError):
                            if usage is not None:
                                with output as out:
                                    out += usage
                            return
                    try:
                        if inspect.isgeneratorfunction(funct):
                            with output as out:
                                for line in funct(*fargs):
                                    out += line
                        else:
                            rval = funct(*fargs)
                            if rval is not None:
                                with output as out:
                                    out += rval
                    except NotImplementedError:
                        with output as out:
                            out += "".join("\x03%s\x02 %s " %(("08,01", "01,08")[i%2], v) for i, v in enumerate("🚧 UNDER CONSTRUCTION 🚧")) + "\x03"
                    except BaseException:
                        if error is not None:
                            with output as out:
                                out += error
                        raise
        return _
    return decorator
