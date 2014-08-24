import requests
import re
import math
from PIL import Image
from io import BytesIO

from bot.events import command, Callback, msghandler
from util.services import url
from util.text import unescape
from util.images import irc_render, draw_braille

exceptions = {Callback.USAGE: "12Google Images│ "\
                              "Usage: .image [-NUM_RESULTS] <query>",
              Callback.ERROR: "04Google Images│ "\
                              "Error: Could not fetch google image results."}


templates = {'@': "%(color).2d│ 02%(title)s · %(content)s\n"\
                  "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s",
             '.': "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s",
             '!': "%(color).2d│ 12↗ %(url)s · %(width)s×%(height)s · 03%(fullurl)s"}

maxlines = {'@': 1,
            '.': 4,
            '!': 6}
deflines = {'@': 1,
            '.': 1,
            '!': 4}


colors = {(88, 54, 149): '\x032,4▓', (71, 142, 124): '\x0311,15▓', (42, 140, 42): '\x0f\x033█', (207, 194, 169): '\x030,8▓', (63, 114, 63): '\x033,6▓', (10, 35, 10): '\x031,3▓', (204, 204, 204): '\x0f\x030█', (203, 79, 53): '\x035,8▓', (57, 118, 39): '\x033,7▓', (56, 101, 101): '\x0310,15▓', (168, 204, 168): '\x030,9▓', (68, 142, 68): '\x033,15▓', (176, 55, 176): '\x0f\x0313█', (169, 78, 169): '\x0313,15▓', (190, 58, 88): '\x034,13▓', (113, 45, 152): '\x036,12▓', (150, 70, 111): '\x036,8▓', (6, 21, 21): '\x031,10▓', (164, 88, 52): '\x035,9▓', (190, 190, 190): '\x030,15▓', (174, 159, 77): '\x038,11▓', (149, 149, 149): '\x0f\x0315█', (206, 138, 92): '\x038,13▓', (153, 153, 153): '\x030,1▓', (44, 13, 44): '\x031,13▓', (63, 170, 103): '\x039,12▓', (102, 49, 116): '\x036,10▓', (32, 9, 31): '\x031,6▓', (89, 52, 146): '\x032,5▓', (65, 53, 142): '\x032,7▓', (199, 50, 50): '\x0f\x035█', (185, 162, 184): '\x030,6▓', (50, 74, 144): '\x032,3▓', (36, 81, 121): '\x0310,12▓', (57, 188, 74): '\x039,11▓', (171, 57, 52): '\x034,7▓', (43, 140, 60): '\x033,11▓', (51, 74, 163): '\x032,11▓', (25, 13, 7): '\x031,7▓', (17, 17, 57): '\x031,12▓', (166, 54, 95): '\x035,12▓', (53, 53, 179): '\x0f\x032█', (151, 60, 151): '\x0313,14▓', (197, 166, 197): '\x030,13▓', (172, 172, 172): '\x030,14▓', (88, 75, 52): '\x037,11▓', (178, 53, 76): '\x034,6▓', (181, 143, 67): '\x038,14▓', (48, 14, 14): '\x031,4▓', (54, 41, 16): '\x031,8▓', (83, 53, 178): '\x032,13▓', (95, 59, 42): '\x037,14▓', (62, 77, 107): '\x0310,13▓', (77, 77, 171): '\x032,15▓', (89, 89, 209): '\x0312,15▓', (157, 79, 73): '\x034,11▓', (195, 59, 59): '\x0f\x034█', (115, 47, 114): '\x036,14▓', (163, 61, 101): '\x034,12▓', (196, 56, 56): '\x034,5▓', (51, 122, 144): '\x0311,12▓', (180, 141, 106): '\x038,12▓', (178, 175, 64): '\x038,9▓', (111, 79, 110): '\x036,9▓', (164, 188, 182): '\x030,11▓', (155, 58, 58): '\x035,10▓', (37, 82, 82): '\x0310,14▓', (217, 166, 65): '\x0f\x038█', (30, 98, 92): '\x0310,11▓', (52, 174, 67): '\x039,10▓', (152, 65, 65): '\x034,10▓', (163, 188, 163): '\x030,3▓', (89, 166, 89): '\x039,13▓', (55, 90, 149): '\x032,9▓', (49, 12, 12): '\x031,5▓', (161, 95, 59): '\x034,9▓', (61, 204, 61): '\x0f\x039█', (128, 38, 127): '\x0f\x036█', (69, 69, 230): '\x0f\x0312█', (37, 126, 52): '\x033,10▓', (46, 156, 46): '\x033,9▓', (193, 51, 81): '\x035,13▓', (174, 51, 45): '\x035,7▓', (102, 54, 31): '\x0f\x037█', (95, 65, 216): '\x0312,13▓', (78, 118, 131): '\x0311,13▓', (140, 42, 139): '\x036,13▓', (48, 122, 89): '\x033,12▓', (11, 35, 29): '\x031,11▓', (94, 94, 94): '\x0314,15▓', (170, 170, 210): '\x030,12▓', (130, 82, 39): '\x037,8▓', (94, 81, 150): '\x032,8▓', (19, 19, 19): '\x031,14▓', (107, 63, 124): '\x036,11▓', (64, 172, 64): '\x039,14▓', (46, 61, 155): '\x032,10▓', (13, 13, 44): '\x031,2▓', (53, 124, 106): '\x0311,14▓', (15, 51, 15): '\x031,9▓', (168, 56, 56): '\x035,14▓', (120, 54, 67): '\x037,13▓', (80, 119, 46): '\x033,4▓', (57, 57, 191): '\x032,12▓', (37, 37, 37): '\x031,15▓', (46, 140, 116): '\x0f\x0311█', (169, 145, 70): '\x038,10▓', (133, 65, 132): '\x036,15▓', (76, 76, 76): '\x0f\x0314█', (91, 91, 38): '\x037,9▓', (82, 61, 44): '\x037,10▓', (75, 118, 75): '\x033,13▓', (200, 85, 60): '\x034,8▓', (83, 190, 83): '\x039,15▓', (58, 58, 153): '\x032,14▓', (85, 146, 47): '\x033,8▓', (202, 165, 165): '\x030,5▓', (50, 124, 50): '\x033,14▓', (186, 74, 74): '\x035,15▓', (121, 42, 103): '\x036,7▓', (201, 167, 167): '\x030,4▓', (0, 0, 0): '\x0f\x031█', (159, 174, 174): '\x030,10▓', (70, 70, 191): '\x0312,14▓', (93, 57, 80): '\x037,12▓', (113, 77, 60): '\x037,15▓', (25, 85, 85): '\x0f\x0310█', (178, 166, 160): '\x030,7▓', (81, 117, 44): '\x033,5▓', (165, 63, 63): '\x034,14▓', (200, 161, 86): '\x038,15▓', (160, 72, 66): '\x035,11▓', (181, 47, 69): '\x035,6▓', (183, 81, 81): '\x034,15▓', (166, 166, 197): '\x030,2▓', (71, 49, 166): '\x032,6▓'}
colors.update({(110, 72, 72): '\x034,10▒', (114, 144, 144): '\x030,10▒', (172, 102, 96): '\x036,8▒', (166, 121, 165): '\x030,6▒', (150, 52, 40): '\x035,7▒', (197, 54, 54): '\x034,5▒', (126, 51, 114): '\x032,5▒', (139, 54, 103): '\x037,13▒', (210, 185, 134): '\x030,8▒', (68, 140, 68): '\x039,14▒', (208, 108, 57): '\x035,8▒', (61, 108, 96): '\x0311,14▒', (23, 70, 58): '\x031,11▒', (97, 144, 132): '\x0311,15▒', (183, 157, 107): '\x038,15▒', (55, 104, 136): '\x033,12▒', (51, 27, 15): '\x031,7▒', (77, 53, 105): '\x032,7▒', (64, 19, 63): '\x031,6▒', (100, 70, 130): '\x0310,13▒', (146, 121, 70): '\x038,14▒', (88, 27, 88): '\x031,13▒', (89, 65, 53): '\x037,14▒', (185, 57, 117): '\x034,13▒', (148, 56, 45): '\x034,7▒', (138, 93, 138): '\x036,15▒', (176, 176, 176): '\x030,15▒', (162, 102, 162): '\x0313,15▒', (122, 62, 203): '\x0312,13▒', (34, 34, 115): '\x031,12▒', (131, 153, 90): '\x038,11▒', (125, 172, 160): '\x030,11▒', (47, 96, 110): '\x032,3▒', (57, 104, 173): '\x0311,12▒', (21, 70, 21): '\x031,3▒', (174, 99, 99): '\x035,15▒', (121, 125, 75): '\x038,10▒', (143, 117, 147): '\x038,12▒', (39, 69, 132): '\x032,10▒', (190, 129, 190): '\x030,13▒', (98, 53, 178): '\x036,12▒', (74, 97, 73): '\x037,11▒', (112, 112, 112): '\x0314,15▒', (196, 110, 120): '\x038,13▒', (61, 61, 204): '\x032,12▒', (94, 121, 94): '\x036,9▒', (26, 26, 89): '\x031,2▒', (118, 99, 50): '\x033,4▒', (85, 89, 84): '\x033,6▒', (132, 64, 144): '\x034,12▒', (38, 38, 38): '\x031,14▒', (105, 176, 105): '\x039,15▒', (87, 117, 117): '\x0310,15▒', (99, 25, 25): '\x031,5▒', (120, 99, 87): '\x034,11▒', (126, 65, 126): '\x0313,14▒', (136, 136, 217): '\x030,12▒', (115, 46, 79): '\x036,7▒', (128, 128, 191): '\x030,2▒', (122, 95, 83): '\x035,11▒', (130, 127, 55): '\x035,9▒', (57, 128, 120): '\x032,9▒', (187, 52, 113): '\x035,13▒', (137, 63, 63): '\x035,14▒', (111, 97, 146): '\x0311,13▒', (51, 172, 51): '\x033,9▒', (30, 102, 30): '\x031,9▒', (163, 44, 88): '\x035,6▒', (72, 72, 153): '\x0312,14▒', (90, 45, 153): '\x032,6▒', (64, 64, 127): '\x032,14▒', (72, 97, 36): '\x033,7▒', (49, 96, 147): '\x032,11▒', (108, 83, 32): '\x031,8▒', (134, 59, 140): '\x035,12▒', (159, 110, 48): '\x037,8▒', (43, 144, 73): '\x039,10▒', (139, 185, 63): '\x038,9▒', (153, 129, 117): '\x030,7▒', (109, 97, 109): '\x033,13▒', (140, 140, 140): '\x030,14▒', (12, 42, 42): '\x031,10▒', (124, 56, 119): '\x032,4▒', (87, 89, 121): '\x036,11▒', (125, 101, 90): '\x037,15▒', (135, 67, 67): '\x034,14▒', (152, 46, 151): '\x036,13▒', (97, 29, 29): '\x031,4▒', (65, 136, 145): '\x039,12▒', (102, 102, 102): '\x030,1▒', (112, 67, 67): '\x035,10▒', (101, 101, 164): '\x032,15▒', (114, 54, 177): '\x032,13▒', (85, 61, 130): '\x037,12▒', (53, 172, 88): '\x039,11▒', (118, 129, 118): '\x039,13▒', (120, 95, 46): '\x033,5▒', (161, 48, 93): '\x034,6▒', (199, 131, 131): '\x030,4▒', (63, 69, 58): '\x037,10▒', (47, 77, 157): '\x0310,12▒', (123, 172, 123): '\x030,3▒', (35, 112, 100): '\x0310,11▒', (33, 112, 63): '\x033,10▒', (206, 112, 62): '\x034,8▒', (50, 80, 80): '\x0310,14▒', (201, 127, 127): '\x030,5▒', (102, 57, 101): '\x036,14▒', (129, 153, 53): '\x033,8▒', (172, 104, 104): '\x034,15▒', (44, 140, 79): '\x033,11▒', (81, 129, 46): '\x037,9▒', (132, 204, 132): '\x030,9▒', (76, 61, 106): '\x036,10▒', (135, 109, 122): '\x032,8▒', (109, 109, 189): '\x0312,15▒', (74, 74, 74): '\x031,15▒', (59, 108, 59): '\x033,14▒', (128, 131, 60): '\x034,9▒', (95, 144, 95): '\x033,15▒'})
colors.update({(159, 57, 89): '\x032,4░', (180, 56, 146): '\x034,13░', (71, 166, 53): '\x037,9░', (144, 43, 110): '\x034,6░', (160, 126, 126): '\x034,15░', (155, 125, 155): '\x0313,15░', (68, 76, 76): '\x035,10░', (73, 105, 80): '\x038,10░', (44, 118, 76): '\x032,3░', (67, 92, 67): '\x033,14░', (63, 86, 201): '\x0311,12░', (186, 82, 148): '\x038,13░', (142, 76, 142): '\x033,13░', (212, 137, 61): '\x035,8░', (94, 167, 60): '\x034,9░', (102, 102, 223): '\x030,12░', (129, 129, 169): '\x0312,15░', (162, 50, 82): '\x032,5░', (181, 53, 144): '\x035,13░', (44, 77, 71): '\x037,10░', (70, 70, 101): '\x032,14░', (101, 70, 101): '\x0313,14░', (56, 188, 56): '\x033,9░', (147, 79, 146): '\x030,6░', (122, 146, 122): '\x033,15░', (106, 69, 69): '\x035,14░', (40, 126, 108): '\x0310,11░', (72, 108, 72): '\x039,14░', (62, 86, 183): '\x033,12░', (100, 194, 62): '\x038,9░', (77, 162, 77): '\x036,9░', (106, 63, 105): '\x033,6░', (132, 41, 132): '\x031,13░', (90, 90, 185): '\x030,2░', (85, 156, 138): '\x030,11░', (34, 114, 79): '\x039,10░', (69, 114, 114): '\x030,10░', (74, 74, 114): '\x0312,14░', (76, 40, 23): '\x031,7░', (89, 66, 88): '\x036,14░', (188, 138, 56): '\x037,8░', (130, 130, 130): '\x0314,15░', (51, 51, 51): '\x030,1░', (109, 41, 140): '\x032,6░', (127, 91, 74): '\x030,7░', (39, 39, 134): '\x031,2░', (66, 114, 118): '\x036,11░', (87, 75, 33): '\x033,7░', (162, 162, 162): '\x030,15░', (49, 156, 102): '\x039,11░', (82, 70, 64): '\x037,14░', (126, 53, 35): '\x035,7░', (145, 54, 176): '\x032,13░', (143, 121, 143): '\x036,15░', (65, 65, 217): '\x032,12░', (183, 92, 183): '\x030,13░', (96, 28, 95): '\x031,6░', (200, 88, 88): '\x030,5░', (88, 146, 103): '\x038,11░', (127, 162, 127): '\x039,15░', (164, 50, 163): '\x036,13░', (146, 44, 44): '\x031,4░', (166, 153, 128): '\x038,15░', (67, 78, 78): '\x034,10░', (138, 62, 153): '\x0310,13░', (108, 108, 108): '\x030,14░', (89, 53, 68): '\x032,7░', (106, 93, 188): '\x038,12░', (125, 125, 156): '\x032,15░', (162, 124, 48): '\x031,8░', (58, 73, 193): '\x0310,12░', (59, 166, 90): '\x032,9░', (60, 118, 94): '\x037,11░', (18, 63, 63): '\x031,10░', (31, 105, 31): '\x031,3░', (82, 156, 82): '\x030,3░', (161, 124, 124): '\x035,15░', (111, 98, 73): '\x038,14░', (159, 72, 48): '\x033,5░', (143, 76, 161): '\x0311,13░', (125, 55, 38): '\x034,7░', (57, 57, 57): '\x031,14░', (194, 134, 80): '\x036,8░', (197, 95, 95): '\x030,4░', (147, 92, 147): '\x039,13░', (47, 118, 131): '\x032,11░', (108, 50, 55): '\x036,7░', (67, 102, 187): '\x039,12░', (149, 37, 37): '\x031,5░', (50, 73, 95): '\x036,10░', (84, 117, 99): '\x035,11░', (149, 58, 189): '\x0312,13░', (157, 54, 139): '\x037,13░', (156, 79, 54): '\x033,4░', (83, 119, 101): '\x034,11░', (45, 153, 45): '\x031,9░', (211, 139, 63): '\x034,8░', (83, 61, 204): '\x036,12░', (100, 66, 187): '\x034,12░', (29, 98, 74): '\x033,10░', (213, 175, 99): '\x030,8░', (118, 133, 133): '\x0310,15░', (101, 64, 185): '\x035,12░', (105, 71, 71): '\x034,14░', (96, 204, 96): '\x030,9░', (34, 105, 87): '\x031,11░', (123, 146, 140): '\x0311,15░', (198, 52, 52): '\x034,5░', (145, 41, 107): '\x035,6░', (68, 92, 86): '\x0311,14░', (77, 65, 180): '\x037,12░', (45, 140, 97): '\x033,11░', (111, 111, 111): '\x031,15░', (51, 51, 172): '\x031,12░', (63, 78, 78): '\x0310,14░', (95, 165, 58): '\x035,9░', (137, 125, 119): '\x037,15░', (32, 77, 108): '\x032,10░', (176, 137, 93): '\x032,8░', (173, 159, 59): '\x033,8░'})



