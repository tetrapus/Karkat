import re
import traceback

from bot.events import Callback
from util.irc import Message

class Seddable(object):
    def __init__(self, msg):
        message_split = msg.split('s/')[1].split('/')

        replace = message_split[0]
        by = message_split[1]

        self.message = msg
        self.to_replace = replace
        self.by = by
        self.rest = ""
        if not msg.endswith('/'):
            self.rest = message_split[2]

        self.linereq = ''

        if not msg.startswith("s/"):
            ## Probably means it has a line requirement
            self.linereq = msg.split('/')[0]

        if True:
            print("To Replace: %s" % (self.to_replace))
            print("Replace by: %s" % (self.by))
            if self.rest:
                print("Some flags: %s" % (self.rest))
            if self.linereq:
                print("Qualifiers: %s" % (self.linereq))

        if 'g' in self.rest:
            self.global_ = True
        else:
            self.global_ = False

        if 'i' in self.rest:
            self.ignorecase = True
        else:
            self.ignorecase = False

class Sed(Callback):
    def __init__(self, server):
        self.server = server
        self.messages = {}
        super().__init__(server)

    def track(self, server, line) -> "privmsg":
        message = Message(line)
        self.messages.setdefault(server.lower(message.context), {}).setdefault(server.lower(message.address.nick), []).append(message.text)


    def get_message(self, channel, sedregex, nick, qual=None):
        channel = self.server.lower(channel)
        if channel not in self.messages:
            return ""
        if not nick in self.messages[channel]:
            return ""
        for message in self.messages[channel][nick]:
            try:
                if qual:
                    if re.search(sedregex, message) and re.search(qual, message):
                        return message
                else:
                    if re.search(sedregex, message):
                        return message
            except BaseException:
                pass
        return ""

    def check_sed(self, msg):
        """ Check whether a message is a sed request """
        if re.match(r"^(\S+[:,] )?(.+/)?s/.+/.*(/([gi]?){2})?$", msg):
            return True

    def sed(self, server, line) -> "privmsg":
        """ Perform the actual sedding """
        message = Message(line)
        msg = message.text
        if re.match(r"^(\S+[:,] )(.+/)?s/.+/.*(/([gi]?){2})?$", msg):
            # target acquired
            if ':' in msg.split()[0]:
                split_msg = msg.split(':')
            else:
                split_msg = msg.split(",")
            nick = split_msg[0]
            msg = split_msg[1].strip()

        sedmsg = Seddable(msg)
        if sedmsg.linereq:
            to_sed = self.get_message(message.context, sedmsg.to_replace, nick, qual=sedmsg.linereq)
        else:
            to_sed = self.get_message(message.context, sedmsg.to_replace, nick)

        if not to_sed:
            return

        try:
            sedmsg.message = to_sed

            if sedmsg.ignorecase and sedmsg.global_:
                # i option on
                new_msg = re.sub(sedmsg.to_replace, sedmsg.by, sedmsg.message, 
                    flags=re.IGNORECASE)
            elif sedmsg.ignorecase:
                # i and g options on
                new_msg = re.sub(sedmsg.to_replace, sedmsg.by, sedmsg.message, 
                    flags=re.IGNORECASE, count=1)
            elif sedmsg.global_:
                # g option on
                new_msg = re.sub(sedmsg.to_replace, sedmsg.by, sedmsg.message)
            else:
                # no options on
                new_msg = re.sub(sedmsg.to_replace, sedmsg.by, sedmsg.message, 
                    count=1)

            self.track(server, "%s PRIVMSG %s :%s" %(message.address.hostmask, message.context, new_msg))
            server.message("<%s> %s" % (nick, new_msg), message.context)
        except BaseException:
            traceback.print_exc()

__initialise__ = Sed