# chordnet
Python Implementation of the chord protocol, introduced by Stoica et al

## Installation

## Usage
`import chordnet as ring`: to stay consistent with the language from the original
paper, we recommend importing this package as `ring`. This fits with the concept
of "joining" an existing ring network, or creating a new one (`ring.join(...)`,
`ring.create()`. Examples follow this practice.

## Dependencies

## Development
This project uses `uv`.


## Files
.
├── `.gitignore`: excludes files from version control.
├── `.python-version`: pins to the dev (and min-supported) version.
├── `chord_paper.pdf`: The paper this library implements.
├── `LICENSE`: copy of software license.
├── `pyproject.toml`: project configuration.
├── `README.md`: this file.
├── `src`: contains the library source code.
│   └── `chordnet`: The package.
│       ├── `__init__.py`: package init file.
│       ├── `address.py`: Helper class, its objects represent a chord network address.
│       ├── `net.py`: `_Net` is the helper class that handles networking functions.
│       ├── `node.py`: `Node` is the public class for interacting with a ring network.
│       └── `py.typed`: empty, indicates to IDEs that type annotations are used.
├── `tests`: test code directory (we use `pytest`).
│   ├── `test_net.py`: tests for the `_Net` class.
│   └── `test_node.py`: tests for the `Node` class.
└── `uv.lock`: lock file for `uv`. pins dependencies to exact versions.
