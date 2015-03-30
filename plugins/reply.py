from bot.events import command

@command
def reply(server, msg):
    return server.reply_hook(server, msg.message)

__callbacks__ = {"privmsg": [reply]}