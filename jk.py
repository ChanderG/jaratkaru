from dataclasses import dataclass
import sys
from contextlib import contextmanager
import operator as op
from functools import partial

class Token:
    def __init__(self, val: str, pos: int, line: int, txt: [str]):
        self.val = val
        self.pos = pos
        self.line = line
        self.txt = txt

    def __str__(self):
        return self.val
    def __repr__(self):
        return self.val

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
class TypeNotImplemented(Exception):
    pass
class IncorrectArgument(Exception):
    pass

def autowrap_raw(item):
    if isinstance(item, Sexp):
        return item # already in the right format!
    if isinstance(item, int):
        return SexpAtom(item, None)
    if isinstance(item, str):
        # all string return values are atoms
        # not symbols
        return SexpAtom(item, None)
    if isinstance(item, list):
        items = list(map(autowrap_raw, item))
        return SexpList(items, None)
    if item in [None, True, False]:
        return SexpAtom(item, None)
    raise TypeNotImplemented(f"the type {type(item).__name__} is not implemented in Jaratkaru")

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
                if ch == ";": # handle comments
                    break
                if ch in ["(", ")", "'", "`", ","]:
                    push(Token(ch, idx+1, lineno, self.txt))
                elif ch == " ":
                    pass
                elif ch == '"':
                    tok = ch
                    start = idx
                    while idx+1 < len(line) and line[idx+1] not in ['"']:
                        idx += 1
                        tok = tok + line[idx]
                    if idx + 1 == len(line): # reached end of line without finding "
                        # create a temp token to use it for error formatting
                        t = Token(tok, start, lineno, self.txt)
                        raise ParseException("Unbalanced \" found" + t.format_loc())
                    else:
                        # consume the closing "
                        idx += 1
                        tok = tok + line[idx]
                        push(Token(tok, start, lineno, self.txt))
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
                if token.val[0] == '"' and token.val[-1] == '"':
                    return SexpAtom(token.val[1:-1], token)
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

        self.ast = results
        return results

    def post_parse(self):
        self._post_parse(self.ast)
        return self.ast

    def _post_parse(self, sexps):
        macros = {"'": "quote",
                  "`": "quasiquote",
                  ",": "unquote",}
        i = 0
        while i < len(sexps):
            if isinstance(sexps[i], SexpList):
                self._post_parse(sexps[i].val)
            elif isinstance(sexps[i], SexpSymbol):
                if sexps[i].val in macros.keys():
                    if isinstance(sexps[i+1], SexpList):
                        self._post_parse(sexps[i+1].val)
                    new_lis = [SexpSymbol(macros[sexps[i].val], sexps[i].tok), sexps[i+1]]
                    sexps[i] = SexpList(val=new_lis, tok=sexps[i].tok)
                    del sexps[i+1]

            i += 1

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

    def mset(self, kv_dict):
        for k, v in kv_dict.items():
            self.set(k, v)

class Proc:
    def __init__(self, params, body, env, is_macro=False):
        self.params = params
        self.body = body
        self.env = env
        self.is_macro = is_macro

    def __call__(self, *args):
        # new env for the func context
        l_env = Env(self.env)
        # update all params
        for p, a in zip(self.params.val, args):
            l_env.set(p.val, a)
        # actual eval of forms in the lambda
        for exp in self.body:
            res = EVAL(exp, l_env)
        return res

def READ(inp):
    p = Parser(inp)
    res = p.parse()
    res = p.post_parse()
    return res

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

    condition = EVAL(sexp.val[1], env).val
    if condition:
        return EVAL(sexp.val[2], env)
    else:
        if len(sexp.val) == 4:
            return EVAL(sexp.val[3], env)
        else:
            return None

def eval_progn(sexp, env):
    res = None
    for se in sexp.val[1:]:
        res = EVAL(se, env)
    return res

def eval_lambda(sexp, env):
    if len(sexp.val) < 3:
        raise MalformedExpression("too few exp in lambda definition" + sexp.tok.format_loc())

    if not isinstance(sexp.val[1], SexpList):
        raise MalformedExpression("arg definition should be a list" + sexp.tok.format_loc())

    return Proc(sexp.val[1], sexp.val[2:], env)

def eval_quote(sexp, env):
    if len(sexp.val) != 2:
        raise MalformedExpression("single arg expected to quote" + sexp.tok.format_loc())

    return sexp.val[1]

def eval_eval(sexp, env):
    if len(sexp.val) != 2:
        raise MalformedExpression("single arg expected to eval" + sexp.tok.format_loc())

    return EVAL(EVAL(sexp.val[1], env), env)

