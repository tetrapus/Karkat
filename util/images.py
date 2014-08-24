import math
import colorsys
from operator import itemgetter

class Palette(object):
    XCHAT = {(128, 38, 127) : 6,
             (195, 59, 59)  : 4,
             (25, 85, 85)   : 10,
             (69, 69, 230)  : 12,
             (217, 166, 65) : 8,
             (199, 50, 50)  : 5,
             (42, 140, 42)  : 3,
             (76, 76, 76)   : 14,
             (102, 54, 31)  : 7,
             (53, 53, 179)  : 2,
             (46, 140, 116) : 11,
             (0, 0, 0)      : 1,
             (176, 55, 176) : 13,
             (204, 204, 204): 0,
             (61, 204, 61)  : 9,
             (149, 149, 149): 15}

blocks = {(True, True, False, True): '▛', (True, False, True, True): '▙', (True, True, True, False): '▜', (False, False, False, False): ' ', (True, False, True, False): '▚', (False, False, False, True): '▖', (False, True, False, True): '▞', (True, False, False, True): '▌', (False, True, False, False): '▝', (True, True, True, True): '█', (False, True, True, False): '▐', (False, False, True, False): '▗', (True, True, False, False): '▀', (True, False, False, False): '▘', (False, False, True, True): '▄', (False, True, True, True): '▟'}

def average(points):
    return [sum(i)/len(i) for i in zip(*points)]

def distance(a, b):
    a, b = colorsys.rgb_to_yiq(*a), colorsys.rgb_to_yiq(*b)
    return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))

def nearestColor(c, colorspace):
    return min(colorspace.items(), key=lambda x:distance(c, x[0]))[1]

def aggregate_distance(points, partition):
    mask = tuple(bool(partition >> i & 1) for i in range(3,-1,-1))
    means = average(point for i, point in enumerate(points) if not mask[i]), average(point for i, point in enumerate(points) if mask[i])
    return [sum(distance(means[mask[i]], point) for i, point in enumerate(points)), means, mask]

def bifurcate(points):
    return min([aggregate_distance(points, i) for i in range(1, 15)], key=itemgetter(0))

def irc_render(img, palette=Palette.XCHAT):
    lines = []
    for y in range(img.size[1]//2):
        line = ""
        for x in range(img.size[0]//2):
            _, means, mask = bifurcate([img.getpixel((2*x, 2*y)), img.getpixel((2*x+1, 2*y)), img.getpixel((2*x+1, 2*y+1)), img.getpixel((2*x, 2*y+1))])
            colors = nearestColor(means[1], palette), nearestColor(means[0], palette)
            line += "\x03%d,%d%s" % (nearestColor(means[1], palette), nearestColor(means[0], palette), blocks[mask])
        lines.append(line)
    return "\n".join(lines)

braille = "⠀⠁⠈⠉⠂⠃⠊⠋⠐⠑⠘⠙⠒⠓⠚⠛⠄⠅⠌⠍⠆⠇⠎⠏⠔⠕⠜⠝⠖⠗⠞⠟⠠⠡⠨⠩⠢⠣⠪⠫⠰⠱⠸⠹⠲⠳⠺⠻⠤⠥⠬⠭⠦⠧⠮⠯⠴⠵⠼⠽⠶⠷⠾⠿⡀⡁⡈⡉⡂⡃⡊⡋⡐⡑⡘⡙⡒⡓⡚⡛⡄⡅⡌⡍⡆⡇⡎⡏⡔⡕⡜⡝⡖⡗⡞⡟⡠⡡⡨⡩⡢⡣⡪⡫⡰⡱⡸⡹⡲⡳⡺⡻⡤⡥⡬⡭⡦⡧⡮⡯⡴⡵⡼⡽⡶⡷⡾⡿⢀⢁⢈⢉⢂⢃⢊⢋⢐⢑⢘⢙⢒⢓⢚⢛⢄⢅⢌⢍⢆⢇⢎⢏⢔⢕⢜⢝⢖⢗⢞⢟⢠⢡⢨⢩⢢⢣⢪⢫⢰⢱⢸⢹⢲⢳⢺⢻⢤⢥⢬⢭⢦⢧⢮⢯⢴⢵⢼⢽⢶⢷⢾⢿⣀⣁⣈⣉⣂⣃⣊⣋⣐⣑⣘⣙⣒⣓⣚⣛⣄⣅⣌⣍⣆⣇⣎⣏⣔⣕⣜⣝⣖⣗⣞⣟⣠⣡⣨⣩⣢⣣⣪⣫⣰⣱⣸⣹⣲⣳⣺⣻⣤⣥⣬⣭⣦⣧⣮⣯⣴⣵⣼⣽⣶⣷⣾⣿"

def draw_braille(img):
    img = img.convert('1')
    def getpix(y, x):
        try:
            return img.getpixel((x, y)) < 127
        except IndexError:
            return 0
    lines = []
    for y in range(img.size[1]//4 + bool(img.size[1] % 4)):
        line = []
        row = y * 4
        for x in range(img.size[0]//2 + bool(img.size[0] % 2)):
            col = x * 2
            index = 0
            index += getpix(row, col)
            index += 2*getpix(row, col+1)
            index += 4*getpix(row+1, col)
            index += 8*getpix(row+1, col+1)
            index += 16*getpix(row+2, col)
            index += 32*getpix(row+2, col+1)
            index += 64*getpix(row+3, col)
            index += 128*getpix(row+3, col+1)
            line.append(braille[index])
        lines.append("".join(line))
    return "\n".join(lines)