@command("image img", r"(-[fpclgs\d]+\s+)?(.+)", templates=exceptions)
def image(server, msg, flags, query):
    """
    Image search.

    Search for the given terms on Google. If a number is given, it will display
    that result.

    Code adapted from kochira :v
    """

    params = {
            "safe": "off",
            "v": "1.0",
            "rsz": deflines[msg.prefix],
            "q": query
        }

    if flags:
        for i in flags[1:].strip():
            if i.isdigit():
                params["rsz"] = min(int(i), maxlines[msg.prefix])
            else:
                params.update({"f": {"imgtype": "face"},
                               "p": {"imgtype": "photo"},
                               "c": {"imgtype": "clipart"},
                               "l": {"imgtype": "lineart"},
                               "g": {"as_filetype": "gif"},
                               "s": {"safe": "active"}
                }[i])
                

    r = requests.get(
        "https://ajax.googleapis.com/ajax/services/search/images",
        params=params
    ).json()

    results = r.get("responseData", {}).get("results", [])

    for i, result in enumerate(results):
        server.lasturl = result["url"]
        yield templates[msg.prefix] % {"color" : [12, 5, 8, 3][i % 4],
                                       "url": url.shorten(result["url"]),
                                       "fullurl": result["visibleUrl"],
                                       "width": result["width"],
                                       "height": result["height"],  
                                       "content": unescape(re.sub("</?b>", "", 
                                                    result["content"])),
                                       "title": unescape(re.sub("</?b>", "", 
                                                    result["title"]))}
    if not results:
        yield "12Google Images│ No results."

