from pipeline.io.jsonl import dumps_line, loads_line


def test_jsonl_round_trip_dict():
    obj = {"id": "silkg:Gene:9606:1", "synonyms": ["A1BG", "A1B"], "n": 1}
    line = dumps_line(obj)
    assert line.endswith(b"\n")
    assert loads_line(line) == obj
    assert loads_line(line.decode("utf-8")) == obj


def test_jsonl_round_trip_nested():
    obj = {"a": [{"b": 1}, {"c": None}]}
    assert loads_line(dumps_line(obj)) == obj
