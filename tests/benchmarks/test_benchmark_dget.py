"""Performance benchmarks for deeppath, using pytest-benchmark.

Not collected by a bare `pytest` run (see `norecursedirs` in pyproject.toml) so the
normal test suite and CI stay fast. Run explicitly:

    pytest tests/benchmarks
    pytest tests/benchmarks --benchmark-compare          # against a saved baseline
    pytest tests/benchmarks --benchmark-save=baseline     # save one
    pytest tests/benchmarks --benchmark-histogram

Same data shapes used throughout the perf investigation in TODO.md, so numbers here
are directly comparable to the ones quoted there.
"""

from __future__ import annotations

import pytest

from deeppath import ddelete, dget, dset, dwalk, flatten, has


def make_deep_dict(depth: int) -> dict:
    """A single chain of nested dicts, `depth` levels deep."""
    data: dict = {"value": 42}
    for i in range(depth):
        data = {f"level{i}": data}
    return data


def make_wide_dict(width: int) -> dict:
    return {f"key{i}": i for i in range(width)}


def make_list_of_dicts(n: int) -> dict:
    return {"items": [{"id": i, "name": f"item{i}", "meta": {"active": i % 2 == 0}} for i in range(n)]}


def make_realistic_document() -> dict:
    """A moderately complex, realistic nested structure."""
    return {
        "users": [
            {
                "id": i,
                "name": f"user{i}",
                "roles": ["admin", "editor"] if i % 5 == 0 else ["viewer"],
                "profile": {
                    "address": {"city": "London", "zip": f"E{i}"},
                    "tags": [f"tag{j}" for j in range(3)],
                },
            }
            for i in range(200)
        ],
        "meta": {"generated": True, "count": 200},
    }


DEEP_DICT = make_deep_dict(50)
WIDE_DICT = make_wide_dict(500)
LIST_OF_DICTS = make_list_of_dicts(500)
REALISTIC_DOC = make_realistic_document()
DEEP_PATH = "/".join(f"level{i}" for i in range(49, -1, -1)) + "/value"
FLATTEN_NESTED = [[[[[i]] for i in range(20)]] for _ in range(50)]


@pytest.mark.benchmark(group="dget-simple")
def test_dget_deep_path(benchmark):
    result = benchmark(lambda: dget(DEEP_DICT, DEEP_PATH))
    assert result == 42


@pytest.mark.benchmark(group="dget-simple")
def test_dget_wide_dict_hit(benchmark):
    result = benchmark(lambda: dget(WIDE_DICT, "key250"))
    assert result == 250


@pytest.mark.benchmark(group="dget-simple")
def test_dget_wide_dict_miss(benchmark):
    result = benchmark(lambda: dget(WIDE_DICT, "nonexistent/path", default=None))
    assert result is None


@pytest.mark.benchmark(group="dget-simple")
def test_dget_list_index(benchmark):
    result = benchmark(lambda: dget(LIST_OF_DICTS, "items[250]/name"))
    assert result == "item250"


@pytest.mark.benchmark(group="dget-wildcard")
def test_dget_list_wildcard_bracket(benchmark):
    result = benchmark(lambda: dget(LIST_OF_DICTS, "items[*]/name"))
    assert len(result) == 500


@pytest.mark.benchmark(group="dget-wildcard")
def test_dget_list_wildcard_star_key(benchmark):
    # Bare "*" over a list never matches -- see TODO.md on the mapping/sequence
    # wildcard split. Kept as its own benchmark: it exercises the no-match,
    # short-circuit path rather than a real fan-out.
    result = benchmark(lambda: dget(LIST_OF_DICTS, "items/*/name"))
    assert result == []


@pytest.mark.benchmark(group="dget-wildcard")
def test_dget_realistic_wildcard(benchmark):
    result = benchmark(lambda: dget(REALISTIC_DOC, "users[*]/profile/address/city"))
    assert len(result) == 200


@pytest.mark.benchmark(group="dget-wildcard")
def test_dget_realistic_nested_wildcard(benchmark):
    result = benchmark(lambda: dget(REALISTIC_DOC, "users[*]/profile/tags[*]"))
    assert len(result) == 600


@pytest.mark.benchmark(group="dget-slice")
def test_dget_list_slice_bounded(benchmark):
    # 300 of the 500 items -- same order of magnitude as the wildcard benchmarks above.
    result = benchmark(lambda: dget(LIST_OF_DICTS, "items[100:400]/name"))
    assert len(result) == 300


@pytest.mark.benchmark(group="dget-slice")
def test_dget_list_slice_full(benchmark):
    # "items[:]" selects the same 500 elements as "items[*]" in
    # test_dget_list_wildcard_bracket above - same data, same result, deliberately set
    # up as a direct comparison. Wildcard iterates the list directly; slice goes
    # through range(*slice.indices(len(node))) + repeated __getitem__, so this is
    # where any overhead from the index-based approach would show up.
    result = benchmark(lambda: dget(LIST_OF_DICTS, "items[:]/name"))
    assert len(result) == 500


