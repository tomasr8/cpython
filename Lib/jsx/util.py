import re


def indent(text, spaces=4):
    return "\n".join(f"{' ' * spaces}{line}" for line in text.split("\n"))


def flatten(children):
    for child in children:
        if isinstance(child, (list, tuple)):
            yield from flatten(child)
        else:
            yield child


CAMELCASE = re.compile(r"(?<!^)(?=[A-Z])")


def dash_case(name):
    return CAMELCASE.sub("-", name).lower()
