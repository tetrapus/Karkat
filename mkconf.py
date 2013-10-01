#! /usr/bin/env python3

import yaml
import os

if not os.path.exists("config/apikeys.conf"):
    print("Warning: No apikeys file found.")

fname = input("Config filename (e.g Freenode.yaml): ")
if "." not in fname:
    fname = fname + ".yaml"

settings = {"Mode": 0}
server = input("Server Address (e.g irc.freenode.net): ")
port = input("Port (default: 6667): ")
settings["Server"] = [server, int(port or 6667)]
settings["Nick"] = [input("Bot Nick (e.g Karkat): ")]
while settings["Nick"][-1]:
    settings["Nick"].append(input(("Backup " * len(settings["Nick"])) 
                            + ("Bot Nick (enter for None): ")))
del settings["Nick"][-1] 

settings["Real Name"] = input("Real Name (default=Nick): ")
if not settings["Real Name"]:
    settings["Real Name"] = settings["Nick"][0]

settings["Username"] = input("Username (default=Nick): ")
if not settings["Username"]:
    settings["Username"] = settings["Nick"][0]

settings["Admins"] = [i.strip() for i in input("Administrators (Comma separated, e.g *@goes.rawr, tetrap.us): ").split(",")]

confidr = input("Configuration Directory (default: /config/Server): ")
if confidr:
    settings["Data"] = confidr

with open(fname, "w") as f:
    f.write(yaml.dump(settings))

print ("Wrote config to " + fname)