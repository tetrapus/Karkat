class _State:
    def init(self, name, bot, printer):
        self.name = name
        self.bot = bot
        self.printer = printer
_state = _State()
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


prnt = print
emit_print = print # TODO: Format this shit yo.
def command(string):
    name, arg = string.split(" ", 1).upper()
    if name in _commands:
        return _commands[name](arg)
    elif name in _commandnames:
        raise NotImplementedError
    else:
        _state.bot.raw_message(string)

def nickcmp(nick1, nick2):
    return _state.nickcmp(nick1, nick2)