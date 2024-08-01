from jsx.elements import is_void_element
from jsx.util import indent, flatten, dash_case


__all__ = ["Component", "Fragment", "jsx"]


def Fragment(props):
    return props["children"]


class JSXElement:
    def __init__(self, tag, props, children):
        self.tag = tag
        self.props = props
        self.children = children

    def __repr__(self):
        tag = self.tag if isinstance(self.tag, str) else self.tag.__name__
        return f"<{tag} />"

    def __str__(self):
        match self.tag:
            case str():
                return self._convert_builtin()
            case _:
                return self._convert_component()

    def _convert_builtin(self):
        props = " ".join([f'{k}="{v}"' for k, v in self.props.items()])
        if props:
            props = f" {props}"
        if not self.children:
            if is_void_element(self.tag):
                return f"<{self.tag}{props} />"
            return f"<{self.tag}{props}></{self.tag}>"
        children = flatten(self.children)
        children = flatten(str(child) for child in children)
        children = "\n".join(indent(child) for child in children)
        return f"<{self.tag}{props}>\n{children}\n</{self.tag}>"

    def _convert_component(self):
        rendered = self.tag({**self.props, "children": self.children})
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
    if (style := props.get("style")) and isinstance(style, dict):
        props["style"] = "; ".join([f"{dash_case(k)}: {v}" for k, v in style.items()])
    return JSXElement(tag, props, children)


jsx.Fragment = Fragment
