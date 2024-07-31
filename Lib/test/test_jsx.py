from jsx import jsx
import sys
import unittest

from pathlib import Path


TEST_DATA = Path(__file__).parent / 'jsx_data'


tests = [
    <img src="test.jpg" />,
    <a href="google.com">"Click here!"</a>,
    <a href="google.com"><b>"Click here!"</b></a>,
    <div style={{"color": "red"}}>{"Hello, world!"}</div>,
    <div>
        {[<p>f"Row: {i}"</p> for i in range(10)]}
    </div>,
    <p style={{'backgroundColor': 'blue', 'marginTop': '10px'}}>"test"</p>,
    <div>
        <h1>"Title"</h1>
        <p>"Paragraph"</p>
        {<footer/> if True else None}
    </div>
]


def jsx_update_snapshots():
    for i, test in enumerate(tests):
        (TEST_DATA / f"jsx_{i}.html").write_text(str(test))


class JSX_Tests(unittest.TestCase):
    maxDiff = None

    def test_JSX_output(self):
        for i, test in enumerate(tests):
            snapshot = (TEST_DATA / f"jsx_{i}.html").read_text()
            with self.subTest(test_input=test):
                self.assertEqual(str(test), snapshot)


def main():
    if __name__ != '__main__':
        return
    elif len(sys.argv) > 1 and sys.argv[1] == '--snapshot-update':
        jsx_update_snapshots()
        sys.exit(0)
    unittest.main()


main()
