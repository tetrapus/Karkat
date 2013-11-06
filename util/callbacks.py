def threadsafe(funct):
    funct.isThreadsafe = True
    return funct

def inline(funct):
    funct.isInline = True
    return funct

def isInline(funct):
    return hasattr(funct, "isInline") and funct.isInline 

def isThreadsafe(funct):
    return hasattr(funct, "isThreadsafe") and funct.isThreadsafe

def background(funct):
    funct.isBackground = True
    return funct

def isBackground(funct):
    return hasattr(funct, "isBackground") and funct.isBackground

def xchat(funct):
    """
    Generates the xchat version of funct's args.
    """
    @functools.wraps(funct)
    def _(server, line):
        word_eol = [line.split(" ", n)[-1] for n in range(line.count(" ") + 1)]
        return funct(line.split(), word_eol)
    return _

'''
!! DEPRECATED
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

def command(triggers, args=None, admin=False, private=".", public="@", templates=None, key=str.lower):
    if type(triggers) == str:
        triggers = [triggers]
    triggers = [key(i) for i in triggers]
    def decorator(funct):
        @functools.wraps(funct)
        def _(*argv) -> "privmsg": # (): # sublime text highlight fix
            try:
                message = Command(argv[-1])
                user = message.address
                server = argv[-2]
                fargs = [argv[0], message]
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
                    except:
                        if error is not None:
                            with output as out:
                                out += error
                        raise
        return _
    return decorator

class Callback(object):
    def __init__(self):
        self.callbacks = {}
        self.server = None
        self.stream = None
        self.id = None

    def initialise(self, server):
        self.server = server
        self.stream = server.printer
        self.id = server.name
        server.register_all(self.callbacks)