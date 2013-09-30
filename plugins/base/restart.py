from irc import Callback

def __initialise__(name, bot, printer):
    cb = Callback()
    cb.initialise(name, bot, printer)
    @cb.command("restart", public=":", private="", admin=True)
    def set_restart(message):
        bot.restart = True
        printer.raw_message("QUIT :Restarting...")
    bot.register("privmsg", set_restart)