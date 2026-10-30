"""Fetch the MedAgentBench FHIR server files from Docker Hub without Docker.

Pulls only three files from the pinned image used by the official task environments:
  /app/main.war                (HAPI FHIR JPA server)
  /configs/application.yaml    (Spring config)
  /data/test_db.mv.db          (pre-loaded H2 database of synthetic patients)
Layers are streamed and scanned newest-first, so later layers override earlier ones
exactly as in a Docker build. Nothing is written except the three target files.

Usage:  python fetch_server.py [target_dir]     (default: ./mab_server)
"""
import json, os, sys, tarfile, time, urllib.request

REPO = "jyxsu6/medagentbench"
DIGEST = "sha256:3fb83d7ed71c5476f9eb6212bd440a909ef7505922bbc757dc488a8fc0701966"
TARGETS = {"app/main.war", "configs/application.yaml", "data/test_db.mv.db"}
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def _token():
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{REPO}:pull"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["token"]


def _open(path, token, accept=ACCEPT, timeout=120):
    req = urllib.request.Request(
        f"https://registry-1.docker.io/v2/{REPO}/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": accept},
    )
    return urllib.request.urlopen(req, timeout=timeout)


def manifest(token):
    with _open(f"manifests/{DIGEST}", token) as r:
        m = json.loads(r.read())
    if "manifests" in m:  # multi-arch index -> pick linux/amd64
        amd = [x for x in m["manifests"] if x.get("platform", {}).get("architecture") == "amd64"][0]
        with _open(f"manifests/{amd['digest']}", token) as r:
            m = json.loads(r.read())
    return m


def fetch(target_dir="mab_server"):
    token = _token()
    layers = manifest(token)["layers"]
    remaining = set(TARGETS)
    for idx in range(len(layers) - 1, -1, -1):
        if not remaining:
            break
        layer = layers[idx]
        t0 = time.time()
        token = _token()  # tokens can expire during long downloads
        with _open(f"blobs/{layer['digest']}", token, accept="*/*", timeout=600) as resp:
            with tarfile.open(fileobj=resp, mode="r|gz") as tf:
                for member in tf:
                    name = member.name.lstrip("./")
                    if name in remaining and member.isfile():
                        out = os.path.join(target_dir, *name.split("/"))
                        os.makedirs(os.path.dirname(out), exist_ok=True)
                        src = tf.extractfile(member)
                        with open(out, "wb") as fh:
                            while True:
                                chunk = src.read(8 << 20)
                                if not chunk:
                                    break
                                fh.write(chunk)
                        remaining.discard(name)
                        print(f"  layer {idx}: extracted {name} ({member.size/1e6:.1f} MB)", flush=True)
        print(f"layer {idx} scanned ({layer['size']/1e6:.1f} MB compressed, {time.time()-t0:.0f}s); "
              f"remaining: {sorted(remaining)}", flush=True)
    if remaining:
        raise RuntimeError(f"Not found in image: {sorted(remaining)}")
    return {t: os.path.getsize(os.path.join(target_dir, *t.split("/"))) for t in TARGETS}


if __name__ == "__main__":
    print(json.dumps(fetch(sys.argv[1] if len(sys.argv) > 1 else "mab_server"), indent=1))
