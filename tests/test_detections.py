import json
import os
import pathlib
import pytest
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from detections import load_detections

SCHEMAS = {p.stem: json.loads(p.read_text()) for p in pathlib.Path("schemas").glob("*.json")}
CLIENT = KustoClient(KustoConnectionStringBuilder.with_no_authentication(
    os.environ.get("KUSTO_URL", "http://localhost:8080")))


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


CASES = [(d, kind) for d in load_detections() for kind in ("positive", "negative")]


@pytest.mark.parametrize("det,kind", CASES, ids=[f"{d['title']}::{k}" for d, k in CASES])
def test_detection(det, kind):
    fixture = pathlib.Path("tests/fixtures") / det["id"] / f"{kind}.json"
    assert fixture.exists(), f"missing fixture: {fixture}"
    tables = json.loads(fixture.read_text())
    query = "".join(as_datatable(t, rows) for t, rows in tables.items()) + det["query"]
    rows = CLIENT.execute("NetDefaultDB", query).primary_results[0].rows
    if kind == "positive":
        assert len(rows) > 0, f"{det['title']} did not fire on positive fixture"
    else:
        assert len(rows) == 0, f"{det['title']} fired on negative fixture: {rows}"