import random
import json

from bot.events import command, Callback


braille = "⠀⠁⠈⠉⠂⠃⠊⠋⠐⠑⠘⠙⠒⠓⠚⠛⠄⠅⠌⠍⠆⠇⠎⠏⠔⠕⠜⠝⠖⠗⠞⠟⠠⠡⠨⠩⠢⠣⠪⠫⠰⠱⠸⠹⠲⠳⠺⠻⠤⠥⠬⠭⠦⠧⠮⠯⠴⠵⠼⠽⠶⠷⠾⠿⡀⡁⡈⡉⡂⡃⡊⡋⡐⡑⡘⡙⡒⡓⡚⡛⡄⡅⡌⡍⡆⡇⡎⡏⡔⡕⡜⡝⡖⡗⡞⡟⡠⡡⡨⡩⡢⡣⡪⡫⡰⡱⡸⡹⡲⡳⡺⡻⡤⡥⡬⡭⡦⡧⡮⡯⡴⡵⡼⡽⡶⡷⡾⡿⢀⢁⢈⢉⢂⢃⢊⢋⢐⢑⢘⢙⢒⢓⢚⢛⢄⢅⢌⢍⢆⢇⢎⢏⢔⢕⢜⢝⢖⢗⢞⢟⢠⢡⢨⢩⢢⢣⢪⢫⢰⢱⢸⢹⢲⢳⢺⢻⢤⢥⢬⢭⢦⢧⢮⢯⢴⢵⢼⢽⢶⢷⢾⢿⣀⣁⣈⣉⣂⣃⣊⣋⣐⣑⣘⣙⣒⣓⣚⣛⣄⣅⣌⣍⣆⣇⣎⣏⣔⣕⣜⣝⣖⣗⣞⣟⣠⣡⣨⣩⣢⣣⣪⣫⣰⣱⣸⣹⣲⣳⣺⣻⣤⣥⣬⣭⣦⣧⣮⣯⣴⣵⣼⣽⣶⣷⣾⣿"

def draw_braille(board, size):
    def getpix(y, x):
        try:
            return board[y][x]
        except IndexError:
            return 0
    lines = []
    for y in range(size[1]//4 + bool(size[1] % 4)):
        line = []
        row = y * 4
        for x in range(size[0]//2 + bool(size[0] % 2)):
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
    

def draw_half(board):
    size = (len(board[0]), len(board))
    def getpix(y, x):
        try:
            return board[y][x]
        except IndexError:
            return 0
    return "\n".join("".join("\x03%.2d,%.2d▄" % (getpix(2*y+1, x), getpix(2*y, x))
                        for x in range(size[0]))
                            for y in range(size[1]//2 + bool(size[1] % 2)))


class Game(object):
    COLORS = [10, 6, 3, 8, 9, 13, 14, 11, 7, 2, 4]
    PIECES = [[[1, 1, 1, 1]],
              [[1, 1, 1], [0, 0, 1]],
              [[1, 1, 1], [1, 0, 0]],
              [[1, 1], [1, 1]],
              [[0, 1, 1], [1, 1, 0]],
              [[1, 1, 1], [0, 1, 0]],
              [[1, 1, 0], [0, 1, 1]]]         

    def __init__(self, name, size=(10, 16), board=None, players=None):
        self.name = name
        self.size = size
        if board is None:
            board = [[None for i in range(size[1])] for j in range(size[0])]
        self.board = board
        if players is None:
            players = {}
        self.players = players

    def serialise(self):
        return {"size": list(self.size), "board": self.board, "players": self.players}

    def rand_piece(self):
        return random.choice(self.PIECES)

    def add_player(self, key, name):
        self.players[key] = {"name":name, "score": 0, "pieces": [self.rand_piece(), self.rand_piece()], "color": hash(key) % len(self.COLORS)}

    


class Tetris(Callback):
    TETRIS_SAVED = "tetris_games.json"

    def __init__(self, server):
        self.save_file = server.get_config_dir(self.TETRIS_SAVED)
        try:
            with open(self.save_file) as f:
                self.games = json.load(f)
            self.games = {k: Game(k, *v) for k, v in self.games.items()}
        except:
            self.games = {}

        self.server = server
        super().__init__(server)

    def init_game(self, channel):
        chan = self.server.lower(channel)
        if chan not in self.games:
            self.games[chan] = Game(channel)
        return self.games[chan]

    def ensure_created(self, channel, user):
        game = self.init_game(channel)
        luser = self.server.lower(user)
        if luser not in game.players:
            game.add_player(luser, user)
        return game

    # TODO: Fix multiline display

    def format_user(self, player):
        currentp = draw_half([[player['color'] if j else j for j in i] for i in player['pieces'][0]]).split("\n")
        nextp = draw_half([[player['color'] if j else j for j in i] for i in player['pieces'][1]]).split("\n")
        currentpl, nextpl = len(currentp), len(nextp)
        if currentpl > nextpl:
            nextp.extend([" " * len(player['pieces'][1])] * (currentpl - nextpl))
        else:
            currentp.extend([" " * len(player['pieces'][0])] * (nextpl - currentpl))
        height = max(currentpl, nextpl)
        left = ["\x0312⡇\x03 Current: "] + (["\x0312⡇\x03          "] * (height - 1))
        mid = ["\x0f · Next: "] + (["\x0f         "] * (height - 1))
        lines = zip(left, currentp, mid, nextp)
        lines = ["%s%s%s%s" % s for s in lines]
        lines[0] += "\x0f · Score: %d" % player["score"]
        return "\n".join(lines)            

    @command
    def piece(self, server, message):
        game = self.ensure_created(message.context, message.address.nick)
        player = game.players[self.server.lower(message.address.nick)]
        return self.format_user(player)

    @command
    def rotate(self, server, message):
        game = self.ensure_created(message.context, message.address.nick)
        player = game.players[self.server.lower(message.address.nick)]
        player['pieces'][0] = list(zip(*player['pieces'][0][::-1]))
        return self.format_user(player)

    @command
    def tetris(self, server, message):
        game = self.ensure_created(message.context, message.address.nick)
        

    @command("drop", "\d+")
    def drop(self, server, message, index: int):
        game = self.ensure_created(message.context, message.address.nick)
        

__initialise__ = Tetris