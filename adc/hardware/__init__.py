"""1.1 Hardware hiding.

Every module in this package hides how a physical device is driven or read.
Each one declares an abstract interface and ships two implementations behind
it, a real one and a simulated one. Nothing above this package ever sees a
raw count, a pin number or a byte string.
"""
