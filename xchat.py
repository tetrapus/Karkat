XCHAT_EAT_NONE   = 0   # pass it on through! 
XCHAT_EAT_XCHAT  = 1   # don't let xchat see this event 
XCHAT_EAT_PLUGIN = 2   # don't let other plugins see this event 
XCHAT_EAT_ALL    = (XCHAT_EAT_XCHAT|XCHAT_EAT_PLUGIN)  # don't let anything see this event


class _State:
    def init(self, name, bot, printer):
        self.name = name
        self.bot = bot
        self.printer = printer
        self.context = None

    def prnt(self, string):
        return self.context.prnt(string)

    def emit_print(self, event_name, *args):
        return self.context.emit_print(event_name, *args)

    def command(self, string):
        return self.context.command(string)

    def get_info(self, type):
        return self.context.get_info(type)

    def get_list(self, type):
        return self.context.get_list(type)

_state = _State()

class _Context(object):
    def set(self):
        _state.context = self

    def prnt(self, string):
        print(string) # TODO

    def emit_print(self, event_name, *args):
        print("[%s]" % event_name, args) # TODO

    def command(self, string):
        name, arg = string.split(" ", 1).upper()
        if name in _commands:
            return _commands[name](self, arg)
        elif name in _commandnames:
            raise NotImplementedError
        else:
            _state.bot.raw_message(string)

    def get_info(self, type):
        if type == "away":
            return _state.bot.away

    def get_list(self, type):
        pass

__initialise__ = _state.init
_commandnames = """ADDBUTTON ALLCHAN   ALLCHANL  ALLSERV   AWAY
  BACK      BAN       CHANOPT   CHARSET   CLEAR
  CLOSE     COUNTRY   CTCP      CYCLE     DCC
  DEBUG     DEHOP     DELBUTTON DEOP      DEVOICE
  DISCON    DNS       ECHO      EXEC      EXECCONT
  EXECKILL  EXECSTOP  EXECWRITE FLUSHQ    GATE
  GETFILE   GETINT    GETSTR    GHOST     GUI
  HELP      HOP       ID        IGNORE    INVITE
  JOIN      KICK      KICKBAN   KILLALL   LAGCHECK
  LASTLOG   LIST      LOAD      MDEHOP    MDEOP
  ME        MENU      MKICK     MODE      MOP
  MSG       NAMES     NCTCP     NEWSERVER NICK
  NOTICE    NOTIFY    OP        PART      PING
  QUERY     QUIT      QUOTE     RECONNECT RECV
  SAY       SEND      SERVCHAN  SERVER    SET
  SETCURSOR SETTAB    SETTEXT   SPLAY     TOPIC
  TRAY      UNBAN     UNIGNORE  UNLOAD    URL
  USELECT   USERLIST  VOICE     WALLCHAN  WALLCHOP
  

  ACTION    AME       ANICK     AMSG      BANLIST
  CHAT      DIALOG    DMSG      EXIT      GREP
  J         KILL      LEAVE     M         ONOTICE
  RAW       SERVHELP  SPING     SQUERY    SSLSERVER
  SV        UMODE     UPTIME    VER       VERSION
  WALLOPS   WII


  UNLOAD    RELOADALL UNLOADALL PL_RELOAD RELOAD
  UNLOAD    LOAD      NP        NOHL      UNLOAD
  LOAD      PY        LOAD      RELOADALL SOURCE
  TCL       TIMER""".split()

_commands = {}


prnt = _state.prnt
emit_print =_state.emit_print # TODO: Format this shit yo.
command = _state.command
get_info = _state.get_info
get_list = _state.get_list
get_context = lambda: _state.context

def nickcmp(nick1, nick2):
    return _state.nickcmp(nick1, nick2)
