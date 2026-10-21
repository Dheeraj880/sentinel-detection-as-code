import pathlib
import yaml
from sigma.collection import SigmaCollection
from sigma.backends.kusto import KustoBackend
from sigma.pipelines.microsoftxdr import microsoft_xdr_pipeline


def load_detections():
    """Return every detection as {id, title, tags, query, source}."""
    out = []
    for p in sorted(pathlib.Path("rules/sigma").rglob("*.yml")):
        text = p.read_text()
        meta = yaml.safe_load(text)
        backend = KustoBackend(processing_pipeline=microsoft_xdr_pipeline())
        kql = backend.convert(SigmaCollection.from_yaml(text))[0]
        out.append({"id": meta["id"], "title": meta["title"],
                    "tags": meta.get("tags", []), "query": kql, "source": str(p)})
    for p in sorted(pathlib.Path("rules/kql").rglob("*.yml")):
        meta = yaml.safe_load(p.read_text())
        out.append({"id": meta["id"], "title": meta["title"],
                    "tags": meta.get("tags", []), "query": meta["query"], "source": str(p)})
    return out


if __name__ == "__main__":
    build = pathlib.Path("build")
    build.mkdir(exist_ok=True)
    for d in load_detections():
        (build / f"{d['id']}.kql").write_text(f"// {d['title']}\n{d['query']}\n")
        print("OK ", d["title"])