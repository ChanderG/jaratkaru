class Tokenizer:
    def __init__(self, txt):
        # works only for single line input
        # does not work for strings

        toks = []
        def push(item):
            toks.append(item)
        def pop():
            return toks.pop()

        idx = 0
        while idx < len(txt):
            ch = txt[idx]
            if ch == "(" or ch == ")":
                push((ch, idx+1))
            elif ch == " ":
                pass
            else:
                tok = ch
                start = idx
                while idx+1 < len(txt) and txt[idx+1] not in ["(", ")", " "]:
                    idx += 1
                    tok = tok + txt[idx]
                push((tok, start))
            idx += 1
        self.tokens = toks

def READ(inp):
    t = Tokenizer(inp)
    return t.tokens

def EVAL(inp):
    return inp

def PRINT(inp):
    return inp

def rep(inp):
    return PRINT(EVAL(READ(inp)))

def main():
    while True:
        inp = input("user> ")
        print(rep(inp))

main()
