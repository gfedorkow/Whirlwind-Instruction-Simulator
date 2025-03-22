
import wwinfra

player_symbols = ['none', 'X', 'O', '?']

indent = [
    "",   # 0
    "    ",
    "        ",
    "            ",
    "                ",
    "                    ",   # 5
    "                        ",
    "                            ",
    "                                ",
    "                                    ",
    "                                        ",   #10
]

Debug = True

def print_experiment(cm, cb, fmt, args, depth_label, iff=None):
    if iff:
        try:
            ev = eval(iff)
        except TypeError:
            print("can't evaluate term %s" % iff)
            ev = 0
        print("Debug Condition = %s, returns %d" % (iff, ev))
    if depth_label == 0:
        depth = 0
    else:
        depth = cm.rd(cb.cpu.rl(depth_label))
    fmt = indent[depth] + fmt
    arg_ints = []
    for a in args:
        try:
            val = cm.rd(cb.cpu.rl(a))
        except:
            print("value error in print_experiment: %s", a)
            val = 0

        if val & 0x8000:   # check WW sign bit
            val = - (val ^ 0xffff)
        arg_ints.append(val)
    try:
        print(fmt % tuple(arg_ints))
    except TypeError:
        print("print_experiment TypeError")


# ordinary print function, but indent according to the current stack depth
def print_indent(cm, fmt, depthp, iff=None):
    if not Debug:
        return
    depth = cm.rd(depthp)
    fmt = indent[depth] + fmt
    print(fmt)


def print_board(cm, boardpp:int, depthp:int, player_addr, title="", iff=None):
    # print("print_board boardpp=0o%o, depthp=0o%o, player_addr=0o%o" % (boardpp, depthp, player_addr))
    if not Debug:
        return
    if iff:
        try:
            ev = eval(iff)
        except TypeError:
            print("can't evaluate term %s" % iff)
            ev = 0
        print("Debug Condition = %s, returns %d" % (iff, ev))

    player = cm.rd(player_addr)

    boardp = cm.rd(boardpp)
    if depthp == 0:
        depth = 0
    else:
        depth = cm.rd(depthp)
    if depth < 0:
        print("print_board negative depth=0o%o" % (depth))
        depth = 0
    print("%s%s Board Address: 0o%o, depth %d, player %d" %
          (indent[depth], title, boardp, depth, player))
    prnt = ''
    for i in range(0,3):
        prnt += indent[depth]
        for j in range(0,3):
            val = cm.rd(boardp + 3*i + j)
            if val > 3:
                prnt += '- '
            else:
                prnt += player_symbols[val] + ' '
        prnt += '\n'
    prnt += '\n'
    print(prnt)
    

if __name__ == "__main__":
    print_board(0, 0o63, 2)
