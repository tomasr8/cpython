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

PyJSX is a fork of [CPython](github.com/python/cpython) which extends its grammar to support (almost) all JSX syntax natively. This means that there is not transpilation necessary. You can directly execute the above example.

## Installation

Clone this repository and run:

```bash
git clone --branch jsx github.com/tomasr8/cpython.git
cd cpython
./configure
make
```

This will create a `./python` binary with JSX support. 

## Usage

Almost all JSX syntax is supported, with two notable exceptions:

- Text nodes must be valid Python strings: `<p>"Paragraph"</p>`. This is illegal: `<p>Paragrah</p>`. This limitation stems from the the way the tokenizer and parser operate and would require a lot of effort to get it working. This seems like an acceptable compromise.
- Spread syntax: `<div {...props}></div>`. This probably only requires modification to the grammar (`Grammar/python.gram`) but I haven't looked into it too deeply.

Any module containing JSX code must include the following import:

```python
from jsx import jsx
```

Normal and self-closing tags:

```python
x = <div></div>
y = <img />
```

Props:

```python
<a href="example.com">"Click me!"</a>
<div style={{'color': 'red'}}>"..."</div>
```

Nested expressions:

```python
<div>
    {[<p>f"Row: {i}"</p> for i in range(10)]}
</div>
```

Fragments:

```python
fragment = (
    <>
        <p>"1st paragraph"</p>
        <p>"2nd paragraph"</p>
    </>
)
```

Custom components:

```python
from jsx import jsx, Component

class Header(Component):
    def render():
        return <h1>{self.props['children']}</h1>

header = <Header>"Title"</Header>
print(header)
```

## Prior art

[packed](https://github.com/michaeljones/packed) - JSX-style preprocessor for Python 
