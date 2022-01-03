# _*_ conding: utf-8 _*_

from re import compile
from operator import add, sub, mul, floordiv, gt, lt, eq, ne
from functools import reduce # Python3


class Nothing(Exception):
    """
    Exception indicating parser failure
    Only used internally
    """
    pass


class ParserFailure(Exception):
    """
    Exception indicating parser failure
    User responsible
    """
    pass


class Parser:
    """
    Base class for parser
    """
    def __init__(self, do_f):
        self.do_f = do_f

    def __call__(self, s):
        def run(m, nullable=False, throwable=False):
            """
            Run a parser `m`, while chaining its state under the hood.
            Possibly returns `None` if `nullable=True` is specified; otherwise, skip the remaining task.
            Specifying `throwable=True` will raise a user responsible exception, instead.
            """
            nonlocal s
            r = m(s)
            if r is not None:
                (a, s) = r
                return a
            # Note that s is unchanged if the computation fails
            if nullable:
                return None
            if throwable:
                raise ParserFailure
            raise Nothing
        try:
            return (self.do_f(run), s)
        # Leave `ParserFailure` uncaptured
        except Nothing:
            return None

    def bind(self, f):
        """
        Monadic bind operator for parser combination
        """
        @parser_do
        def bind_self_f(run):
            return run(f(run(self)))
        return bind_self_f

    def __and__(self, p):  # &
        """
        Run self then p.
        Two results are returned as a list.
        Have higher precedence than `|`
        """
        @parser_do
        def self_then_p(run):
            return [run(self), run(p)]
        return self_then_p

    def __or__(self, p):  # |
        """
        Run self first. if it fails, run p.
        """
        @parser_do
        def self_or_p(run):
            a = run(self, nullable=True)
            if a is not None:
               return a
            return run(p)
        return self_or_p

    def __rshift__(self, p):  # >>
        """
        Run self then p (discard the result of self)
        Have higher precedence than `&`
        """
        @parser_do
        def discard_self_then_p(run):
            run(self)
            return run(p)
        return discard_self_then_p

    def __lshift__(self, p):  # <<
        """
        Run self then p (discard the result of p)
        Have higher precedence than `&`
        """
        @parser_do
        def self_then_discard_p(run):
            a = run(self)
            run(p)
            return a
        return self_then_discard_p

    def __gt__(self, f):  # >
        """
        Run self then apply the function f with the normal output
        Fliped version of fmap
        """
        @parser_do
        def f_of_self(run):
            return f(run(self))
        return f_of_self


def parser_do(f):
    """
    Decorator
    Mimic Haskell-like do notation
    """
    return Parser(f)


class Get (Parser):
    """
    Get the current state
    """
    def __init__(self):
        pass

    def __call__(self, s):
        return (s, s)


get = Get()


class put (Parser):
    """
    Update the current state
    """
    def __init__(self, s):
        self.s = s

    def __call__(self, _):
        return (self.s, self.s)


class Fail (Parser):
    """
    Always fail
    """
    def __init__(self):
        pass

    def __call__(self, _):
        return None


fail = Fail()


def unit(a):
    """
    Monadic unit
    Always succeed, returning `a`
    """
    @parser_do
    def ret_a(run):
        return a
    return ret_a


empty = unit('')


def pattern(pstr, flags=0):
    """
    Recoginize regular expression `pstr`
    Possibly fail
    """
    pat = compile(pstr, flags=flags)
    @parser_do
    def p(run):
        s = run(get).strip()
        m = pat.match(s)
        if m is None:
            return run(fail)
        run(put(s[m.end():]))
        return s[:m.end()]
    return p


def word(pstr):
    """
    Recoginize `word`
    Possibly fail
    """
    pos = len(pstr)
    @parser_do
    def p(run):
        s = run(get).strip()
        if s[:pos] == pstr:
            run(put(s[pos:]))
            return pstr
        return run(fail)
    return p


def optional(p):
    """
    Return an empty or singleton list.
    Always succeed
    """
    @parser_do
    def opt_p(run):
        a = run(p, nullable=True)
        return [] if a is None else [a]
    return opt_p

def moreThan0(p):
    """
    Run p repeatedly as long as possible.
    The results are returned as a possibly empty list.
    Always succeed
    """
    @parser_do
    def q(run):
        s = run(get)
        a = run(p)
        # Consume at least one character; otherwise, loop forever
        if len(run(get)) < len(s):
            return a
        run(fail)

    @parser_do
    def p_star(run):
        a = []
        while True:
            b = run(q, nullable=True)
            if b is None: break
            a.append(b)
        return a
    return p_star


def moreThan1(p):
    """
    Run p repeatedly at least once
    The results are returned as a non-empty list.
    Possibly fail
    """
    @parser_do
    def p_plus(run):
        return [run(p)] + run(moreThan0(p))
    return p_plus


def sepBy(p, sep):
    """
    Recognizes a sequence of `p` separated by `sep`
    The results are returned as a non-empty list.
    Possibly fail
    """
    @parser_do
    def p_sepBy_sep(run):
        return [run(p)] + reduce(add, run(moreThan0(sep & p)), [])
    return p_sepBy_sep


def peek(p):
    """
    Looks ahead (never consume input string)
    Return True or False
    Always succeed
    """
    @parser_do
    def q(run):
        s = run(get)
        r = run(p, nullable=True)
        if r is not None:
            run(put(s))
            return True
        return False
    return q


def fatal(msg):
    @parser_do
    def p(run):
        s = run(get)
        raise ParserFailure("{}:{}".format(msg, s[:16]))
    return p


# Abbreviations

pat = pattern
w   = word
opt = optional
