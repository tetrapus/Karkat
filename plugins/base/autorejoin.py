def __initialise__(name, bot, stream):
	def autorejoin(line):
		words = line.split()
		if words[3].lower() == bot.nick.lower():
			stream.raw_message("JOIN %s" % words[2])
	bot.register("kick", autorejoin)