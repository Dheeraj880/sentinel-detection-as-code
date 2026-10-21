import json
import os
import pathlib
import pytest
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from detections import load_detections

SCHEMAS = {p.stem: json.loads(p.read_text()) for p in pathlib.Path("schemas").glob("*.json")}
CLIENT = KustoClient(KustoConnectionStringBuilder.with_no_authentication(
    os.environ.get("KUSTO_URL", "http://localhost:8080")))
FIXTURES = pathlib.Path("tests/fixtures")
DETECTIONS = load_detections()


def literal(value, kql_type):
    if kql_type == "string":
        return json.dumps(value if value is not None else "")
    if value is None:
        return f"{kql_type}(null)"
    if kql_type == "datetime":
        return f"datetime({value})"
    if kql_type == "dynamic":
        return f"dynamic({json.dumps(value)})"
    if kql_type == "bool":
        return "true" if value else "false"
    return str(value)


def as_datatable(table, rows):
    schema = SCHEMAS[table]
    cols = ", ".join(f"{c}:{t}" for c, t in schema.items())
    vals = ",\n".join(", ".join(literal(r.get(c), t) for c, t in schema.items()) for r in rows)
    return f"let {table} = datatable({cols}) [\n{vals}\n];\n"


def fixture_files(det):
    return sorted((FIXTURES / det["id"]).glob("*.json"))


@pytest.mark.parametrize("det", DETECTIONS, ids=[d["title"] for d in DETECTIONS])
def test_rule_has_positive_and_negative(det):
    names = [f.stem for f in fixture_files(det)]
    assert any(n.startswith("positive") for n in names), f"no positive fixture for {det['title']} ({det['id']})"
    assert any(n.startswith("negative") for n in names), f"no negative fixture for {det['title']} ({det['id']})"


CASES = [(d, f) for d in DETECTIONS for f in fixture_files(d)]


@pytest.mark.parametrize("det,fixture", CASES, ids=[f"{d['title']}::{f.stem}" for d, f in CASES])
def test_detection(det, fixture):
    tables = json.loads(fixture.read_text())
    query = "".join(as_datatable(t, rows) for t, rows in tables.items()) + det["query"]
    rows = CLIENT.execute("NetDefaultDB", query).primary_results[0].rows
    if fixture.stem.startswith("positive"):
        assert len(rows) > 0, f"{det['title']} did not fire on {fixture.name}"
    elif fixture.stem.startswith("negative"):
        assert len(rows) == 0, f"{det['title']} fired on {fixture.name}: {rows}"
    else:
        pytest.fail(f"fixture name must start with 'positive' or 'negative': {fixture}")