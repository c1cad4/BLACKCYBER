"""Regression checks for BOOT IBC integrity and careful evidence classification."""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class BootForensicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=load("boot_audit","scripts/osmosis_boot_audit.py")
        cls.exits=load("boot_exits","scripts/osmosis_boot_exits.py")

    def test_correct_ibc_denom(self):
        self.assertEqual(self.audit.BOOT_HASH,self.audit.EXPECTED_BOOT_HASH)
        self.assertEqual(self.audit.BOOT_DENOM,"ibc/FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4")
        self.assertNotEqual(self.audit.BOOT_HASH,self.audit.EXCLUDED_CRO_HASH)
        self.assertEqual(self.exits.BOOT_HASH,self.exits.EXPECTED)

    def test_pool_denom_requires_exact_asset_field(self):
        denom=self.audit.BOOT_DENOM
        self.assertFalse(self.audit.contains_exact_denom({"name":denom},denom))
        self.assertFalse(self.audit.contains_exact_denom({"symbol":"BOOT","token_denom":"ibc/OTHER"},denom))
        self.assertTrue(self.audit.contains_exact_denom({"pool_assets":[{"token":{"denom":denom,"amount":"100"}}]},denom))

    def test_historical_pools_not_overclaimed(self):
        self.assertEqual(self.exits.POOLS,(596,597))
        self.assertEqual(self.audit.POOLS,(596,597))
        self.assertEqual(self.audit.OPTIONAL_POOL,595)

if __name__ == "__main__":
    unittest.main()