@command("gif", r"(-[fpclgs\d]\s+)?(.+)", templates=exceptions)
def gif(server, msg, flags, query):
    flags = "-g" + (flags or "").strip("-")
    yield from image.funct(server, msg, flags, query)
    
@command("face mfw", r"(-[fpclgs\d]\s+)?(.+)", templates=exceptions)
def face(server, msg, flags, query):
    flags = "-f" + (flags or "").strip("-")
    yield from image.funct(server, msg, flags, query)

@command("photo", r"(-[fpclgs\d]\s+)?(.+)", templates=exceptions)
def photo(server, msg, flags, query):
    flags = "-p" + (flags or "").strip("-")
    yield from image.funct(server, msg, flags, query)

@command("clipart", r"(-[fpclgs\d]\s+)?(.+)", templates=exceptions)
def clipart(server, msg, flags, query):
    flags = "-c" + (flags or "").strip("-")
    yield from image.funct(server, msg, flags, query)

@command("lineart", r"(-[fpclgs\d]\s+)?(.+)", templates=exceptions)
def lineart(server, msg, flags, query):
    flags = "-l" + (flags or "").strip("-")
    yield from image.funct(server, msg, flags, query)

def nearestColor(c, colors=colors):
    return min(colors.keys(), key=lambda x: math.sqrt(sum((v-c[i])**2 for i, v in enumerate(x))))

