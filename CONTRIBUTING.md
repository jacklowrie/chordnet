# Contributing
Please get in touch before starting work or opening a PR, to avoid
duplicating work. Opening an issue works well for now. If you see an unassigned
open issue you want to work on, please leave a comment on it - assigned issues
are spearheaded by the assignee, if they need help they will coordinate on the
issue.

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
