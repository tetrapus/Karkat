import time
from datetime import datetime
import re
import os
import os.path

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, Text, create_engine, Index

from bot.events import Callback, command, msghandler
from util.irc import IRCEvent
from util.database import Database

__depends__ = ["util.database", "util.irc", "bot.events"]

# TODO: Caching
#       Scrollback
#       sed
#       search

# Data model
has_context = ["PART", "NOTICE", "PRIVMSG", "JOIN"]
has_sender = ['NICK', 'QUIT', 'PART', 'NOTICE', 'PRIVMSG', 'JOIN']


Base = declarative_base()

class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)

    timestamp = Column(DateTime, nullable=False)

    type = Column(Text, nullable=False)

    sender = Column(Text)
    sender_nick = Column(Text)
    sender_ident = Column(Text)
    sender_hostmask = Column(Text)

    context = Column(Text)

    payload = Column(Text)
    payload_lower = Column(Text)
    data = Column(Text, nullable=False)

Index("idx_event_trace", Event.type, Event.timestamp)

class LastEventCache(Base):
    __tablename__ = 'last_event_cache'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)

    nick = Column(Text, nullable=False)
    newnick = Column(Text)
    context = Column(Text)
    data = Column(Text, nullable=False)

Index("idx_last_event_cache", LastEventCache.context, LastEventCache.nick, LastEventCache.newnick)

class LastSpokeCache(Base):
    __tablename__ = 'last_spoke_cache'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)

    nick = Column(Text, nullable=False)
    context = Column(Text, nullable=False)
    data = Column(Text, nullable=False)

Index("idx_last_spoke_cache", LastSpokeCache.context, LastSpokeCache.nick)


def strip_prefix(text):
    if text.startswith(":"):
        return text[1:]
    else:
        return text


def make_event(message, timestamp=None, key=str.lower):
    """ Create an Event object from a raw IRC message """

    if timestamp is None:
        timestamp = datetime.utcnow()

    evt = Event(timestamp=timestamp, data=message)

    if not message.startswith(":"):
        # Message has no prefixed origin
        evt.type, evt.payload = message.split(" ", 1)

    else:
        evt.sender, evt.type, args = message[1:].split(" ", 2)

        # Check if the sender is a user
        if "@" in evt.sender:
            nick, rest = evt.sender.split("!", 1)
            evt.sender_nick = key(nick)
            evt.sender_ident, evt.sender_hostmask = rest.split("@", 1)

        # Check if the message has a context
        if evt.type in has_context:
            args = args.split(" ", 1)
            if len(args) > 1:
                context, args = args
            else:
                context = strip_prefix(args[0])
                args = None
            evt.context = key(context)

        evt.payload = args
    if evt.payload is not None:
        evt.payload_lower = key(evt.payload)

    return evt


def abstime(date):
    if date.year == datetime.utcfromtimestamp(time.time()):
        return date.strftime("%B %-d, %H:%M")
    else:
        return date.strftime("%B %-d, %Y")


def timefmt(timestamp):
    timediff = (datetime.utcnow() - timestamp).total_seconds()

    minutes, seconds = divmod(timediff, 60)
    if not minutes:
        return "%d seconds ago" % seconds
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return "%d minutes ago" % minutes
    days, hours = divmod(hours, 24)
    if not days:
        if minutes > (5 + hours):
            return "%d hours %d mins ago" % (hours, minutes)
        else:
            return "%d hours ago" % hours
    if days < 10:
        if hours > days:
            return "%d days %d hours ago" % (days, hours)
        else:
            return "%d days ago" % days
    else:
        return abstime(timestamp)

def msgfmt(evt):
    nick = evt.sender.split("!", 1)[0]
    if evt.payload.startswith(":\x01ACTION ") and evt.payload.endswith("\x01"):
        return "\x0306•\x03 %s %s" % (nick, evt.payload[9:-1])
    elif evt.payload.startswith(":\x01") and evt.payload.endswith("\x01"):
        return "\x0306• CTCP\x03 %s" % (evt.payload[2:-1])
    return "\x0315<\x03%s\x0315>\x03 %s" % (nick, evt.payload[1:])

def noticefmt(evt):
    nick = evt.sender.split("!", 1)[0]
    if evt.payload.startswith(":\x01ACTION ") and evt.payload.endswith("\x01"):
        return "\x0313•\x03 %s %s" % (nick, evt.payload[9:-1])
    elif evt.payload.startswith(":\x01") and evt.payload.endswith("\x01"):
        return "\x0313• NCTCP\x03 %s" % (evt.payload[2:-1])
    return "\x0313-\x03%s\x0313-\x03 %s" % (nick, evt.payload[1:])