@command("view", "(.*)")
@Callback.threadsafe
def asciiart(server, msg, pic):
    if not pic:
        pic = server.lasturl
    elif not pic.startswith("http"):
        params = {
            "safe": "off",
            "v": "1.0",
            "rsz": 1,
            "q": pic
        }
        pic = requests.get(
          "https://ajax.googleapis.com/ajax/services/search/images",
          params=params
        ).json()["responseData"]["results"][0]["url"]
    server.lasturl = pic
    if msg.prefix == "!": 
        h_max = 16
    else: 
        h_max = 6
    w_max = 15
    w_res, h_res = 3, 1

    data = requests.get(pic).content
    data = BytesIO(data)
    img = Image.open(data)
    if img.size[0] > 4096 or img.size[1] > 4096:
        return "│ Image too large."

    scalefactor = max(img.size[0]/w_max, img.size[1]/h_max)
    x, y = img.size[0]/scalefactor, img.size[1]/scalefactor
    img = img.resize((int(img.size[0]/scalefactor) * w_res, int(img.size[1]/scalefactor)*h_res), Image.ANTIALIAS)
    img = img.convert("RGBA")
    img.load()  # needed for split()
    background = Image.new('RGB', img.size, (255,255,255))
    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return "\n".join("".join(colors[nearestColor(img.getpixel((i, j)))] for i in range(img.size[0])) for j in range(img.size[1]))

