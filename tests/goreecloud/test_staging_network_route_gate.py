"""Offline route table fixtures for the private Search startup boundary."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[2] / "scripts" / "staging_start_search.py"
spec = importlib.util.spec_from_file_location("staging_route_gate", FILE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

HEADER = "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT"
INTERNAL = "eth0\t00F71DAC\t00000000\t0001\t0\t0\t0\tF0FFFFFF\t0\t0\t0"
DEFAULT = "eth0\t00000000\t010011AC\t0003\t0\t0\t0\t00000000\t0\t0\t0"
PUBLIC = "eth1\t0000000A\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0"
LOOPBACK6 = "0" * 32 + " 80 " + "0" * 32 + " 00 " + "0" * 32 + " 00000000 00000000 00000000 00000001 lo"
EXTERNAL6 = "0" * 32 + " 00 " + "0" * 32 + " 00 " + "0" * 32 + " 00000000 00000000 00000000 00000003 eth0"


class RouteTableGuardTests(unittest.TestCase):
    def test_only_expected_staging_internal_subnet_is_accepted(self):
        self.assertTrue(gate._parse_ipv4_route_table(HEADER + "\n" + INTERNAL))
        self.assertTrue(gate._parse_ipv6_route_table(LOOPBACK6))

    def test_live_shared_tor_default_route_is_rejected(self):
        for rows in (DEFAULT, INTERNAL + "\n" + DEFAULT,
                     INTERNAL + "\n" + PUBLIC, PUBLIC):
            with self.subTest(rows=rows):
                self.assertFalse(gate._parse_ipv4_route_table(HEADER + "\n" + rows))

    def test_missing_truncated_or_malformed_ipv4_routes_fail_closed(self):
        for text in ("", HEADER, HEADER+"\ncorrupt", HEADER+"\n"+INTERNAL.replace("00F71DAC", "abc"),
                     HEADER+"\n"+INTERNAL.replace("00000000", "FFFFFFFF", 1)):
            with self.subTest(text=text[-45:]):
                self.assertFalse(gate._parse_ipv4_route_table(text))

    def test_ipv6_routable_interface_rejected(self):
        self.assertFalse(gate._parse_ipv6_route_table(LOOPBACK6 + "\n" + EXTERNAL6))
        self.assertFalse(gate._parse_ipv6_route_table("bad route"))

    def test_missing_proc_data_is_not_permitted(self):
        with patch.object(gate.Path, "read_text", side_effect=OSError("synthetic")):
            self.assertFalse(gate.staging_namespace_confined())

    def test_both_route_tables_required_without_network_probe(self):
        with patch.object(gate.Path, "read_text", side_effect=[
            HEADER + "\n" + INTERNAL, LOOPBACK6
        ]) as reader:
            self.assertTrue(gate.staging_namespace_confined())
            self.assertEqual(2, reader.call_count)


if __name__ == "__main__":
    unittest.main()
