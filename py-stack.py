from dataclasses import dataclass

@dataclass
class Sexp:
  val: any

class ParseException(Exception):
    pass

class Tokenizer:
    def __init__(self, txt):
        self.txt = txt
        # works only for single line input
        # does not work for strings

        toks = []
        def push(item):
            toks.append(item)

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

    def read_atom(self, token):
        try: return int(token)
        except ValueError:
            try: return float(token)
            except ValueError:
                return token

    def raise_parse_error(self, msg, tok):
        fmt_msg = msg + f" at character {tok[1]}"
        fmt_msg += "\n"
        fmt_msg += self.txt + "\n"
        fmt_msg += "-"*(tok[1]-1) + "^"
        fmt_msg += "\n"

        raise ParseException(fmt_msg)

    def parse(self):
        stack = []
        def push(item):
            stack.append(item)
        def pop():
            if len(stack) == 0:
                return None
            return stack.pop()

        for t in self.tokens:
            if t[0] == "(":
                push(t)
            elif t[0] == ")":
                lis = []

                while True:
                    item = pop()
                    if item == None:
                        self.raise_parse_error("Unbalanced ) found", t)
                    elif isinstance(item, Sexp):
                        lis.insert(0, item)
                    elif item[0] == "(":
                        break
                    else: # should not reach here
                        self.raise_parse_error("Unexpected token found", item)

                push(Sexp(lis))
            else:
                push(Sexp(self.read_atom(t[0])))

        # check if stack is empty of tokens here
        results = []
        while True:
            item = pop()
            if item == None:
                break
            if isinstance(item, Sexp):
                results.insert(0, item)
            else: # un-expected
                self.raise_parse_error("Unbalanced ( found", item)

        return results

def READ(inp):
    t = Tokenizer(inp)
    return t.parse()

def EVAL(inp):
    return inp

def PRINT(inp):
    return inp

def rep(inp):
    return PRINT(EVAL(READ(inp)))

def main():
    while True:
        try:
            inp = input("user> ")
            print(rep(inp))
        except ParseException as p:
            print("Error in parsing: ", p)

main()
