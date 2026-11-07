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
        cls.verify=load("boot_verify_exits","scripts/osmosis_boot_verify_exits.py")
        cls.reserves=load("boot_reserves","scripts/osmosis_boot_reserves.py")

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

    def test_verifier_only_explicit_lp_exits(self):
        tx={"tx":{"body":{"messages":[
            {"@type":"/osmosis.gamm.v1beta1.MsgExitPool","pool_id":"596",
             "sender":"osmo1example","share_in_amount":"1000",
             "token_out_mins":[{"denom":"uosmo","amount":"10"}]},
            {"@type":"/osmosis.gamm.v1beta1.MsgSwapExactAmountIn","pool_id":"596",
             "sender":"osmo1example"},
            {"@type":"/osmosis.gamm.v1beta1.MsgExitPool","pool_id":"999",
             "sender":"osmo1different"}
        ]}}}
        records=self.verify.classify_messages(tx,596)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["sender_address"],"osmo1example")
        self.assertEqual(records[0]["minimum_tokens_out"][0]["amount_atomic"],"10")
        self.assertEqual(self.verify.classify_messages(tx,597),[])

    def test_exit_rank_does_not_infer_usd_or_person(self):
        rows=[{"hash":"A"*64,"status":"confirmed_successful_lp_exit_message",
               "messages":[{"pool_id":596,"sender_address":"osmo1public"}]}]
        ranked=self.verify.summarize(rows)
        self.assertEqual(ranked[0]["exit_tx_count"],1)
        self.assertIsNone(ranked[0]["total_removed_usd"])
        self.assertEqual(ranked[0]["identity"],"not independently attributed")

    def test_historical_reserve_asset_hash(self):
        self.assertEqual(self.reserves.BOOT_DENOM,self.audit.BOOT_DENOM)
        self.assertEqual(self.reserves.POOLS,(596,597))

    def test_actual_exit_token_amounts_need_unique_event(self):
        good={"logs":[{"msg_index":0,"events":[{"type":"pool_exited","attributes":[
            {"key":"pool_id","value":"596"},
            {"key":"sender","value":"osmo1example"},
            {"key":"tokens_out","value":"12uosmo,340ibc/FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4"}
        ]}]}]}
        found=self.verify.match_pool_exit_events(good,596,"osmo1example")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["tokens_out"][0]["amount_atomic"],"12")
        self.assertEqual(len(found[0]["tokens_out"]),2)
        self.assertEqual(self.verify.match_pool_exit_events(good,597,"osmo1example"),[])
        self.assertEqual(self.verify.match_pool_exit_events(
            {"logs":good["logs"]+good["logs"]},596,"osmo1example"),[])

if __name__ == "__main__":
    unittest.main()