def handle_quasiquote_sexp(parexp, pos, env):
    """
    Try to unquote any child of the current exp.
    The curren exp is input as the pos'th child of parexp.

    This trick is used to be able to carry over changes by mutating the parent array.
    """
    sexp = parexp.val[pos]
    if isinstance(sexp, SexpList):
        ff = sexp.val[0]
        if isinstance(ff, SexpSymbol) and ff.val == "unquote":
            if len(sexp.val) != 2:
                raise MalformedExpression("single arg expected to unquote" + sexp.tok.format_loc())
            new_sexp = autowrap_raw(EVAL(sexp.val[1], env))
            new_sexp.tok = sexp.tok
            parexp.val[pos] = new_sexp
        else:
            for ind in range(len(sexp.val)):
                handle_quasiquote_sexp(sexp, ind, env)
            parexp.val[pos] = sexp

def eval_quasiquote(sexp, env):
    if len(sexp.val) != 2:
        raise MalformedExpression("single arg expected to quasiquote" + sexp.tok.format_loc())

    handle_quasiquote_sexp(sexp, 1, env)
    return sexp.val[1]

def eval_defun_or_defmacro(sexp, env, is_macro=False):
    if len(sexp.val) < 4:
        raise MalformedExpression("too few exp in definition" + sexp.tok.format_loc())

    if not isinstance(sexp.val[1], SexpSymbol):
        raise MalformedExpression("name should be second arg for def" + sexp.tok.format_loc())

    if not isinstance(sexp.val[2], SexpList):
        raise MalformedExpression("arg definition should be a list" + sexp.tok.format_loc())

    proc = Proc(sexp.val[2], sexp.val[3:], env, is_macro)
    env.set(sexp.val[1].val, proc)
    return proc

def EVAL(sexp, env):
    if isinstance(sexp, SexpAtom):
        return sexp
    elif isinstance(sexp, SexpSymbol):
        return env.get(sexp)
    elif isinstance(sexp, SexpList):
        if len(sexp.val) == 0:
            return None
        form = sexp.val[0]

        if form.val == "let*":
            return eval_let_star(sexp, env)
        elif form.val == "setq":
            return eval_setq(sexp, env)
        elif form.val == "if":
            return eval_if(sexp, env)
        elif form.val == "progn":
            return eval_progn(sexp, env)
        elif form.val == "lambda":
            return eval_lambda(sexp, env)
        elif form.val == "quote":
            return eval_quote(sexp, env)
        elif form.val == "eval":
            return eval_eval(sexp, env)
        elif form.val == "quasiquote":
            return eval_quasiquote(sexp, env)
        elif form.val == "unquote":
            raise MalformedExpression("unquote cannot be used outside a quasiquote" + sexp.tok.format_loc())
        elif form.val == "defun":
            return eval_defun_or_defmacro(sexp, env, False)
        elif form.val == "defmacro":
            return eval_defun_or_defmacro(sexp, env, True)
        else:
            proc = EVAL(sexp.val[0], env)
            if hasattr(proc, "is_macro") and proc.is_macro:
                form = proc(*sexp.val[1:]) # apply on un-evaled args
                return EVAL(form, env)
            else:
                args = list(map(lambda x: EVAL(x, env), sexp.val[1:]))
                return autowrap_raw(proc(*args)) # eval args and then apply
    else:
        return sexp # not even an sexp here

def PRINT(sexp):
    if isinstance(sexp, SexpList):
        res = ""
        for s in sexp.val:
            res += " "
            res +=  PRINT(s)
        return "(" + res[1:] + ")"
    elif isinstance(sexp, SexpAtom):
        if isinstance(sexp.val, str):
            return '"' + sexp.val + '"'
        else:
            return str(sexp.val)
    elif isinstance(sexp, Sexp):
        return str(sexp.val)
    else:
        return str(sexp) # not a sexp

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

# Built-ins

def atom2(oper):
    def fun(x, y):
        print(x, y)
        if not isinstance(x, SexpAtom):
            raise IncorrectArgument("exected atom")
        if not isinstance(y, SexpAtom):
            raise IncorrectArgument("exected atom")
        return oper(x.val, y.val)
    return fun

def anyN(oper):
    def fun(*args):
        print(args)
        un_args = list(map(lambda x: x.val, args))
        return oper(*un_args)
    return fun

def list1(oper):
    def fun(lis):
        if not isinstance(lis, SexpList):
            raise IncorrectArgument("exected list")
        return oper(lis.val)
    return fun

env.mset({'+': atom2(op.add), '-': atom2(op.sub),
          '*': atom2(op.mul), '/': atom2(op.truediv)})
env.mset({'>': anyN(op.gt), '<': anyN(op.lt),
          '>=': anyN(op.ge), '<=': anyN(op.le), '=': anyN(op.eq)})
env.set('print', anyN(print))
env.mset({'car': list1(lambda x: x[0]), 'cdr': list1(lambda x: x[1:]),
          'len': list1(len),})


main()
