"""test_node.py: tests for the Node class.

NOTE: many of these tests were AI generated as regression tests, in preparation
for refactoring.
"""
from loguru import logger

logger.enable("chordnet")

# Global test variables
ip: str = "127.0.0.1"
anchor_port: int = 1234
joiner_port: int = 2345

# test with manual stepping of daemon
# test with daemon running (eventual repair)
