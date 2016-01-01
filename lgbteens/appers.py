import os
import time
import sqlite3
import requests
import yaml
import json


#from bot.events import command
from util.irc import command

def stime(start, end=-1):
    if end == -1: end = int(time.time())
    diff = end-start
    if diff > 86400: s = "\x02%.2f\x02 days" %(diff/86400,)
    elif diff > 3600: s = "\x02%.2f\x02 hours" %(diff/3600,)
    elif diff > 60: s = "\x02%.2f\x02 minutes" %(diff/60,)
    else: s = "\x02%d\x02 seconds" %(diff,)
    return s

class Apper(object):

    DBFILE = "appers.db"

    def __init__(self, server, ap="f", finish="came", abort="abort"):
        self.db = server.get_config_dir(self.DBFILE)
        if not os.path.exists(self.db):
            os.makedirs(server.get_config_dir(), exist_ok=True)

        self.ap = ap

        # Initialise the db
        self.init_db()

        server.register("privmsg", command(ap+"apquery", "(.+)", admin=True)(self.apquery))
        server.register("privmsg", command([ap+"ap", ap+"apping"])(self.apping))
        server.register("privmsg", command(["i"+finish, ap+"apped"], error="\x02Woah\x02. You need to start %sapping first." % ap)(self.apped))
        server.register("privmsg", command([abort, ap+"apfail"], error="\x02Woah\x02. You weren't %sapping anyway." % ap)(self.apfail))
        server.register("privmsg", command([ap+"aplist", ap+"appers"])(self.aplist))
        server.register("privmsg", command(["last"+ap+"ap", ap+"aphistory"], "(.*)")(self.aphistory))
        server.register("privmsg", command(ap+"apstats", "(.*)")(self.apstats))
        server.register("privmsg", command(ap+"apremove")(self.apremove))
        server.register("privmsg", command(ap+"apedit")(self.apedit))
        server.register("privmsg", command(ap+"apadd")(self.apadd))
        server.register("privmsg", command(ap+"apexport", r"(?:-(json|csv|xml|plaintext|table|yaml)\s+)?(.*)")(self.apexport))

    def init_db(self):
        with sqlite3.connect(self.db) as sql:
            sql.execute('''CREATE TABLE IF NOT EXISTS %sappers (
                    uid INTEGER PRIMARY KEY AUTOINCREMENT,
                    lnick TEXT,
                    host TEXT UNIQUE NOT NULL)''' % self.ap)
            sql.execute('''CREATE TABLE IF NOT EXISTS %saps (
                    fid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER NOT NULL,
                    start INTEGER NOT NULL,
                    end INTEGER NOT NULL)''' % self.ap)

    def apquery(self, server, message, query):
        with sqlite3.connect(self.db) as sql:
            q = sql.execute(query)
            yield "R" + str(q.rowcount)
            for r in q.fetchall():
                yield str(r)    

    def apping(self, server, message):
        addr = message.address
        with sqlite3.connect(self.db) as sql:
            sql.execute("INSERT OR IGNORE INTO %sappers(host) VALUES (?)" % self.ap, (addr.mask,))
            sql.execute("UPDATE %sappers SET lnick=? WHERE host=?" % self.ap, (addr.nick.lower(), addr.mask))
            uid = sql.execute("SELECT uid FROM %sappers WHERE host=?" % self.ap, (addr.mask,)).fetchone()[0]

            sql.execute("DELETE FROM %saps WHERE uid=? AND end = 0" % self.ap, (uid,))
            sql.execute("INSERT INTO %saps(uid, start, end) VALUES (?, ?, 0)" % self.ap, (uid, int(time.time())))
            return "%s: You are now \x02%sapping\x02" % (addr.nick, self.ap)

    def apped(self, server, message):
        addr = message.address
        with sqlite3.connect(self.db) as sql:
            uid = sql.execute("SELECT uid FROM %sappers WHERE host=?" % self.ap, (addr.mask,)).fetchone()[0]
            start, fid = sql.execute("SELECT start,fid FROM %saps WHERE uid=? AND end = 0" % self.ap, (uid,)).fetchall()[-1]
            end = int(time.time())

            sql.execute("UPDATE %saps SET end=? WHERE fid=(?)" % self.ap, (end, fid))
            return "%s: \x02Congratulations\x02. You were %sapping for %s." % (addr.nick, self.ap, stime(start, end))

    def apfail(self, server, message):
        addr = message.address
        with sqlite3.connect(self.db) as sql:
            uid = sql.execute("SELECT uid FROM %sappers WHERE host=?" % self.ap, (addr.mask,)).fetchone()[0]

            sql.execute("DELETE FROM %saps WHERE uid=? AND end = 0" % self.ap, (uid,))
            return "%s: \x02Ouch\x02. Better luck next time." % addr.nick

    def aplist(self, server, message):
        with sqlite3.connect(self.db) as sql:
            slack = 0
            appers = []
            for uid, start in sql.execute("SELECT uid,start FROM %saps WHERE end = 0" % self.ap).fetchall()[::-1]:
                if time.time() - start > 86400:
                    slack += 1
                    continue
                nick = sql.execute("SELECT lnick FROM %sappers WHERE uid=?" % self.ap, (uid,)).fetchone()[0]
                appers.append(nick + " (since %s ago)" % stime(start))
            if slack:
                appers.append("and \x02%d\x02 others..." % slack)
            return ("\x02Currently %sapping\x02: " % self.ap) + (", ".join(appers))

    def aphistory(self, server, message, apper):
        if not apper:
            apper = message.address.nick
        with sqlite3.connect(self.db) as sql:
            try:
                name = apper.lower()
                aps = []
                uid = sql.execute("SELECT uid FROM %sappers WHERE lnick=?" % self.ap, (name,)).fetchone()[0]
                for start, end in sql.execute("SELECT start,end FROM %saps WHERE uid=?" % self.ap, (uid,)).fetchall()[-7:][::-1]:
                    if end == 0:
                        aps.append("\x02currently %sapping\x02 (since %s ago)" % (self.ap, stime(start)))
                    else:
                        aps.append("%s ago for %s" % (stime(end), stime(start, end)))
                return ("\x02%s's last %saps\x02: " % (apper, self.ap)) + (", ".join(aps))
            except Exception:
                return "\x02Woah\x02. /Apparently/ %s doesn't %sap." % (apper, self.ap)

    def apstats(self, server, message, apper):
        if not apper:
            apper = message.address.nick
        with sqlite3.connect(self.db) as sql:
            try:
                name = apper.lower()
                uid = sql.execute("SELECT uid FROM %sappers WHERE lnick=?" % self.ap, (name,)).fetchone()[0]
                times = [c[0] for c in sql.execute("SELECT end-start FROM %saps WHERE uid=? AND end > 0" % self.ap, (uid,)).fetchall()]
                resp = "\x02%s's %sap stats\x02: " % (apper, self.ap)
                aps = len(times)
                stats = [sum(times[:3])/min(3,aps), sum(times[:10])/min(10,aps), sum(times)/aps, max(times)]
                resp += "\x02%s\x02 (avg. of 3), \x02%s\x02 (avg. of 10), \x02%s\x02 (cumulative mean), \x02%s\x02 (longest session)" %tuple([stime(0,t) for t in stats])

                try:
                    times = sql.execute("SELECT start,end FROM %saps WHERE uid=? AND end > 0" % self.ap, (uid,)).fetchall()
                    gaps = []
                    for i in range(len(times)-1):
                        gaps.append(times[i+1][0]-times[i][1])
                    resp += ", \x02%s\x02 (longest no%sap)" %(stime(0,max([t for t in gaps if t < 86400*365*7])),self.ap)
                except:
                    pass
                return resp
            except Exception:
                return "\x02Woah\x02. /Apparently/ %s doesn't %sap." % (apper, self.ap)

    def apremove(self, server, message):
        raise NotImplementedError

    def apedit(self, server, message):
        raise NotImplementedError

    def apadd(self, server, message):
        raise NotImplementedError

    def apexport(self, server, message, fmt, apper):
        if not apper:
            apper = message.address.nick
        with sqlite3.connect(self.db) as sql:
            try:
                name = apper.lower()

                uid = sql.execute("SELECT uid FROM %sappers WHERE lnick=?" % self.ap, (name,)).fetchone()[0]
                times = sql.execute("SELECT fid, start, end FROM %saps WHERE uid=?" % self.ap, (uid,)).fetchall()

                if not fmt:
                    fmt = "xml"

                data = ""
                if fmt == "json":
                    data = json.dumps([{"start": i[1], "end": i[2] if i[2] else None, "id":i[0]} for i in times])
                elif fmt == "csv":
                    for fid, start, end in times:
                        data += str(fid) + "," + str(start) + "," + str(end) + "\r\n"
                elif fmt == "xml":
                    data = "<%saps %sapper=%r id=%r>\r\n" % (self.ap, self.ap, name, uid)
                    for fid, start, end in times:
                        data += "    <%sap id=%r>\r\n" % (self.ap, fid)
                        data += "        <start>%r</start>\r\n" % start
                        if end:
                            data += "        <end>%r</end>\r\n" % end
                        data += "    </%sap>\r\n" % self.ap
                    data += "</%saps>\r\n" % self.ap
                elif fmt == "plaintext":
                    for fid, start, end in times:
                        data += "%d: %sapping from %s to %s, total length %f minutes.\r\n" % (fid, self.ap, time.asctime(time.gmtime(float(start))), time.asctime(time.gmtime(float(end))), (end - start)/60)
                elif fmt == "table":
                    data += "  ID  |  START TIME  |   END TIME   \r\n"
                    data += "------+--------------+--------------\r\n"
                    for fid, start, end in times:
                        data += "%5d | %12d | %12d \r\n" % (fid, start, end)
                elif fmt == "yaml":
                    data = yaml.safe_dump([{"start": i[1], "end": i[2] if i[2] else None, "id":i[0]} for i in times])

                formats = {"yaml":"yaml", "table":"txt", "plaintext":"txt", "xml":"xml", "csv":"csv", "json":"json"}

                postres = requests.post("https://api.github.com/gists", data=json.dumps({"files": {"%s-%saps.%s" % (apper, self.ap, formats[fmt]): {"content": data}}}))
                response = postres.json()
                return "Exported to %s." % response["html_url"]

            except Exception:
                return "No %sap history recorded for %s." % (self.ap, apper)

config = [{"ap":"f", "finish":"came", "abort":"abort"},
          {"ap":"fl", "finish":"landed", "abort":"crash"},
          {"ap":"n", "finish":"woke", "abort":"cantsleep"},
          {"ap":"cr", "finish":"shat", "abort":"clench"},
          {"ap":"", "finish":"compiled", "abort":"segfault"}]

def __initialise__(server):
    global apps
    apps = [Apper(server, **c) for c in config]