blocks = {(True, True, False, True): '▛', (True, False, True, True): '▙', (True, True, True, False): '▜', (False, False, False, False): ' ', (True, False, True, False): '▚', (False, False, False, True): '▖', (False, True, False, True): '▞', (True, False, False, True): '▌', (False, True, False, False): '▝', (True, True, True, True): '█', (False, True, True, False): '▐', (False, False, True, False): '▗', (True, True, False, False): '▀', (True, False, False, False): '▘', (False, False, True, True): '▄', (False, True, True, True): '▟'}
defaults = {(128, 38, 127): '\x036', (195, 59, 59): '\x034', (25, 85, 85): '\x0310', (69, 69, 230): '\x0312', (217, 166, 65): '\x038', (199, 50, 50): '\x035', (42, 140, 42): '\x033', (76, 76, 76): '\x0314', (102, 54, 31): '\x037', (53, 53, 179): '\x032', (46, 140, 116): '\x0311', (0, 0, 0): '\x031', (176, 55, 176): '\x0313', (204, 204, 204): '\x030', (61, 204, 61): '\x039', (149, 149, 149): '\x0315'}


@command("render", "(.*)")
@Callback.threadsafe
def render(server, msg, pic):
    if not pic:
        pic = server.lasturl
    elif not pic.startswith("http"):
        params = {
            "safe": "off",
            "v": "1.0",
            "rsz": 1,
            "q": pic
        }
        pic = requests.get(
          "https://ajax.googleapis.com/ajax/services/search/images",
          params=params
        ).json()["responseData"]["results"][0]["url"]
    server.lasturl = pic
    if msg.prefix == "!": 
        h_max = 16
    else: 
        h_max = 6
    w_max = 20
    w_res, h_res = 6, 2

    data = requests.get(pic).content
    data = BytesIO(data)
    img = Image.open(data)
    if img.size[0] > 4096 or img.size[1] > 4096:
        return "│ Image too large."

    scalefactor = max(img.size[0]/w_max, img.size[1]/h_max)
    x, y = img.size[0]/scalefactor, img.size[1]/scalefactor
    img = img.resize((int(img.size[0]/scalefactor) * w_res, int(img.size[1]/scalefactor)*h_res), Image.ANTIALIAS)
    cmap = img.resize((int(img.size[0]/2), int(img.size[1]/2))).convert("RGBA")
    img = img.convert('1')
    cmap.load()  # needed for split()
    background = Image.new('RGB', cmap.size, (255,255,255))
    background.paste(cmap, mask=cmap.split()[3])  # 3 is the alpha channel
    return "\n".join("".join(defaults[nearestColor(background.getpixel((x, y)), defaults)] + blocks[img.getpixel((2*x, 2*y)) != 255,
                                    img.getpixel((2*x+1, 2*y)) != 255,
                                    img.getpixel((2*x+1, 2*y+1)) != 255,
                                    img.getpixel((2*x, 2*y+1)) != 255] for x in range(int(img.size[0]/2))) for y in range(int(img.size[1]/2)))

