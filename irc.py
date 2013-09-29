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
        if not target.startswith("#"):
            self.context = self.address.nick
        self.text = message
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
        def _(line):
            word_eol = [line.split(" ", n)[-1] for n in range(line.count(" ") + 1)]
            return funct(line.split(), word_eol)
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
        def _(*args): 
            message = Message(args[-1])
            fargs = args[:-1] + (message.address, message.context, message)
            return funct(*fargs)
        return _

    def initialise(self, name, bot, printer):
        self.stream = printer
        self.bot = bot
        self.id = name


    def command(self, triggers, args=None, key=str.lower, usage=None, error=None, admin=False, private=".", public="@"):
        if type(triggers) == str:
            triggers = [triggers]
        triggers = [key(i) for i in triggers]
        def decorator(funct):
            @functools.wraps(funct)
            def _(*argv):
                try:
                    message = Command(argv[-1])
                    user = message.address

                    # Check admin permissions
                    if admin and not self.bot.isAdmin(user.hostmask):
                        return

                    if len(argv) == 2:
                        fargs = [argv[0], message]
                    else:
                        fargs = [message]
                except IndexError:
                    return
                else:
                    if message.prefix in private + public and key(message.command) in triggers:
                        # Triggered.
                        # Set up output
                        if message.prefix in private:
                            output = self.stream.buffer(user.nick, "NOTICE")
                        else:
                            output = self.stream.buffer(message.context, "PRIVMSG")

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


'''
    def command(self, 
                name=None,
                args=None, 
                triggers=(".", "@"), 
                usage=None,
                usage_prompt="",
                error=None,
                error_prompt="",
                admin=False,
                key=str.lower):
        """
        Helper function for easy creation of common command-related options.
        A command is defined as anything with the following syntactic structure:
        [triggers]name args
        Arguments:
            name: A string or a list of strings representing the string used to identify the command to the user.
            args: A regular expression consisting of groups matching the function signature of the wrapped function.
            triggers: A 2-tuple of strings or lists of strings describing the trigger characters for the function.
                      triggers[0] is private, triggers[1] is public.
            usage: NotImplemented: If true, will autogenerate a usage message for invalid argument values. 
                   If a string, will show this instead.
            usage_prompt: A prompt which will be prepended to the usage message.
            error: If true, will autogenerate an error message for errors raised by the wrapped function. 
                   If a string, will show this instead. 
                   If a dict, will use whichever error is raised, else None key if exists.
            error_prompt: A prompt which will be prepended to the error message.
            admin: If true, only enable command for admins.
            key: Comparison key for the name string. Usually set to str.lower for case insensitivity.
        """
        # Check if this is the top-level decorator
        if callable(name): # name is the function we're wrapping
            return self.command(name.__name__)(name)

        def decorator(funct):
            # Process arguments at "compile" time
            if name is None:
                triggertext = [funct.__name__]
            elif type(name) == str:
                triggertext = [name]
            else:
                triggertext = name
            triggertext = [key(i) for i in triggertext]

            private, public = [[i] if type(i) == str else i for i in triggers]
            alltriggers = set(private + public)
            # Calculate usage message
            if usage is not None:
                if usage == True:
                    # Calculate trigger text
                    if len(alltriggers) == 1:
                        rtrigger = list(alltriggers)[0]
                    elif all(len(x) == 1 for x in alltriggers):
                        rtrigger = "[%s]" % ("".join(alltriggers))
                    else:
                        rtrigger = "(%s)" % ("|".join(alltriggers))

                    if len(triggertext) == 1:
                        rname = triggertext[0]
                    else:
                        rname = "(%s)" % ("|".join(triggertext))

                    if args is not None:
                        pass # Calculate args from function signature
                    else:
                        rargs = ""
                    usagetext = " Usage: %s%s%s" % (rtrigger, rname)
                else:
                    usagetext = usage
                # Prepend prompt
                usagetext = "%s%s" % (usage_prompt, usagetext)
            else:
                usagetext = None

            # Calculate error message
            if error is not None:
                errortext = "%s%s" % (error_prompt, error)

            @functools.wraps(funct)
            def _(*argv):
                try:
                    message = Command(argv[-1], prefixes=alltriggers)
                    user = message.address

                    # Check admin permissions
                    if admin and not self.bot.isAdmin(user.hostmask):
                        print(user.hostmask)
                        return

                    # If we're given a self, use it
                    if len(argv) == 2:
                        fargs = [argv[0], message]
                    else:
                        fargs = [message]

                except IndexError:
                    # Not a command.
                    return
                else:
                    if message.prefix in alltriggers and key(message.command) in triggertext:
                        # Triggered.
                        # Set up output
                        if message.prefix in private:
                            output = self.stream.buffer(user.nick, "NOTICE")
                        else:
                            output = self.stream.buffer(message.context, "PRIVMSG")

                        # Check arguments
                        if args is not None:
                            try:
                                argument = message.arg or ""
                                fargs.extend(list(re.match(args, argument).groups()))
                            except (AttributeError, IndexError):
                                if usage is not None:
                                    with output as out:
                                        out += usagetext
                                return
                        try:
                            rval = funct(*fargs)
                            with output as out:
                                if rval is None:
                                    pass
                                elif type(rval) == str:
                                    out += rval
                                else:
                                    # Assume iterable
                                    for i in rval:
                                        out += rval
                        except:
                            if error is not None:
                                if error == True:
                                    error_data = sys.exc_info()[:2]
                                    errortext = "%s%s: %s" % (error_prompt, error_data[0], error_data[1])
                                with output as out:
                                    out += errortext
                            else:
                                raise
            return _
        return decorator
'''