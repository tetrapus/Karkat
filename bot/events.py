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
        self.stream = server.stream
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
                raise Warning("Callback.register mutilates function annotations, but an annotation is already defined.")
            funct.__annotations__["return"] = hooks
            return funct
        return decorator

    @staticmethod
    def splitTemplates(templates):
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


    @staticmethod
    def command(name=None, args=None, prefixes=("!", "@"), templates=None, admin=None):
        if callable(name):
            # Used with no arguments.
            return Callback.command(name.__name__)(name) 

        def decorator(funct):
            if name is None:
                triggers = [funct.__name__]
            elif type(name) == str:
                triggers = [name]
            else:
                triggers = []

            triggers = [i.lower() for i in triggers]

            private, public = prefixes
            prefixes = "".join(prefixes)

            errors, templates = Callback.splitTemplates(templates)

            @functools.wraps(funct)
            def _(*argv) -> "privmsg": 
                try:
                    server = argv[-2]
                    message = Command(argv[-1], server)
                    user = message.address

                    # Check if we're a bound method.
                    if len(argv) == 3:
                        fargs = [argv[0], message]
                    else:
                        fargs = [message]

                    # Check admin permissions
                    if admin is not None and server.is_admin(user.hostmask) != admin:
                        return

                except IndexError:
                    return

                else:
                    if message.prefix in prefixes and message.command.lower() in triggers:
                        # Triggered.
                        # Set up output
                        if message.prefix in private:
                            output = server.printer.buffer(user.nick, "NOTICE")
                        else:
                            output = server.printer.buffer(message.context, "PRIVMSG")

                        # Check arguments
                        try:
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
                                    raise InvalidUsage(server, message)
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
                        except Callback.ERROR as e:
                            for error in errors:
                                if issubclass(e, error):
                                    template = errors[error]
                                    break
            return _
        return decorator