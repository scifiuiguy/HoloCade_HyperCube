# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Mirror HoloCadeUDPTransport packet layout (HoloCade_Unity Runtime/Core/Networking)."""

from __future__ import annotations

import struct
from typing import Final

PACKET_START_MARKER: Final[int] = 0xAA


class DataType:
    BOOL = 0
    INT32 = 1
    FLOAT = 2
    STRING = 3
    BYTES = 4


def crc8_xor(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
    return c & 0xFF


def build_packet(data_type: int, channel: int, payload: bytes) -> bytes:
    body = bytes([PACKET_START_MARKER, data_type & 0xFF, channel & 0xFF]) + payload
    return body + bytes([crc8_xor(body)])


def build_float(channel: int, value: float) -> bytes:
    p = struct.pack("<f", float(value))
    return build_packet(DataType.FLOAT, channel, p)


def build_int32(channel: int, value: int) -> bytes:
    p = struct.pack("<i", int(value))
    return build_packet(DataType.INT32, channel, p)
