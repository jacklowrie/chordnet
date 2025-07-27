# Contributing
Please get in touch before starting work or opening a PR, to avoid
duplicating work.

## Development
This project uses `uv`.

## Files
- `src`: contains the library source code.
  -  `chordnet`: The package.
      - `__init__.py`: package init file.
      - `address.py`: Helper class, its objects represent a chord network address.
      - `net.py`: `_Net` is the helper class that handles networking functions.
      - `node.py`: `Node` is the public class for interacting with a ring network.
      - `py.typed`: empty, indicates to IDEs that type annotations are used.
- `tests`: test code directory (we use `pytest`).
  -  `test_net.py`: tests for the `_Net` class.
  -  `test_node.py`: tests for the `Node` class.
- `.gitignore`: excludes files from version control.
- `.python-version`: pins to the dev (and min-supported) version.
- `chord_paper.pdf`: The paper this library implements.
- `LICENSE`: copy of software license.
- `pyproject.toml`: project configuration.
- `README.md`: this file.
- `uv.lock`: lock file for `uv`. pins dependencies to exact versions.
