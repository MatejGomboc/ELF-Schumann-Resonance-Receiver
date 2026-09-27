"""Minimal KiCad S-expression reader/writer.

Quoted strings are parsed into :class:`Q` so they round-trip with quotes;
bare atoms stay plain ``str``. Lists are plain Python lists.
"""


class Q(str):
    """A quoted S-expression string."""


def parse(text):
    tokens = _tokenize(text)
    pos = 0
    stack = [[]]
    while pos < len(tokens):
        tok = tokens[pos]
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
        pos += 1
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def _tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            i += 1
        elif c in '()':
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == '\\':
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(Q(''.join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def fmt_num(v):
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, int):
        return str(v)
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def dumps(node, indent=0):
    """Serialise in KiCad's tab-indented style."""
    if not isinstance(node, list):
        return _atom(node)
    if not node:
        return '()'
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return '(' + ' '.join(_atom(x) for x in node) + ')'
    # keep short (xy ...) runs on one line like KiCad does
    if node[0] == 'pts':
        return '(pts ' + ' '.join(dumps(x) for x in node[1:]) + ')'
    pad = '\t' * (indent + 1)
    parts = []
    head = []
    for x in node:
        if isinstance(x, list):
            break
        head.append(_atom(x))
    out = '(' + ' '.join(head)
    for x in node[len(head):]:
        parts.append('\n' + pad + dumps(x, indent + 1))
    return out + ''.join(parts) + '\n' + '\t' * indent + ')'


def _atom(x):
    if isinstance(x, Q):
        return '"' + _escape(x) + '"'
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return fmt_num(x)
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    return str(x)


def _escape(s):
    # parse() keeps backslash escapes verbatim, so only escape bare quotes
    out = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            out.append(s[i:i + 2])
            i += 2
            continue
        out.append('\\"' if s[i] == '"' else s[i])
        i += 1
    return ''.join(out)


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def find1(node, key, default=None):
    r = find(node, key)
    return r[0] if r else default