@command("show", "(.*)")
@Callback.threadsafe
def show(server, msg, pic):
    if not pic:
        pic = server.lasturl
    elif not pic.startswith("http"):
        params = {
            "safe": "off",
            "v": "1.0",
            "rsz": 1,
            "q": pic
        }
        pic = requests.get(
          "https://ajax.googleapis.com/ajax/services/search/images",
          params=params
        ).json()["responseData"]["results"][0]["url"]
    server.lasturl = pic
    if msg.prefix == "!": 
        h_max = 16
    else: 
        h_max = 6
    w_max = 18
    w_res, h_res = 6, 2

    data = requests.get(pic).content
    data = BytesIO(data)
    img = Image.open(data)
    if img.size[0] > 4096 or img.size[1] > 4096:
        return "│ Image too large."

    scalefactor = max(img.size[0]/w_max, img.size[1]/h_max)
    x, y = img.size[0]/scalefactor, img.size[1]/scalefactor
    img = img.resize((int(img.size[0]/scalefactor) * w_res, int(img.size[1]/scalefactor)*h_res), Image.ANTIALIAS)
    img = img.convert("RGBA")
    img.load()  # needed for split()
    background = Image.new('RGB', img.size, (255,255,255))
    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return irc_render(background)

@command("trace", "(.*)")
@Callback.threadsafe
def trace(server, msg, pic):
    if not pic:
        pic = server.lasturl
    elif not pic.startswith("http"):
        params = {
            "safe": "off",
            "v": "1.0",
            "rsz": 1,
            "q": pic
        }
        pic = requests.get(
          "https://ajax.googleapis.com/ajax/services/search/images",
          params=params
        ).json()["responseData"]["results"][0]["url"]
    server.lasturl = pic
    if msg.prefix == "!": 
        h_max = 16
    else: 
        h_max = 6
    w_max = 55
    w_res, h_res = 6, 4

    data = requests.get(pic).content
    data = BytesIO(data)
    img = Image.open(data)
    if img.size[0] > 4096 or img.size[1] > 4096:
        return "│ Image too large."

    scalefactor = max(img.size[0]/w_max, img.size[1]/h_max)
    x, y = img.size[0]/scalefactor, img.size[1]/scalefactor
    img = img.resize((int(img.size[0]/scalefactor) * w_res, int(img.size[1]/scalefactor)*h_res), Image.ANTIALIAS)
    img = img.convert("RGBA")
    img.load()  # needed for split()
    background = Image.new('RGB', img.size, (255,255,255))
    background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
    return draw_braille(img)

@msghandler
def urlcache(server, msg):
    urls = [i for i in msg.text.split() if i.startswith("http")]
    if urls:
        server.lasturl = urls[-1]

__callbacks__ = {"privmsg": [image, gif, face, photo, clipart, lineart, asciiart, urlcache, render, show, trace]}