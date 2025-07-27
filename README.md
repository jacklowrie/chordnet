# chordnet
Python implementation of the chord protocol, introduced by Stoica et al
This library began as a group project for cs536 at Purdue University in
Fall 2024.

## Installation
`pip install chordnet`
`uv add chordnet`

## Usage
to stay consistent with the language from the original
paper, we recommend importing this package as `ring`:
```python
from chordnet import Node as ring
```
This fits with the concept of "joining" an existing ring network, or creating a
new one (`ring.join(...)`, `ring.create()`. Examples follow this practice.

## High level roadmap
- [x] port over code from course project
- [ ] set up repo/project workflows, including using `uv`
- [ ] make sure nodes can run on a single computer (same IP, diff't ports)
- [ ] add robust testing
- [ ] refactor to use asyncio

