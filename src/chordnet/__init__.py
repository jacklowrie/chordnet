"""# A Python Library for Distributed Computing

ChordNet implements the chord protocol, introduced by Stoica et al.
It implements a distributed hash table.

## Project Links
- [Source (github)](https://github.com/jacklowrie/chordnet)
- [Issues](https://github.com/jacklowrie/chordnet/issues)
- [Download](https://github.com/jacklowrie/chordnet/releases)
- [History](https://github.com/jacklowrie/chordnet/releases)
- [PyPI](https://pypi.org/project/chordnet/)

.. include:: ../../README.md
   :start-line: 16
""" # noqa: D415 (this docstring is rendered by pdoc)
from loguru import logger

from .chordnet import ChordNet

logger.disable("chordnet")

__all__=['ChordNet']
