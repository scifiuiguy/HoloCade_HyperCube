# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.

import struct
import unittest

from holocade_hypercube.protocol.holocade_udp import (
    PACKET_START_MARKER,
    DataType,
    build_float,
    crc8_xor,
)


class TestHolocadeUdp(unittest.TestCase):
    def test_float_packet_crc_matches_xor_scheme(self):
        pkt = build_float(100, 0.52)
        self.assertEqual(pkt[0], PACKET_START_MARKER)
        self.assertEqual(pkt[1], DataType.FLOAT)
        self.assertEqual(pkt[2], 100)
        body = pkt[:-1]
        self.assertEqual(pkt[-1], crc8_xor(body))
        self.assertAlmostEqual(struct.unpack_from("<f", pkt, 3)[0], 0.52, places=5)


if __name__ == "__main__":
    unittest.main()
