import sys

from util.irc import Message, Callback


class Allbots:
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.sendline(pref + (" ".join(data)))
    def __getattr__(self, d):
        return Allbots(self.bots, self.args + " " + d)

class Interpreter(object):
    def __init__(self, name, bot, stream):
        self.curcmd = []
        self.codeReact = 0
        self.stream = stream
        self.bot = bot
        self.namespace = {"server": bot, "printer": stream, "print": stream.message, "karkat": Allbots([bot]), "main":__import__("__main__")}
        self.namespace.update(sys.modules)
        bot.register("privmsg", self.trigger)

    @Callback.inline
    def trigger(self, line):
        msg = Message(line)
        args = msg.text.split(" ", 1)
        if self.bot.is_admin(msg.address.hostmask):
            # TODO: modify passed in namespace's stdout.
            evaluate = False
            if msg.text == ("%s, undo" % self.bot.nick):
                # Delete the last command off the buffer
                self.curcmd.pop()
                self.stream.message("oh, sure", Message(line).context)
            elif self.codeReact:
                # Code is being added to the buffer.
                # Keep building
                if '"""' in msg.text:
                    # Is the end of the input somewhere in the text?
                    self.codeReact = 0
                    evaluate = True
                self.curcmd.append(msg.text.split('"""', 1)[0])
                
            elif '"""' in msg.text:
                # Enable code building.
                #TODO: Generalise
                self.codeReact = 1
                act = msg.text.split('"""', 1)[-1]
                if act:
                    self.curcmd = [act]

            elif args[0] == ">>>":
                try:
                    act = args[1]
                except IndexError:
                    act = ""
                if act and (act[-1] in "\\:" or act[0] in " \t@"):
                    self.curcmd += [act[:-1]] if act[-1] == "\\" else [act]
                else:
                    self.curcmd.append(act)
                    evaluate = True
            if evaluate:
                code = "\n".join(self.curcmd)#"\n".join([re.sub("\x02(.+?)(\x02|\x0f|$)", "self.stream.message(\\1, %r)" % msg.context, i) for i in self.curcmd])
                print("-------- Executing code --------")
                print(code)
                print("--------------------------------")
                try: 
                    assert "\n" not in code
                    output = eval(code, self.namespace)
                    if output != None: 
                        self.stream.message(str(output), msg.context)
                except:
                    try:
                        exec(code, self.namespace)
                    except BaseException as e:
                        self.stream.message("\x02「\x02\x0305 oh wow\x0307 \x0315%s \x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e), msg.context)
                self.curcmd = []

__initialise__ = Interpreter