# Same paths/data as the dget benchmarks above, so a has-vs-dget comparison in the same
# report is a direct read of has()'s short circuit, not a different-shape comparison.
# The wildcard cases in particular all match on the very first element scanned (every
# item/user has the field being checked), which is exactly where has() should look
# cheapest next to dget() building the full result list.


@pytest.mark.benchmark(group="has-simple")
def test_has_deep_path(benchmark):
    result = benchmark(lambda: has(DEEP_DICT, DEEP_PATH))
    assert result is True


@pytest.mark.benchmark(group="has-simple")
def test_has_wide_dict_hit(benchmark):
    result = benchmark(lambda: has(WIDE_DICT, "key250"))
    assert result is True


@pytest.mark.benchmark(group="has-simple")
def test_has_wide_dict_miss(benchmark):
    result = benchmark(lambda: has(WIDE_DICT, "nonexistent/path"))
    assert result is False


@pytest.mark.benchmark(group="has-simple")
def test_has_list_index(benchmark):
    result = benchmark(lambda: has(LIST_OF_DICTS, "items[250]/name"))
    assert result is True


@pytest.mark.benchmark(group="has-wildcard")
def test_has_list_wildcard_bracket(benchmark):
    result = benchmark(lambda: has(LIST_OF_DICTS, "items[*]/name"))
    assert result is True


@pytest.mark.benchmark(group="has-wildcard")
def test_has_list_wildcard_star_key(benchmark):
    # Mirrors dget_list_wildcard_star_key: bare "*" never matches a list, so this
    # exercises has()'s no-match path, not a short circuit.
    result = benchmark(lambda: has(LIST_OF_DICTS, "items/*/name"))
    assert result is False


@pytest.mark.benchmark(group="has-wildcard")
def test_has_realistic_wildcard(benchmark):
    result = benchmark(lambda: has(REALISTIC_DOC, "users[*]/profile/address/city"))
    assert result is True


@pytest.mark.benchmark(group="has-wildcard")
def test_has_realistic_nested_wildcard(benchmark):
    result = benchmark(lambda: has(REALISTIC_DOC, "users[*]/profile/tags[*]"))
    assert result is True


@pytest.mark.benchmark(group="dset")
def test_dset_build_new(benchmark):
    def build():
        data: dict = {}
        for i in range(200):
            dset(data, f"items[{i}]/id", i)
            dset(data, f"items[{i}]/name", f"item{i}")
        return data

    result = benchmark(build)
    assert len(result["items"]) == 200


@pytest.mark.benchmark(group="dset")
def test_dset_deep_path(benchmark):
    def build():
        data: dict = {}
        dset(data, DEEP_PATH, 42)
        return data

    result = benchmark(build)
    assert dget(result, DEEP_PATH) == 42


@pytest.mark.benchmark(group="ddelete")
def test_ddelete_single(benchmark):
    def delete_one():
        # Fresh structure each call since ddelete mutates - built from a plain dict
        # literal (not dset) so construction cost stays negligible next to the delete
        # itself, matching the single-key shape of dget_wide_dict_hit/deep_path_get.
        data = {"a": {"b": 1, "c": 2}}
        ok = ddelete(data, "a/b")
        return ok, data

    ok, result = benchmark(delete_one)
    assert ok is True
    assert result == {"a": {"c": 2}}


@pytest.mark.benchmark(group="ddelete")
def test_ddelete_wildcard_bulk(benchmark):
    def delete_all():
        # Fresh 500-item structure each call, then delete every match in one wildcard
        # call - exercises the descending-index-sort-then-delete path at the same
        # scale as dget_list_wildcard_bracket/dset_build_new, not just a single delete.
        data = {"items": [{"id": i} for i in range(500)]}
        ok = ddelete(data, "items[*]")
        return ok, data

    ok, result = benchmark(delete_all)
    assert ok is True
    assert result == {"items": []}


@pytest.mark.benchmark(group="dwalk")
def test_dwalk_realistic(benchmark):
    result = benchmark(lambda: list(dwalk(REALISTIC_DOC)))
    assert len(result) > 0


@pytest.mark.benchmark(group="dwalk")
def test_dwalk_list_of_dicts(benchmark):
    result = benchmark(lambda: list(dwalk(LIST_OF_DICTS)))
    assert len(result) == 1500  # 500 items x (id, name, meta/active)


@pytest.mark.benchmark(group="flatten")
def test_flatten_nested(benchmark):
    result = benchmark(lambda: flatten(FLATTEN_NESTED))
    assert len(result) == 1000  # 50 x 20
