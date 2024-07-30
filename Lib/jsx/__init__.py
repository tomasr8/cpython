__all__ = ["Component", "Fragment", "jsx"]


class Component:
    def __init__(self, props):
        self.props = props

    def render(self):
        raise NotImplementedError


class Fragment(Component):
    def render(self):
        return self.props["children"]


class JSXElement:
    def __init__(self, tag, props, children):
        self.tag = tag
        self.props = props
        self.children = children

    def __repr__(self):
        tag = self.tag if isinstance(self.tag, str) else self.tag.__name__
        if not self.children:
            return f"<{tag} {self.props} />"
        return f"<{tag} {self.props}>{self.children}</{tag}>"

    def __str__(self):
        match self.tag:
            case str():
                props = " ".join([f'{k}="{v}"' for k, v in self.props.items()])
                if props:
                    props = f" {props}"
                children = _flatten(str(child) for child in self.children)
                children = "\n".join(_indent(child) for child in children)
                return f"<{self.tag}{props}>\n{children}\n</{self.tag}>"
            case _:
                component = self.tag({**self.props, "children": self.children})
                rendered = component.render()
                match rendered:
                    case None:
                        return ""
                    case tuple() | list():
                        return "\n".join(str(child) for child in rendered)
                    case _:
                        return str(rendered)


def jsx(tag, props=None, *children):
    if props is None:
        props = {}
    return JSXElement(tag, props, children)


def _indent(text, spaces=4):
    return "\n".join(f"{' ' * spaces}{line}" for line in text.split("\n"))


def _flatten(children):
    for child in children:
        if isinstance(child, (list, tuple)):
            yield from _flatten(child)
        else:
            yield child
