"""
Interprets python statements.
"""

import sys
import subprocess
import shlex
import re

from util.irc import Message, Callback


class Pipeline(object):
    def __init__(self, descriptor=None):
        self.steps = []
        if descriptor:
            for step in descriptor.split("|"):
                self.add(step.strip())

    def __repr__(self):
        return " | ".join(self.steps)

    def add(self, step, pos=None):
        if pos:
            self.steps.insert(pos, step)
        else:
            self.steps.append(step)
            pos = len(self.steps) - 1
        return pos

    # syntactic sugar
    def __or__(self, step):
        self.add(step)
        return self

    def remove(self, pos):
        del self.steps[pos]

    def run(self):
        procs = {}
        procs[0] = subprocess.Popen(shlex.split(self.steps[0]), stdout=subprocess.PIPE)
        if len(self.steps) > 1:
            i = 1
            for p in self.steps[1:]:
                procs[i] = subprocess.Popen(shlex.split(p), stdin=procs[i-1].stdout, stdout=subprocess.PIPE)
                procs[i-1].stdout.close()
        output = procs[len(procs) - 1].communicate()[0]
        return output.decode("utf-8")


class PipelineWithSubstitutions(Pipeline):
    def __init__(self, descriptor=None, substitutions=None):
        Pipeline.__init__(self, descriptor)
        self.substitutions = substitutions

    def add(self, step, pos=None):
        for sub in self.substitutions:
            step = re.sub(sub, self.substitutions[sub], step)
        Pipeline.add(self, step, pos)
        

class VolatilePipeline(Pipeline):
    def __repr__(self):
        return self.run()
        
class PipeWrapper(object):
    def __sub__(self, thing):
        pipe = VolatilePipeline()
        pipe.add(thing)
        return pipe

    def __lshift__(self, thing):
        return self.__sub__(thing)
        
run = PipeWrapper()

# Magic interpretter objects
class Allbots(object):
    """ Construct IRC messages from python dot syntax. """
    def __init__(self, bots, args = ""):
        self.bots = bots
        self.args = args
    def __call__(self, *data):
        pref = self.args + (" " * bool(self.args))
        for i in self.bots:
            i.sendline(pref + (" ".join(data)))
    def __getattr__(self, word):
        return Allbots(self.bots, self.args + " " + word)

class NamespaceStack(object):

    @property
    def globals(self):
        return self.namespace[0]

    @property
    def locals(self):
        return self.namespace[-1] if len(self.namespace) > 1 else None

    def __init__(self, default):
        self.namespace = [default]

    def push(self, obj):
        if type(obj) == dict:
            namespace = obj
        else:
            namespace = obj.__dict__

        self.namespace.append(namespace)
        if "__name__" in namespace:
            return "Namespace set to `%s`." % namespace["__name__"]
        else:
            return "Namespace set."

    def pop(self):
        if len(self.namespace) > 1:
            self.namespace.pop()
            if "__name__" in self.namespace[-1]:
                return "Namespace reset to `%s`." % self.namespace[-1]["__name__"]
            elif len(self.namespace) == 1:
                return "Using default namespace."
            else:
                return "Namespace reset."
        return "Already using default namespace."

    def __str__(self):
        return self.pop()

    def __lshift__(self, obj):
        return self.push(obj)


class Interpreter(object):
    """ Builds chunks of python code to execute. """

    def __init__(self, server):
        self.curcmd = []
        self.last = None
        self.building = 0
        self.namespace = {"server": server, 
                          "printer": server.printer, 
                          "print": server.printer.message, 
                          "karkat": Allbots([server]), 
                          "main":__import__("__main__"),
                          "run": run}
        self.namespace.update(sys.modules)
        self.namespace = NamespaceStack(self.namespace)
        server.register("privmsg", self.trigger)

    def get_stdout(self, server, target):
        def message(text):
            server.printer.message(text, target)
        return message

    @Callback.inline
    def trigger(self, server, line):
        msg = Message(line)
        args = msg.text.split(" ", 1)
        if server.is_admin(msg.address.hostmask):
            self.namespace.globals["print"] = self.get_stdout(server, msg.context)
            self.namespace.globals["_"] = self.last
            self.namespace.globals["namespace"] = self.namespace
            self.namespace.globals["pop"] = self.namespace
            evaluate = False
            if msg.text == ("%s, undo" % server.nick):
                # Delete the last command off the buffer
                self.curcmd.pop()
                server.printer.message("oh, sure", Message(line).context)
            elif self.building:
                # Code is being added to the buffer.
                # Keep building
                if '"""' in msg.text:
                    # Is the end of the input somewhere in the text?
                    self.building = 0
                    evaluate = True
                self.curcmd.append(msg.text.split('"""', 1)[0])
                
            elif '"""' in msg.text:
                # Enable code building.
                #TODO: Generalise
                self.building = 1
                act = msg.text.split('"""', 1)[-1]
                if act:
                    self.curcmd = [act]

            elif args[0].endswith(">>>") and args[0][:-3] in ["", server.nick]:
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
                code = "\n".join(self.curcmd)
                print("-------- Executing code --------")
                print(code)
                print("--------------------------------")
                try: 
                    assert "\n" not in code
                    output = eval(code, self.namespace.globals, self.namespace.locals)
                    if type(output) in [map, filter]:
                        output = list(output)
                    self.last = output
                    if output != None: 
                        server.printer.message(str(output), msg.context)
                except BaseException:
                    try:
                        exec(code, self.namespace.globals, self.namespace.locals)
                    except BaseException as err:
                        # TODO: Clean this.
                        server.printer.message(
                            "\x02「\x02\x0305 "
                            "oh wow"
                            "\x0307 \x0315%s \x03\x02」\x02 "
                            % (repr(err)[:repr(err).find("(")]) + str(err), 
                               msg.context)
                self.curcmd = []

__initialise__ = Interpreter
