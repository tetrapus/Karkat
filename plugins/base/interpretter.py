import re

from irc import Message

class Interpretter(object):
    def __init__(self, name, bot, stream):
        self.curcmd = []
        self.codeReact = 0
        self.stream = stream
        self.bot = bot
        bot.register("privmsg", self.trigger)

    def trigger(self, line):
        msg = Message(line)
        args = msg.text.split(" ", 1)
        if msg.address.mask in self.bot.admins:
            # TODO: modify passed in namespace's stdout.
            msgdata = Message(line)
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
                self.curcmd.append(data[1:].split('"""', 1)[0])
                
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
                code = "\n".join([re.sub("\x02(.+?)(\x02|\x0f|$)", "self.stream.message(\\1, %r)" % msg.context, i) for i in self.curcmd])
                print("-------- Executing code --------")
                print(code)
                print("--------------------------------")
                try: 
                    assert "\n" not in code
                    output = eval(code, globals())
                    if output != None: 
                        self.stream.message(str(output))
                except:
                    try:
                        exec(code, globals())
                    except BaseException as e:
                        self.stream.message("\x02「\x02\x0305 oh wow\x0307 \x0315%s \x03\x02」\x02 "%(repr(e)[:repr(e).find("(")]) + str(e))
                self.curcmd = []

__initialise__ = Interpretter