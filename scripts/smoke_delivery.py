"""Verify a local/public full-stack URL; --live-job additionally downloads real SPHEREx data."""

import argparse
import json
import time
import urllib.request


def check(base: str, *, live_job=False, timeout_s=240):
    base = base.rstrip("/")

    def read(path, body=None):
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    def doc(path, body=None):
        return json.loads(read(path, body))

    assert b"<html" in read("/").lower(), "Built frontend is missing"
    health = doc("/api/health")
    assert health["status"] == "ok" and health["synthetic"] is False
    assert health["job_engine"] == "running", "Coordinate jobs must be enabled"
    manifest = doc("/api/manifest")
    assert not manifest["synthetic"] and len(manifest["fields"]) >= 5
    counts = {}
    for item in manifest["fields"]:
        field = doc("/api/fields/" + item["id"])
        assert not field["provenance"]["synthetic"] and len(field["frames"]) >= 2
        assert all(f["source_uri"] and f["release"] != "synthetic" for f in field["frames"])
        assert read(f"/data/fields/{field['id']}/{field['frames'][0]['image']}").startswith(b"\x89PNG\r\n\x1a\n")
        if item["id"] in {"barnards-star", "eps-indi-b", "r-draconis", "rw-aurigae", "wise-0855"}:
            comparison = doc(f"/api/fields/{field['id']}/comparisons")
            assert comparison["images"] and not comparison["synthetic"]
            assert read("/data/" + comparison["images"][0]["image"]).startswith(b"\x89PNG\r\n\x1a\n")
        counts[field["id"]] = len(field["frames"])
    assert len(doc("/api/lightcurves")["products"]) >= 2
    result = {"base": base, "real_fields": counts, "job_engine": health["job_engine"]}
    if live_job:
        # Deliberately different from every preset; the server must build these coordinates.
        parameters = {"ra": 269.4465, "dec": 4.7689, "size_deg": 0.05, "detectors": [2], "max_frames": 8}
        job = doc("/api/jobs", parameters)
        until = time.monotonic() + timeout_s
        while job["status"] in {"queued", "running"} and time.monotonic() < until:
            time.sleep(1)
            job = doc("/api/jobs/" + job["id"])
        assert job["status"] == "ready", f"Coordinate job did not finish: {job}"
        field = doc("/api/fields/" + job["result_field_id"])
        assert (field["center"]["ra"], field["center"]["dec"]) == (parameters["ra"], parameters["dec"])
        assert not field["provenance"]["synthetic"] and len(field["frames"]) >= 2
        assert read(f"/data/fields/{field['id']}/{field['frames'][0]['image']}").startswith(b"\x89PNG\r\n\x1a\n")
        result["live_job"] = {"id": job["id"], "field_id": field["id"], "frames": len(field["frames"])}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Local or public origin, e.g. http://localhost:8000")
    parser.add_argument("--live-job", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.base, live_job=args.live_job), indent=2))
