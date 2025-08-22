# ChordNet
[![Main Branch Status](https://github.com/jacklowrie/chordnet/actions/workflows/main.yml/badge.svg)](https://github.com/jacklowrie/chordnet/actions/workflows/main.yml)
[![PyPI Published](https://github.com/jacklowrie/chordnet/actions/workflows/publish.yml/badge.svg)](https://github.com/jacklowrie/chordnet/actions/workflows/publish.yml)
Python implementation of the chord protocol, introduced by Stoica et al.
This library began as a [group project](https://github.com/jacklowrie/chord) for cs536 at Purdue University in
Fall 2024.

## Installation
`pip install chordnet`

`uv add chordnet`

## Development
See `CONTRIBUTING.md`.

## Usage
to stay consistent with the language from the original paper, we recommend
importing this package as `ring`:
```python
from chordnet import Node as ring
```
This fits with the concept of "joining" an existing ring network, or creating a
new one, (`ring.join(...)`, `ring.create()`.
Examples follow this practice.

## High level roadmap
- [x] port over code from course project
- [x] set up repo/project workflows, including using `uv`
- [x] add robust testing
- [x] Add type annotations
- [ ] make sure old mininet setup/raspi setups still work
- [ ] make sure nodes can run on a single computer (same IP, diff't ports)
- [ ] refactor to use asyncio
