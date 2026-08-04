from pipeline.progress import configure, count_lines, track


def test_track_disabled_yields_all_items(tmp_path):
    configure(enabled=False)
    items = list(track(range(5), total=5, desc="test", unit="it"))
    assert items == [0, 1, 2, 3, 4]


def test_count_lines(tmp_path):
    path = tmp_path / "sample.jsonl"
    path.write_text("a\nb\nc\n", encoding="utf-8")
    assert count_lines(path) == 3
