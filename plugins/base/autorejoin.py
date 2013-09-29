def __initialise__(name, bot, stream):
	def autorejoin(line):
		words = line.split()
		if bot.eq(words[3], bot.nick):
			stream.raw_message("JOIN %s" % words[2])
	bot.register("kick", autorejoin)