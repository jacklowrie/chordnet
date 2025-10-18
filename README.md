# ChordNet
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/jacklowrie/chordnet/main.yml?logo=GitHub&label=Main%20Branch%20Build)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/jacklowrie/chordnet/release.yml?logo=GitHub&label=PyPI%20Published%20Build)

![GitHub License](https://img.shields.io/github/license/jacklowrie/chordnet?logo=github)
![PyPI - Types](https://img.shields.io/pypi/types/chordnet?logo=pypi)
![PyPI - Version](https://img.shields.io/pypi/v/chordnet?logo=pypi)
![PyPI - Downloads](https://img.shields.io/pypi/dm/chordnet?logo=pypi)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/chordnet?logo=pypi)
![PyPI - Implementation](https://img.shields.io/pypi/implementation/chordnet?logo=pypi)


Python implementation of the chord protocol, introduced by Stoica et al.
This library began as a [group project](https://github.com/jacklowrie/chord) for cs536 at Purdue University in
Fall 2024.

## Installation
`pip install chordnet`

`uv add chordnet`


## Usage
To stay consistent with the language from the original paper, we recommend
naming your chordnet attribute `ring`:
```python
from chordnet import ChordNet

ring = new ChordNet(...)
ring.create() # or ring.join(...)
#...application logic...
ring.leave()
# end program
```
This fits with the concept of "joining" an existing ring network, or creating a
new one. Examples follow this practice.

At present, this package only supports IP lookup. All application-dependent
logic (state transfer, etc) must be handled by the application.
The easiest way to do this is to initialize ChordNet as an attribute on
an application class:
```python
class App:
    def __init__(self, ip: str, chordnet_port: int) -> None:
        self._ring = ChordNet(ip, chordnet_port)

    def start(
        self, ip = None: str | None, port = None: int | None
    ) -> None:
        if ip and port:
            self._ring.join(ip, port)
        elif not ip and not port:
            self._ring.create()
        else:
            print("need both or neither")
            return
    def stop(self) -> None:
        self._ring.leave()
```
In future versions, we hope to support in-package state transfer.
