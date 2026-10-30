"""Start the MedAgentBench HAPI FHIR server locally (no Docker) and wait until it is ready.

Replicates the launch command of the official task image:
  java --class-path main.war -Dloader.path=main.war!/WEB-INF/classes/,main.war!/WEB-INF/
       org.springframework.boot.loader.PropertiesLauncher
with SPRING_CONFIG_LOCATION pointing at the image's application.yaml. The only change is
the H2 datasource path, overridden on the command line because the image hard-codes the
Linux path /data/test_db.
"""
import os, shutil, subprocess, sys, time, urllib.request

# Never route requests to the local FHIR server through an outbound HTTP proxy.
for _k in ("NO_PROXY", "no_proxy"):
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k, ""), "localhost", "127.0.0.1") if x)

HERE = os.path.dirname(os.path.abspath(__file__))


def java_exe():
    # On Windows, call the real JDK launcher (Library/lib/jvm/bin/java.exe), not the Library/bin shim:
    # Library/bin also holds copies of Windows api-ms-win-*.dll runtime files, and loading those
    # fails with WinError 623 (illegal system DLL relocation) inside restricted sandboxes.
    roots = [env_root()]
    for root in roots:
        for cand in (os.path.join(root, "Library", "lib", "jvm", "bin", "java.exe"),
                     os.path.join(root, "lib", "jvm", "bin", "java"),
                     os.path.join(root, "bin", "java")):
            if os.path.exists(cand):
                return cand
    raise RuntimeError("Java 17 not found; create the env with openjdk=17")


def env_root():
    """Root of the conda env that provides Java (derived from the java shim on PATH, else CONDA_PREFIX)."""
    shim = shutil.which("java")
    if shim:
        d = os.path.dirname(os.path.abspath(shim))              # .../Library/bin  or .../bin
        if os.path.basename(os.path.dirname(d)).lower() == "library":
            return os.path.dirname(os.path.dirname(d))           # Windows conda layout
        return os.path.dirname(d)
    return os.environ.get("CONDA_PREFIX", sys.prefix)


def _clean_path():
    """PATH without any folder of the Java conda env (root and Library/* carry runtime DLL copies; see java_exe)."""
    bad = os.path.normcase(env_root())
    return os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                           if not os.path.normcase(p).startswith(bad))


def is_ready(port=8080, timeout=60):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/fhir/metadata", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def build_h2fix(server_dir):
    """Compile the rwdisk H2 file-system provider into <server_dir>/extra-classes (once)."""
    out = os.path.join(server_dir, "extra-classes")
    marker = os.path.join(out, "mab", "RwDiskFilePath.class")
    if os.path.exists(marker):
        return out
    import glob, zipfile
    src = os.path.join(HERE, "h2fix", "src")
    lib = os.path.join(HERE, "h2fix", "lib")
    os.makedirs(lib, exist_ok=True)
    # Compile against the war's own jars.
    with zipfile.ZipFile(os.path.join(server_dir, "app", "main.war")) as w:
        for n in w.namelist():
            base = os.path.basename(n)
            if n.startswith("WEB-INF/lib/") and (base.startswith(("h2-", "spring-core-")) or
                                                 (base.startswith("spring-boot-3") and base.count("-") == 2)):
                dest = os.path.join(lib, base)
                if not os.path.exists(dest):
                    with open(dest, "wb") as fh:
                        fh.write(w.read(n))
    javac = os.path.join(os.path.dirname(java_exe()), "javac.exe" if os.name == "nt" else "javac")
    cp = os.pathsep.join(glob.glob(os.path.join(lib, "*.jar")))
    proc = subprocess.run([javac, "--release", "17", "-cp", cp, "-d", out] +
                          glob.glob(os.path.join(src, "mab", "*.java")),
                          capture_output=True, text=True, env=dict(os.environ, PATH=_clean_path()))
    # Inside restricted Windows sandboxes javac writes its classes and then crashes while closing the jars
    # ("Cannot close compiler resources": Path.toRealPath is denied), so judge success by the outputs.
    needed = [os.path.join(out, "mab", c) for c in ("RwDiskFilePath.class", "RegisterRwDisk.class")]
    if " error" in proc.stdout + proc.stderr and "Cannot close compiler resources" not in proc.stdout + proc.stderr \
            or not all(os.path.exists(p) for p in needed):
        raise RuntimeError("javac failed:\n" + (proc.stdout + proc.stderr)[-2000:])
    os.makedirs(os.path.join(out, "META-INF"), exist_ok=True)
    shutil.copy(os.path.join(src, "META-INF", "spring.factories"), os.path.join(out, "META-INF", "spring.factories"))
    return out


def start(server_dir="mab_server", port=8080, heap="-Xms1g -Xmx4g", wait_s=900, log="mab_server/fhir.log"):
    if is_ready(port):
        return {"status": "already running", "port": port}
    server_dir = os.path.abspath(server_dir)
    app_dir = os.path.join(server_dir, "app")
    db = os.path.join(server_dir, "data", "test_db").replace("\\", "/")
    cfg = os.path.join(server_dir, "configs", "application.yaml").replace("\\", "/")
    for f in (os.path.join(app_dir, "main.war"), db + ".mv.db", cfg):
        if not os.path.exists(f):
            raise FileNotFoundError(f"{f} missing; run fetch_server.py first")
    extra = build_h2fix(server_dir).replace("\\", "/")
    env = dict(os.environ, PATH=_clean_path(),
               SPRING_CONFIG_LOCATION=f"file:///{cfg.lstrip('/')}",
               JAVA_TOOL_OPTIONS=f"{heap} -Djava.security.egd=file:/dev/./urandom")
    cmd = [java_exe(), "--class-path", "main.war",
           f"-Dloader.path=main.war!/WEB-INF/classes/,main.war!/WEB-INF/,{extra}",
           "org.springframework.boot.loader.PropertiesLauncher",
           f"--spring.datasource.url=jdbc:h2:rwdisk:{db};DB_CLOSE_DELAY=-1",
           f"--server.port={port}"]
    logf = open(os.path.abspath(log), "ab")
    proc = subprocess.Popen(cmd, cwd=app_dir, env=env, stdout=logf, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if proc.poll() is not None:
            raise RuntimeError(f"FHIR server exited with code {proc.returncode}; see {log}")
        if is_ready(port):
            return {"status": "started", "pid": proc.pid, "port": port, "startup_s": round(time.time() - t0)}
        time.sleep(5)
    raise TimeoutError(f"FHIR server not ready after {wait_s}s; see {log}")


if __name__ == "__main__":
    print(start())
    print("Server running; leave this process alive while agents run.")
    while True:
        time.sleep(3600)
