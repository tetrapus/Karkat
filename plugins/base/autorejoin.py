def initialise(name, bot, stream):
	def autorejoin(line):
		if line.split()[3].lower() == bot.nick.lower():
			stream.raw_message("JOIN %s" % x[2])
	bot.register("kick", autorejoin)
__initialise__ = initialise