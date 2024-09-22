from dataclasses import dataclass
import sys
from contextlib import contextmanager

class Token:
    def __init__(self, val: str, pos: int, line: int, txt: [str]):
        self.val = val
        self.pos = pos
        self.line = line
        self.txt = txt

    def format_loc(self):
        fmt_msg = f" at character {self.pos}"
        if self.line != 0:
            fmt_msg += f" on line number {self.line+1}"
        fmt_msg += "\n"
        fmt_msg += self.txt[self.line] + "\n"
        fmt_msg += "-"*(self.pos-1) + "^"
        fmt_msg += "\n"

        return fmt_msg

@dataclass
class SexpAtom:
    val: any
    tok: Token

@dataclass
class SexpSymbol:
    val: str
    tok: Token

@dataclass
class SexpList:
    val: list
    tok: Token

Sexp = SexpAtom | SexpSymbol | SexpList

class ParseException(Exception):
    pass
class UnboundError(Exception):
    pass
class MalformedExpression(Exception):
    pass
class MalformedLetStructure(Exception):
    pass

class Parser:
    def __init__(self, txt: [str]):
        self.txt = txt
        # Now, tokenize the input
        # does not work for strings

        toks = []
        def push(item):
            toks.append(item)

        for lineno, line in enumerate(txt):
            idx = 0
            while idx < len(line):
                ch = line[idx]
                if ch == "(" or ch == ")":
                    push(Token(ch, idx+1, lineno, self.txt))
                elif ch == " ":
                    pass
                else:
                    tok = ch
                    start = idx
                    while idx+1 < len(line) and line[idx+1] not in ["(", ")", " "]:
                        idx += 1
                        tok = tok + line[idx]
                    push(Token(tok, start, lineno, self.txt))
                idx += 1

        self.tokens = toks

    def read_atom(self, token):
        try: return SexpAtom(int(token.val), token)
        except ValueError:
            try: return SexpAtom(float(token.val), token)
            except ValueError:
                return SexpSymbol(token.val, token)

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
                        raise ParseException("Unbalanced ) found" + t.format_loc())
                    elif isinstance(item, Sexp):
                        lis.insert(0, item)
                    elif item.val == "(":
                        break
                    else: # should not reach here
                        raise ParseException("Unexpected token found" + item.format_loc())

                push(SexpList(lis, item))
            else:
                push(self.read_atom(t))

        # check if stack is empty of tokens here
        results = []
        while True:
            item = pop()
            if item == None:
                break
            if isinstance(item, Sexp):
                results.insert(0, item)
            else: # un-expected
                raise ParseException("Unbalanced ( found" + item.format_loc())

        return results

class Env:
    def __init__(self, outer = None):
        self.outer = outer
        self.data = {}

    def get(self, key: SexpSymbol):
        if key.val in self.data:
            return self.data[key.val]
        elif self.outer is not None:
            return self.outer.get(key)
        else:
            raise UnboundError(key.val + key.tok.format_loc())

    def set(self, key, value):
        self.data[key] = value

def READ(inp):
    p = Parser(inp)
    return p.parse()

def eval_let_star(sexp, env):
    if len(sexp.val) < 3:
        raise MalformedLetStructure("Bindings or Body missing" + sexp.tok.format_loc())
    binds = sexp.val[1]
    body = sexp.val[2:]
    l_env = Env(env)

    if not isinstance(binds, SexpList):
        raise MalformedLetStructure("Bindings should be a list" + binds.tok.format_loc())
    for bind in binds.val:
        if not isinstance(bind, SexpList):
            raise MalformedLetStructure("Binding should be a list" + bind.tok.format_loc())
        if len(bind.val) != 2:
            raise MalformedLetStructure("Binding should be a list of 2 items, key and value" + bind.tok.format_loc())

        key = bind.val[0].val
        value = EVAL(bind.val[1], l_env)
        l_env.set(key, value)

    # eval all forms, return the result of the last one
    res = None
    for b in body:
        res = EVAL(b, l_env)
    return res

def eval_setq(sexp, env):
    if len(sexp.val) != 3:
        raise MalformedExpression("setq should have 2 args" + sexp.tok.format_loc())

    var = sexp.val[1]
    if not isinstance(var, SexpSymbol):
        raise MalformedExpression("setq should have symbol as first arg" + var.tok.format_loc())
    body = sexp.val[2]
    res = EVAL(body, env)
    env.set(var.val, res)

    return res

def eval_if(sexp, env):
    if len(sexp.val) > 4:
        raise MalformedExpression("if should have max 4 args" + sexp.tok.format_loc())

    condition = EVAL(sexp.val[1], env)
    if condition:
        return EVAL(sexp.val[2], env)
    else:
        if len(sexp.val) == 4:
            return EVAL(sexp.val[3], env)
        else:
            return None

def EVAL(sexp, env):
    if isinstance(sexp, SexpAtom):
        return sexp.val
    elif isinstance(sexp, SexpSymbol):
        return env.get(sexp)
    elif isinstance(sexp, SexpList):
        form = sexp.val[0]

        if form.val == "let*":
            return eval_let_star(sexp, env)
        elif form.val == "setq":
            return eval_setq(sexp, env)
        elif form.val == "if":
            return eval_if(sexp, env)
        else:
            eval_lis = list(map(lambda x: EVAL(x, env), sexp.val))
            return eval_lis[0](*eval_lis[1:])
    else:
        return None

def PRINT(inp):
    return inp

def rep(inp):
    sexps = READ([inp])
    res = []
    for sexp in sexps:
        res.append(EVAL(sexp, env))

    return PRINT(res[-1])

def load_file(filename):
    with open(filename) as f:
        txt = f.read().splitlines()

        sexps = READ(txt)
        for sexp in sexps:
            EVAL(sexp, env)

@contextmanager
def catch_jk_errors():
    try:
        yield
    except ParseException as p:
        print("Error in parsing: ", p)
    except UnboundError as e:
        print("Unbound symbol used: ", e)
    except MalformedLetStructure as e:
        print("Incorrect use of let: ", e)
    except MalformedExpression as e:
        print("Malformed expression: ", e)

def main():
    if len(sys.argv) == 2:
        with catch_jk_errors():
            load_file(sys.argv[1])

    while True:
        with catch_jk_errors():
            inp = input("user> ")
            print(rep(inp))

env = Env()
env.set('+', lambda a,b: a+b)
env.set('-', lambda a,b: a-b)
env.set('*', lambda a,b: a*b)
env.set('/', lambda a,b: a/b)
env.set('<', lambda a,b: a<b)

main()