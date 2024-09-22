from dataclasses import dataclass

@dataclass
class Token:
    def __init__(self, val: str, pos: int, txt: str):
        self.val = val
        self.pos = pos
        self.txt = txt

    def format_loc(self):
        fmt_msg = f" at character {self.pos}"
        fmt_msg += "\n"
        fmt_msg += self.txt + "\n"
        fmt_msg += "-"*(self.pos-1) + "^"
        fmt_msg += "\n"

        return fmt_msg

@dataclass
class SexpAtom:
    val: any

@dataclass
class SexpSymbol:
    val: str

@dataclass
class SexpList:
    val: list

Sexp = SexpAtom | SexpSymbol | SexpList

class ParseException(Exception):
    pass
class UnboundError(Exception):
    pass
class MalformedLetStructure(Exception):
    pass

class Parser:
    def __init__(self, txt):
        self.txt = txt
        # Now, tokenize the input
        # works only for single line input
        # does not work for strings

        toks = []
        def push(item):
            toks.append(item)

        idx = 0
        while idx < len(txt):
            ch = txt[idx]
            if ch == "(" or ch == ")":
                push(Token(ch, idx+1, self.txt))
            elif ch == " ":
                pass
            else:
                tok = ch
                start = idx
                while idx+1 < len(txt) and txt[idx+1] not in ["(", ")", " "]:
                    idx += 1
                    tok = tok + txt[idx]
                push(Token(tok, start, self.txt))
            idx += 1
        self.tokens = toks

    def read_atom(self, token):
        try: return SexpAtom(int(token))
        except ValueError:
            try: return SexpAtom(float(token))
            except ValueError:
                return SexpSymbol(token)

    def raise_parse_error(self, msg, tok):
        fmt_msg = msg + tok.format_loc()
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
            if t.val == "(":
                push(t)
            elif t.val == ")":
                lis = []

                while True:
                    item = pop()
                    if item == None:
                        self.raise_parse_error("Unbalanced ) found", t)
                    elif isinstance(item, Sexp):
                        lis.insert(0, item)
                    elif item.val == "(":
                        break
                    else: # should not reach here
                        self.raise_parse_error("Unexpected token found", item)

                push(SexpList(lis))
            else:
                push(self.read_atom(t.val))

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

class Env:
    def __init__(self, outer = None):
        self.outer = outer
        self.data = {}

    def get(self, key):
        if key in self.data:
            return self.data[key]
        elif self.outer is not None:
            return self.outer.get(key)
        else:
            raise UnboundError(key)

    def set(self, key, value):
        self.data[key] = value

def READ(inp):
    p = Parser(inp)
    return p.parse()

def EVAL(sexp, env):
    if isinstance(sexp, SexpAtom):
        return sexp.val
    elif isinstance(sexp, SexpSymbol):
        return env.get(sexp.val)
    elif isinstance(sexp, SexpList):
        form = sexp.val[0]

        if form.val == "let*":
            if len(sexp.val) < 3:
                raise MalformedLetStructure("Bindings or Body missing")
            binds = sexp.val[1]
            body = sexp.val[2:]
            l_env = Env(env)

            if not isinstance(binds, SexpList):
                raise MalformedLetStructure("Bindings should be a list")
            for bind in binds.val:
                if not isinstance(bind, SexpList):
                    raise MalformedLetStructure("Binding should be a list")
                if len(bind.val) != 2:
                    raise MalformedLetStructure("Binding should be a list of 2 items, key and value")

                key = bind.val[0].val
                value = EVAL(bind.val[1], l_env)
                l_env.set(key, value)

            # eval all forms, return the result of the last one
            res = None
            for b in body:
                res = EVAL(b, l_env)
            return res
        else:
            eval_lis = list(map(lambda x: EVAL(x, env), sexp.val))
            return eval_lis[0](*eval_lis[1:])
    else:
        return None

def PRINT(inp):
    return inp

def rep(inp):
    env = Env()

    env.set('+', lambda a,b: a+b)
    env.set('-', lambda a,b: a-b)
    env.set('*', lambda a,b: a*b)
    env.set('/', lambda a,b: a/b)

    sexps = READ(inp)
    res = []
    for sexp in sexps:
        res.append(EVAL(sexp, env))
    return PRINT(res[-1])

def main():
    while True:
        try:
            inp = input("user> ")
            print(rep(inp))
        except ParseException as p:
            print("Error in parsing: ", p)
        except UnboundError as e:
            print("Unbound symbol used: ", e)
        except MalformedLetStructure as e:
            print("Incorrect use of let: ", e)

main()
