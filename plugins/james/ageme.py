"""
Age Calculator
"""

from bot.events import command, Callback
import datetime
import time


@command('ageme', "(.+)", templates={Callback.USAGE: "USAGE: .ageme day month year [prec] [target]"})
def ageme(bot, msg, arg):
    """ Find exact age of person """

    prec = '16'
    args = arg.split()
    if len(args) == 3:
        (day, month, year) = args
    elif len(args) == 4:
        (day, month, year, prec) = args
    elif len(args) == 5:
        (day, month, year, prec, chan) = args
    else:
        raise Callback.InvalidUsage()

    try:
        int(month)
    except ValueError:
        if len(month) > 2 and month[:3].lower() in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]:
            month = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(month[:3].lower())+1
    try:
        int(prec)
        if int(prec) > 200 or int(prec) < 0:
            raise ValueError
    except ValueError:
        raise Callback.InvalidUsage()

    try:
        age = ("%." + prec + "f") % ((time.time() - time.mktime(datetime.date(int(year), int(month), int(day)).timetuple())) / (60 * 60 * 24 * 365.242))
    except:
        return "04│ Error parsing date. Are you american?"

    return "15│ %s years old" % age

__callbacks__ = {"privmsg": [ageme]}
