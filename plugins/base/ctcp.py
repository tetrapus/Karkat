import os
import yaml

from irc import Message

REPLYFILE = "ctcp.yaml"

def __initialise__(name, bot, stream):
	replies = {}
	if os.path.exists(REPLYFILE):
		replies.update(yaml.safe_load(REPLYFILE))
	conf = os.path.join("config", name, REPLYFILE)
	if os.path.exists(conf):
		replies.update(yaml.safe_load(conf))
	replies = {key.upper(): value for key, value in replies.items()}

	def ctcpreply(line):
		msg = Message(line)
		text = msg.text
		if len(text) > 1 and text[0] == text[-1] == "\x01":
			text = text[1:-1].split(" ")
			command = text[0].upper()
			if command in replies:
				stream.message("\x01%s %s\x01" % (command, replies[command].format(text.split())), msg.context, "NOTICE")

	bot.register("privmsg", ctcpreply)