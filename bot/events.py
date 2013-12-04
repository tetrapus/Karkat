"""
Helper methods for defining event handlers.
"""
import functools
import re
import inspect

from util.irc import Command


# Constants
DIE = "DIE"


class Callback(object):

    __instances__ = []

    ERROR = BaseException
    class InvalidUsage(Exception):
        def __init__(self, msg):
            Exception.__init__("Arguments do not match the usage pattern.")
            self.msg = msg
    USAGE = InvalidUsage

    def __init__(self, server):
        self.__instances__.append(self)

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
            formatter = lambda x: formatter % x
        if issubclass(prefix, Callback.ERROR):
            errors[prefix] = formatter
        else:
            prefixes[prefix] = formatter
    return errors, prefixes


def command(name=None, 
            args=None, 
            prefixes=("!", "@"), 
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
            triggers = [name]
        else:
            triggers = []

        triggers = [i.lower() for i in triggers]

        @functools.wraps(funct)
        def _(*argv) -> "privmsg": 
            try:
                bot = argv[-2]
                msg = Command(argv[-1], bot)
                user = msg.address
            except IndexError:
                return
            else:
                # Check if we're a bound method.
                if len(argv) == 3:
                    fargs = [argv[0], msg]
                else:
                    fargs = [msg]

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
                        if args is not None:
                            try:
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
                                raise Callback.InvalidUsage(bot, msg)
                            else:
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
                        for error in errors:
                            if issubclass(e, error):
                                with output as out:
                                    for line in errors[error]:
                                        out += line
                                break

        return _
    return decorator
