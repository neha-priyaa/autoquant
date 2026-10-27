
    def test_scalar_universe_coerced(self, tmp_path):
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "a.yaml").write_text(
            "meta:\n  slug: a\ndata:\n  universe: SPY\n")
        w = load_module().build_snapshot(tmp_path)["workspace"]
        assert w["specs"][0]["universe"] == ["SPY"]
