"""
Helper methods for defining event handlers.
"""
import functools
import re
import inspect
import sys
import traceback

from util.irc import Command


# Constants
DIE = "DIE"


class Callback(object):

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
    

    ERROR = Exception
    class InvalidUsage(BaseException):
        def __init__(self, msg):
            BaseException.__init__(self, "Arguments do not match the usage pattern.")
            self.msg = msg
    USAGE = InvalidUsage

    def __init__(self, server):
        if "__instances__" not in dir(self.__class__):
            self.__class__.__instances__ = [self]
        else:
            self.__class__.__instances__.append(self)

        self.server = server
        self.printer = server.printer
        self.server_name = server.name

        # Figure out all the hooks
        hooks = {}

        for attr in dir(self):
            try:
                val = getattr(self, attr)
                annotations = getattr(val, "__annotations__")
                if "return" in annotations:
                    hooks.setdefault(annotations["return"], []).append(val)
            except AttributeError:
                pass

        if not hasattr(self, "__callbacks__"):
            self.__callbacks__ = {}

        for trigger in hooks:
            self.__callbacks__.setdefault(trigger, []).extend(hooks[trigger])

        server.register_all(self.__callbacks__)

    @staticmethod
    def hook(*hooks):
        def decorator(funct):
            if "return" in funct.__annotations__:
                raise Warning("Callback.register mutilates function annotations"
                              ", but an annotation is already defined.")
            funct.__annotations__["return"] = hooks
            return funct
        return decorator

def split_templates(templates):
    errors, prefixes = {}, {}

    if templates is None: 
        return errors, prefixes

    for prefix in templates:
        formatter = templates[prefix]
        if not callable(formatter):
            formatter = formatter.format
        if str(prefix) == prefix:
            prefixes[prefix] = formatter
        else:
            errors[prefix] = formatter

    return errors, prefixes

def template(prefixes, errors):
    pass


def command(name=None, 
            args=None, 
            prefixes=("!", "@."), 
            templates=None, 
            admin=None):
    if callable(name):
        # Used with no arguments.
        return command(name.__name__)(name) 
    private, public = prefixes
    prefixes = private + public
    errors, templates = split_templates(templates)

    def decorator(funct):
        if name is None:
            triggers = [funct.__name__]
        elif type(name) == str:
            triggers = name.split()
        else:
            triggers = name

        triggers = [i.lower() for i in triggers]

        #TODO: Parse docstring as templates

        @functools.wraps(funct)
        def _(*argv): 
            try:
                bot = argv[-2]
                msg = Command(argv[-1])
                user = msg.address
            except IndexError:
                return
            else:
                # Check if we're a bound method.
                if len(argv) == 3:
                    fargs = [argv[0], bot, msg]
                else:
                    fargs = [bot, msg]

                # Check admin permissions
                if not (admin is None or bot.is_admin(user.hostmask) == admin):
                    return

                if msg.prefix in prefixes and msg.command.lower() in triggers:
                    # Triggered.
                    # Set up output
                    if msg.prefix in private:
                        output = bot.printer.buffer(user.nick, "NOTICE")
                    else:
                        output = bot.printer.buffer(msg.context, "PRIVMSG")
                    # Check arguments
                    try:
                        try:
                            if args is not None:
                                arg = msg.text.split(" ", 1)
                                if len(arg) == 1:
                                    arg = ""
                                else:
                                    arg = arg[1]
                                if callable(args):
                                    fargs.extend(list(args(arg)))
                                else:
                                    fargs.extend(re.match(args, arg).groups())
                        except (AttributeError, IndexError):
                            print(errors.keys())
                            raise Callback.InvalidUsage(msg)
                        else:
                            # TODO: implement templates
                            if inspect.isgeneratorfunction(funct):
                                with output as out:
                                    for line in funct(*fargs):
                                        out += line
                            else:
                                rval = funct(*fargs)
                                if rval is not None:
                                    with output as out:
                                        out += rval
                    except tuple(errors.keys()) as e:
                        if "-d" in sys.argv:
                            traceback.print_exc()
                        for error in errors:
                            if issubclass(e.__class__, error):
                                with output as out:
                                    out += errors[error](e)
                                break
        _.__annotations__["return"] = "privmsg"
        return _
    return decorator