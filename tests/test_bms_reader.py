import struct
import unittest

from bms_reader import decode_status, make_command


class BmsReaderTests(unittest.TestCase):
    def test_make_command_sets_header_command_and_checksum(self):
        command = make_command(0x97, counter=3)

        self.assertEqual(len(command), 20)
        self.assertEqual(command[:4], b"\xAA\x55\x90\xEB")
        self.assertEqual(command[4], 0x97)
        self.assertEqual(command[16], 3)
        self.assertEqual(command[19], sum(command[:19]) & 0xFF)

    def test_decode_status_extracts_pack_and_cell_values(self):
        frame = bytearray(300)
        struct.pack_into("<H", frame, 6, 3418)
        struct.pack_into("<H", frame, 8, 3422)
        struct.pack_into("<I", frame, 70, 0b11)
        struct.pack_into("<h", frame, 144, 293)
        struct.pack_into("<I", frame, 150, 27347)
        struct.pack_into("<i", frame, 158, -1500)
        struct.pack_into("<h", frame, 162, 268)
        struct.pack_into("<h", frame, 164, 273)
        struct.pack_into("<I", frame, 166, 0)
        struct.pack_into("<h", frame, 170, 125)
        frame[172] = 1
        frame[173] = 87
        struct.pack_into("<I", frame, 174, 200000)
        struct.pack_into("<I", frame, 178, 230000)
        struct.pack_into("<I", frame, 182, 25)
        struct.pack_into("<I", frame, 186, 5750000)
        frame[190] = 99
        struct.pack_into("<I", frame, 194, 3600)
        frame[198] = 1
        frame[199] = 1
        frame[201] = 0

        values = decode_status(frame)

        self.assertEqual(values["cells"], [3.418, 3.422])
        self.assertAlmostEqual(values["voltage"], 27.347)
        self.assertAlmostEqual(values["current"], -1.5)
        self.assertAlmostEqual(values["power"], -41.0205)
        self.assertAlmostEqual(values["cell_delta_mv"], 4.0)
        self.assertEqual(values["soc"], 87)
        self.assertEqual(values["cycles"], 25)
        self.assertTrue(values["charge_enabled"])
        self.assertTrue(values["discharge_enabled"])
        self.assertFalse(values["balancing_active"])

    def test_decode_status_rejects_short_frames(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            decode_status(bytes(299))


if __name__ == "__main__":
    unittest.main()
