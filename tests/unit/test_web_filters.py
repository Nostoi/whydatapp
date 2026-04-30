from why.web.filters import parse_query


def test_defaults():
    s = parse_query({})
    assert s.disposition is None
    assert s.q == ""
    assert s.order_by == "installed_at"
    assert s.order_dir == "desc"


def test_full_parse():
    s = parse_query({
        "disposition": "doc",
        "project": "p",
        "manager": "brew",
        "device": "abc",
        "incomplete": "1",
        "q": "ripgrep",
        "order_by": "manager",
        "order_dir": "asc",
        "limit": "200",
        "offset": "100",
    })
    assert s.disposition == "doc"
    assert s.project == "p"
    assert s.manager == "brew"
    assert s.device_id == "abc"
    assert s.incomplete_only is True
    assert s.q == "ripgrep"
    assert s.order_by == "manager"
    assert s.order_dir == "asc"
    assert s.limit == 200
    assert s.offset == 100


def test_rejects_bad_order_by():
    s = parse_query({"order_by": "nope"})
    assert s.order_by == "installed_at"
