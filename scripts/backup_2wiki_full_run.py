#!/usr/bin/env python3
"""Archive and restore-verify the complete frozen 2Wiki run tree, without mutation.

This tool never claims remote/cloud restoration automatically: verification must
be performed on bytes separately retrieved from an independent destination.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

PINS = {
    "protocol.json": "40ed57afe9b923362a8c725d66f58d32fc2b8796ffe57696a481c34a4b8bfef4",
    "execution/construction/construction.seal.json": "e8ab16b7820f42c6bf62fa69d68ba9d2a56bd4924ae11027f60ca689640cdd44",
    "execution/evaluation/evaluation.complete.json": "db8c09aa8712a16a255298dc6afde83fe1bd3079b846f8cbee2244b946842519",
    "execution/aggregate.json": "721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96",
}

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()

def require_pins(run):
    for rel, expected in PINS.items():
        path = run / rel
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise ValueError("Frozen file missing/modified: " + rel)

def inventory(run):
    records = []
    for directory, dirs, files in os.walk(run, followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs:
            d = Path(directory) / name
            if d.is_symlink():
                raise ValueError("Symlink directory is forbidden: " + str(d))
        for name in files:
            f = Path(directory) / name
            mode = f.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise ValueError("Only regular files may be archived: " + str(f))
            records.append({
                "path": f.relative_to(run).as_posix(),
                "bytes": f.stat().st_size,
                "sha256": sha256(f),
            })
    if not records:
        raise ValueError("No files in run directory")
    return records

def manifest_bytes(manifest):
    return (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n").encode("utf-8")

def validate_archive(archive, expected, restore_to=None):
    expected_files = {x["path"]: x for x in expected["files"]}
    seen = set()
    recovered = None
    if restore_to is not None:
        recovered = Path(restore_to).expanduser().resolve()
        if recovered.exists():
            raise FileExistsError("Recovery destination must not exist: " + str(recovered))
        recovered.mkdir(parents=True)
    try:
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf:
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError("Archive contains non-regular member: " + member.name)
                reader = tf.extractfile(member)
                if reader is None:
                    raise ValueError("Unreadable archive member: " + member.name)
                if member.name == "BACKUP_MANIFEST.json":
                    if reader.read() != manifest_bytes(expected):
                        raise ValueError("Embedded backup manifest mismatch")
                    seen.add(member.name)
                    continue
                if not member.name.startswith("run/"):
                    raise ValueError("Unexpected archive member: " + member.name)
                rel = member.name[len("run/"):]
                if rel not in expected_files or rel in seen:
                    raise ValueError("Unexpected/duplicate archived file: " + rel)
                seen.add(rel)
                digest = hashlib.sha256()
                size = 0
                writer = None
                if recovered:
                    dest = recovered / rel
                    if not dest.resolve().is_relative_to(recovered):
                        raise ValueError("Unsafe recovery member: " + rel)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    writer = dest.open("xb")
                try:
                    while True:
                        piece = reader.read(1024 * 1024)
                        if not piece:
                            break
                        digest.update(piece)
                        size += len(piece)
                        if writer:
                            writer.write(piece)
                finally:
                    if writer:
                        writer.close()
                if size != expected_files[rel]["bytes"] or digest.hexdigest() != expected_files[rel]["sha256"]:
                    raise ValueError("Archived-file hash or size mismatch: " + rel)
        if seen != set(expected_files) | {"BACKUP_MANIFEST.json"}:
            raise ValueError("Archive omitted one or more run files")
        return len(expected_files)
    except Exception:
        if recovered:
            print("INCOMPLETE verification: quarantine partial restore at", recovered)
        raise

def create(run, archive):
    run = Path(run).expanduser().resolve(strict=True)
    archive = Path(archive).expanduser().absolute()
    if archive == run or run in archive.parents:
        raise ValueError("Archive must be outside the frozen run directory")
    if archive.exists():
        raise FileExistsError("Archive already exists; will not overwrite")
    archive.parent.mkdir(parents=True, exist_ok=True)
    sidecar = Path(str(archive) + ".manifest.json")
    receipt = Path(str(archive) + ".sha256.txt")
    if sidecar.exists() or receipt.exists():
        raise FileExistsError("Backup sidecar already exists; no overwrite")
    require_pins(run)
    files = inventory(run)
    manifest = {
        "schema": "rag-poison-transfer.2wiki-complete-run-backup/v1",
        "scope": "entire authorized-matrix directory; external model/dataset caches excluded",
        "frozen_pins": PINS,
        "file_count": len(files),
        "total_bytes": sum(x["bytes"] for x in files),
        "files": files,
    }
    temp = Path(str(archive) + ".incomplete")
    if temp.exists():
        raise FileExistsError("Incomplete archive already exists; investigate it")
    try:
        with tarfile.open(temp, "w:gz", dereference=True) as tf:
            body = manifest_bytes(manifest)
            info = tarfile.TarInfo("BACKUP_MANIFEST.json")
            info.size = len(body)
            info.mode = 0o600
            tf.addfile(info, io.BytesIO(body))
            for item in files:
                tf.add(run / item["path"], arcname="run/" + item["path"], recursive=False)
        validated = validate_archive(temp, manifest)
        require_pins(run)
        if validated != len(files):
            raise ValueError("Archive inventory count mismatch")
        os.replace(temp, archive)
        sidecar.write_bytes(manifest_bytes(manifest))
        receipt.write_text(
            sha256(archive) + "  " + archive.name + "\n"
            + sha256(sidecar) + "  " + sidecar.name + "\n"
        )
    except Exception:
        print("FAIL: source is untouched. Inspect incomplete archive if present.")
        raise
    print("PASS: local full-run archive is internally restorable (not yet off-device verified)")
    print("Files:", len(files), "Source bytes:", manifest["total_bytes"])
    print("Archive:", archive)
    print("Archive SHA-256:", sha256(archive))
    print("Manifest:", sidecar)
    print("Pin the archive SHA separately; download archive + manifest from remote storage for independent restore.")

def verify(archive, manifest_file, expected_digest, restore_to):
    archive = Path(archive).expanduser().resolve(strict=True)
    manifest_file = Path(manifest_file).expanduser().resolve(strict=True)
    if sha256(archive) != expected_digest:
        raise ValueError("Separately recorded archive SHA-256 mismatch")
    manifest = json.loads(manifest_file.read_text())
    if manifest.get("frozen_pins") != PINS or manifest.get("schema") != "rag-poison-transfer.2wiki-complete-run-backup/v1":
        raise ValueError("Wrong backup manifest/pins")
    if len(manifest.get("files", [])) != manifest.get("file_count"):
        raise ValueError("Manifest file count mismatch")
    result = validate_archive(archive, manifest, restore_to)
    print("PASS: separately supplied archive matches pinned hash, embedded manifest and", result, "restored file hashes")
    print("Restored to:", restore_to)
    print("Remote independence must be confirmed by operator (e.g. actual web download to different location/device).")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    c = s.add_parser("create")
    c.add_argument("--run", required=True)
    c.add_argument("--archive", required=True)
    v = s.add_parser("verify")
    v.add_argument("--archive", required=True)
    v.add_argument("--manifest", required=True)
    v.add_argument("--expected-archive-sha256", required=True)
    v.add_argument("--restore-to", required=True)
    a = p.parse_args()
    if a.command == "create":
        create(a.run, a.archive)
    else:
        verify(a.archive, a.manifest, a.expected_archive_sha256, a.restore_to)

if __name__ == "__main__":
    main()
