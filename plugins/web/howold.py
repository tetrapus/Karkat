import json
import requests

from bot.events import command

display_attrs = {"male": (12, "👶👦👨👴"),
                 "female": (13, "👶👧👩👵")}

def how_old(url): 
    string = requests.post("http://how-old.net/Home/Analyze", params={"faceUrl": url, "faceName": "null", "isTest": "False"}).json()
    # Yes, it's double json'd.
    return json.loads(string)["Faces"]

def format_result(attr):
    color, faces = display_attrs[attr["gender"]]
    age_ranges = [5, 16, 45]
    face = 0
    for age in age_ranges:
        if age >= attr["age"]:
            break
        face += 1
    return "\x03%d%s %s\x03" % (color, faces[face], attr["age"])

@command("age", r"(.+)")
def age(server, msg, url):
    try:
        ages = how_old(url)
    except:
        return "04│ 💁 │\x03 Invalid URL."

    if len(ages) == 0:
        return "04│ 💁 │\x03 No faces detected."

    ages = [i["attributes"] for i in sorted(ages, key=lambda x:x['faceRectangle']['left'])]
    return "07│\x03 "+ (" · ".join(format_result(i) for i in ages))

__callbacks__ = {"privmsg": age}