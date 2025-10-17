"""step.py: helper for manual scripts."""

from chordnet._node import _Node as ChordNode


def step(node: ChordNode) -> None:
    """Runs the periodic tasks for the node once."""
    node.stabilize()
    node.fix_fingers()

    print(f"pred: {node.predecessor} succ: {node.successor()}")
    print(node.finger_table)
