"""Stage a verified Swiss OICP feed and its same-generation operator outputs."""
import argparse
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.swiss_national_input import URL, validate
from v9_rebuild import swiss_bundle
from v9_rebuild.orchestrator import artifact_digest

METHODS = {
    "CH:chevp_evpass": "chevp-evpass-official-direct-tariffs.json",
    "CH:autosense_amag": "autosense-amag-direct-tariffs.json",
    "CH:partino_restricted": "par-partino-restricted-direct-classification.json",
    "CH:saascharge_official": "saascharge-official-direct-tariffs.json",
}


def prepare(national_file, national_receipt, receipts, artifacts, output):
    national = json.loads(national_receipt.read_bytes())
    raw = national_file.read_bytes()
    if (national["source"] != URL or national["sha256"] != hashlib.sha256(raw).hexdigest()
            or national["bytes"] != len(raw) or not national.get("retrievedAt")):
        raise ValueError("Swiss national receipt differs from input")
    validate(raw)
    output = output.resolve()
    if output.exists() or output == swiss_bundle.ROOT or swiss_bundle.ROOT in output.parents:
        raise ValueError("Fresh isolated destination required")
    pins = {}
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        stage = Path(folder) / "input"
        swiss_bundle.prepare_archived_inputs(stage)
        manifest = json.loads((stage / "input-manifest.json").read_bytes())
        (stage / swiss_bundle.NATIONAL).write_bytes(gzip.compress(raw, mtime=0))
        manifest["files"][str(swiss_bundle.NATIONAL)] = swiss_bundle.sha(stage / swiss_bundle.NATIONAL)
        for receipt_file in receipts:
            receipt = json.loads(receipt_file.read_bytes())
            source = receipt["sourceId"]
            if source not in METHODS or source in pins or receipt.get("technicalValidation") != "PASS":
                raise ValueError("Unexpected Swiss source receipt")
            if str(receipt["runId"]) == str(national["runId"]):
                if not any(item["source"] == source and item.get("verified") and item["artifact"] == receipt["artifactId"]
                           and item["fileSetSha"] == receipt["artifactSetSha256"] for item in national["derivedJobs"]):
                    raise ValueError("Missing national acquisition job linkage")
            elif (receipt.get("parentInputSha256") != national["sha256"]
                  or str(receipt.get("parentAcquisitionRun")) != str(national["runId"])
                  or receipt.get("parentArtifact") != national["artifactId"]):
                raise ValueError("Operator replay belongs to a different national acquisition")
            slug = source.replace(":", "_")
            state = artifacts / slug / "extracted" / "objects" / slug / receipt["artifactSetSha256"]
            digest, files = artifact_digest(state)
            if digest != receipt["artifactSetSha256"] or files != receipt["files"]:
                raise ValueError("Swiss operator artifact file set differs")
            name = "data/switzerland/" + METHODS[source]
            data = (state / name).read_bytes()
            dest = stage / name
            dest.write_bytes(data)
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            pins[source] = {"runId": receipt["runId"], "artifactId": receipt["artifactId"], "fileSetSHA256": digest}
        if set(pins) != set(METHODS):
            raise ValueError("Swiss renewal inputs incomplete")
        manifest.update(origin="pinned_national_with_operator_artifacts_and_preserved_archives",
                        nationalReceipt=national["sha256"], nationalRetrievedAt=national["retrievedAt"], operatorReceipts=pins)
        (stage / "input-manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
        swiss_bundle.verify_inputs(stage)
        stage.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--national-file", type=Path, required=True)
    parser.add_argument("--national-receipt", type=Path, required=True)
    parser.add_argument("--operator-receipt", type=Path, action="append", required=True)
    parser.add_argument("--artifacts", type=Path, required=True, help="Root of the verified per-source downloads")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.national_file, args.national_receipt, args.operator_receipt, args.artifacts, args.out)