def nickfmt(evt):
    nick = evt.sender.split("!", 1)[0]
    return "\x0303•\x03 %s changed their nick to %s" % (nick, evt.payload[1:])

def quitfmt(evt): 
    nick = evt.sender.split("!", 1)[0]
    if evt.payload:
        quitmsg = " (%s)" % evt.payload[1:]
    else:
        quitmsg = ""
    return "\x0307•\x03 %s disconnected%s" % (nick, quitmsg)

def partfmt(evt):
    nick = evt.sender.split("!", 1)[0]
    if evt.payload:
        partmsg = " (%s)" % evt.payload[1:]
    else:
        partmsg = ""
    return "\x0307•\x03 %s left %s%s" % (nick, evt.context, partmsg)

def joinfmt(evt):
    nick = evt.sender.split("!", 1)[0]
    return "\x0303•\x03 %s joined %s" % (nick, evt.context)
            

class Logger(Callback):
    formatters = {"NICK": nickfmt,
                  "QUIT": quitfmt,
                  "PART": partfmt,
                  "NOTICE": noticefmt,
                  "PRIVMSG": msgfmt,
                  "JOIN": joinfmt}

    def __init__(self, server):
        self.lower = server.lower
        self.logpath = server.get_config_dir("log.txt")
        self.dbpath = server.get_config_dir("log.db")
        self.sedchans = set()
        self.db = Database("sqlite:///" + self.dbpath)
        self.db.create_all(Base.metadata)
        if os.path.exists(self.logpath):
            # Perform migration
            self.sql_migrate(lower=server.lower)
            os.rename(self.logpath, self.logpath + ".old")
        # Initialise db and shit
        super().__init__(server)

    def cache_event(self, session, event):
        if event.sender_nick is None:
            return
        cached_event = {
            'timestamp': event.timestamp,
            'nick': event.sender_nick,
            'context': event.context,
            'data': event.data
        }
        if event.type == 'PRIVMSG' and event.context.startswith("#"):
            query = session.query(LastSpokeCache).filter(
                LastSpokeCache.nick == event.sender_nick,
                LastSpokeCache.context == event.context
            )
            if query.count():
                query.update(cached_event)
            else:
                session.add(LastSpokeCache(**cached_event))

        if event.type == 'NICK':
            cached_event['newnick'] = event.payload_lower[1:]
        else:
            cached_event['newnick'] = None

        if event.type in has_sender:
            query = session.query(LastEventCache).filter(
                LastEventCache.nick == event.sender_nick,
                LastEventCache.context == event.context
            )
            if query.count():
                query.update(cached_event)
            else:
                session.add(LastEventCache(**cached_event))


    def sql_migrate(self, logpath=None, lower=str.lower):
        """ Migrate existing logs to the new SQL database """
        if logpath is None:
            logpath = self.logpath
        with open(self.logpath) as logfile:
            with self.db() as session:
                for line in logfile:
                    try:
                        line = line.rstrip("\n").rstrip("\r")
                        timestamp, text = line.split(" ", 1)
                        event = make_event(text, timestamp=datetime.utcfromtimestamp(float(timestamp)))
                        session.add(event)
                        self.cache_event(session, event)
                    except:
                        print("[Logger] Warning: Could not parse %s" % line)
                        raise

    @Callback.background
    @command("log_migrate", "(.+)", admin=True)
    def partial_migration(self, server, message, path):
        self.sql_migrate(logpath=path, lower=server.lower)
        return "Migration complete."

    def traceuser(self, hostmask, timestamp):
        # Load the logs into memory to compute graph
        # FIXME
        start_nick, x = hostmask.split("!", 1)
        start_ident, start_mask = x.split("@", 1)
        userinf = {(start_nick, start_ident, start_mask)}
        with self.db() as session:
            logs = session.query(
                Event
            ).filter(
                Event.type.in_(['NICK', 'JOIN']),
                Event.timestamp >= timestamp,
            ).order_by(Event.timestamp).all()
            for log in logs:
                nick, x = log.sender.split("!", 1)
                ident, mask = x.split("@", 1)
                if log.type == "NICK" and (nick, ident, mask) in userinf:
                    userinf.add((log.payload[1:], ident, mask))
                elif log.type == "JOIN" and any(log.sender_nick == self.lower(n)
                                             or (ident, mask) == (i, m)
                                             for n, i, m in userinf):
                    userinf.add((nick, ident, mask))
        return userinf

    @Callback.inline
    def log(self, server, line) -> "ALL":
        timestamp = datetime.utcnow()
        with self.db() as session:
            event = make_event(line, timestamp=timestamp)
            session.add(event)
            self.cache_event(session, event)
    
    @command("seen lastseen", r"(\S+)")
    def seen(self, server, msg, user):
        if server.eq(user, msg.address.nick):
            return "04⎟ You're right there!"
        context = server.lower(msg.context)
        nick = server.lower(user)
        # Don't allow seen for pms, for confidentiality
        if not context.startswith("#"):
            return

        with self.db() as session:
            #last = session.query(
            #    Event
            #).filter(
            #    Event.type.in_(types),
            #    (Event.context == context) | (Event.context == None),
            #    (Event.sender_nick == nick)
            #    | ((Event.type == 'NICK') & (Event.payload_lower == ":" + nick))
            #).order_by(
            #    Event.timestamp.desc()
            #).first()
            last = session.query(
                LastEventCache
            ).filter(
                (LastEventCache.context == context)
                | (LastEventCache.context == None),
                (LastEventCache.nick == nick)
                | (LastEventCache.newnick == nick)
            ).order_by(
                LastEventCache.timestamp.desc()
            ).first()

            if last is None:
                return "04⎟ I haven't seen %s yet." % user

            event = make_event(last.data, timestamp=last.timestamp, key=server.lower)

            message = self.formatters[event.type](event)
            timestamp = last.timestamp
            host = event.sender

        if server.isIn(user, server.channels.get(context)):
            status = " · \x0312online now"
        else:
            for nick, _, _ in self.traceuser(host, timestamp):
                if server.isIn(nick, server.channels.get(context)):
                    status = " · \x0312online as %s" % nick
                    break
            else:
                status = ""
        return "%s · \x1d%s%s" % (message, timefmt(timestamp), status)

    @command("last lastspoke lastmsg", r"(\S+)")
    def lastspoke(self, server, msg, user):
        if server.eq(user, msg.address.nick):
            return "04⎟ You just spoke!"

        context = server.lower(msg.context)
        nick = server.lower(user)
        # Don't allow seen for pms, for confidentiality
        if not context.startswith("#"):
            return

        with self.db() as session:
            last = session.query(LastSpokeCache).filter(
                LastSpokeCache.context == context,
                LastSpokeCache.nick == nick
            ).first()
            
            if last is None:
                return "04⎟ I haven't seen %s speak yet." % user
                
            event = make_event(last.data, timestamp=last.timestamp)

            return "%s · \x1d%s" % (msgfmt(event), timefmt(last.timestamp))

    @command("sedon", rank="@")
    def sedon(self, server, msg):
        self.sedchans.add(server.lower(msg.context))
        return "04⎟ Turned on sed."

    @command("sedoff", rank="@")
    def sedoff(self, server, msg):
        self.sedchans.remove(server.lower(msg.context))
        return "04⎟ Turned off sed."

