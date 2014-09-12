# check bracket balance
from bot.events import command

braks = dict(zip("]})", "[{("))
unbraks = dict(zip("[{(", "]})"))

@command("balance", r"(-s\s+)?(.+)")
def balance(server, msg, disable_strings, expr):
    stack = []
    out = ""
    colors = [6, 13, 12, 2, 10, 11, 9, 8, 7, 4]
    errs = 0
    string = None
    sescape = False
    for i in expr:
        if not disable_strings:
            if string is not None:
                if i == string and not sescape:
                    string = None
                    out += i + "\x03%.2d" % colors[(len(stack) - 1) % len(colors)]
                    continue
                if i == "\\":
                    sescape = not sescape
                else:
                    sescape = False
                out += i
                continue
            elif i in '\'"':
                string = i
                out += "\x0315" + i
                continue
        if i in braks.values():
            out += "\x03%.2d\x02%s\x02" % (colors[len(stack) % len(colors)], i)
            stack.append(i)
        elif i in braks:
            while stack and braks[i] != stack[-1]:
                # Add all the missing end brackets
                c = stack.pop()
                out += "\x1f\x02%s\x02\x1f\x03%.2d" % (unbraks[c], colors[(len(stack) - 1) % len(colors)])
                errs += 1
            if not stack:
                # Add a start bracket to balance things
                out += "\x03%.2d\x1f\x02%s\x02\x1f" % (colors[len(stack) % len(colors)], braks[i])
                stack.append(braks[i])
                errs += 1
            stack.pop()
            if len(stack) == 0:
                out += "\x02%s\x02\x0f" % i
            else:
                out += "\x02%s\x02\x03%.2d" % (i, colors[(len(stack) - 1) % len(colors)])
        else:
            out += i
    if sescape:
        out += "\x1f\\\x1f"
    if string is not None:
        out += "\x1f%s\x1f\x03%.2d" % (string, colors[(len(stack) - 1) % len(colors)])
    while stack:
        i = stack.pop()
        out += "\x1f\x02%s\x02\x1f\x03%.2d" % (unbraks[i], colors[(len(stack) - 1) % len(colors)])
        errs += 1
    return "\x0307│\x0315 %d ᴇʀʀᴏʀꜱ \x0307│\x03 %s" % (errs, out)

__callbacks__ = {"privmsg": [balance]}