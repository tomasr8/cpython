# PyJSX - Native support for JSX in Python


```python
from jsx import jsx

def get_body(title, href):
    return (
        <body>
            <h1>{title}</h1>
            <p>
                <a href={href}>"Click me!"</a>
            </p>
        </body>
    )

print(get_body())
```

## What is it?

PyJSX is a fork of [CPython](github.com/python/cpython) which extends the grammar to support (almost) all JSX syntax natively. This means that there is not transpilation necessary - you can directly execute the above example.

## Installation

```bash
git clone --branch jsx github.com/tomasr8/cpython.git
cd cpython
./configure
make
```

This will create a `./python` binary with JSX support. 
If this doesn't work, have a look at the official [build instructions](https://github.com/python/cpython?tab=readme-ov-file#build-instructions).

## Usage

Almost all JSX syntax is supported, with two notable exceptions:

- Text nodes must be valid Python strings: `<p>"Paragraph"</p>`. This limitation stems from the the way the tokenizer and parser operate and would require a lot of changes to support properly.
- Spread syntax: `<div {...props}></div>`. This probably only requires modification to the grammar (`Grammar/python.gram`) but I haven't looked into it too deeply.

Any module containing JSX code must include the following import:

```python
from jsx import jsx
```
This because JSX components are internally represented as a function call `jsx(tag, props, children)`.

### Normal and self-closing tags:

```python
from jsx import jsx

x = <div></div>
y = <img />
```

### Props:

```python
from jsx import jsx

<a href="example.com">"Click me!"</a>
<div style={{"color": "red"}}>"..."</div>
```

### Nested expressions:

```python
from jsx import jsx

<div>
    {[<p>f"Row: {i}"</p> for i in range(10)]}
</div>
```

### Fragments:

```python
from jsx import jsx

fragment = (
    <>
        <p>"1st paragraph"</p>
        <p>"2nd paragraph"</p>
    </>
)
```

### Custom components:

Custom components should inherit from `Component` and provide a `render()` function which returns JSX. The props are passed as `self.props` and children as `self.props["children"]`.

```python
from jsx import jsx, Component

class Header(Component):
    def render():
        return <h1>{self.props["children"]}</h1>

header = <Header>"Title"</Header>
print(header)
```

## Prior art

Inspired by [packed](https://github.com/michaeljones/packed) - JSX-style preprocessor for Python 