#    @msghandler
    def substitute(self, server, msg):
        if not server.isIn(msg.context, self.sedchans):
            return
        match = re.match(r"^(\S+:\s+)?s(\W)(.*?)\2(.*?)(\2g?)?$", msg.text)
        if match:
            target, sep, pattern, sub, flags = match.groups()
            if target is not None: target = target.rstrip(": ")
            if flags is not None: flags = set(flags[1:])
            pattern = re.escape(pattern)
            for timestamp, line in reversed(self.logs):
                # TODO: implement real regular expressions
                # also self-regex
                try:
                    evt = IRCEvent(line)
                    if (evt.type == "PRIVMSG" 
                        and server.eq(msg.context, evt.args[0])
                        and (target is None or server.eq(target, evt.sender.nick))
                        and not re.match(r"^(\S+:\s+)?s(\W)(.*?)\2(.*?)(\2g?)?$", evt.args[1])
                        and re.search(pattern, evt.args[1], flags=re.IGNORECASE)):
                        evt.args[1] = re.sub(pattern, "\x1f%s\x1f" % sub, evt.args[1], count=0 if 'g' in flags else 1, flags=re.IGNORECASE)
                        return msgfmt(evt)
                except:
                    print("[Logger] Warning: Could not parse %s" % line)
            return "04⎟ No matches found."


__initialise__ = Logger