# Contributing
Please get in touch before starting work or opening a PR, to avoid
duplicating work.

## Development
This project uses `uv` and `pre-commit`.
to install `uv`, you can use homebrew:
```sh
brew install uv
```
or follow Astral's instructions for installing
in your environment: [uv documentation](https://docs.astral.sh/uv/getting-started/installation/)

Once `uv` is installed, clone this repo, then run the following:
```sh
uv sync --locked --all-extras --dev # this installs all dev dependencies, without upgrading any.
uv run pre-commit install # sets up pre-commit
```

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
