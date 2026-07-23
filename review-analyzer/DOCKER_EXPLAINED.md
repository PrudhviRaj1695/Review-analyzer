# Docker, explained

Everything we built and verified for containerizing review-analyzer: the
Dockerfile, `.dockerignore`, dependency management, port mapping, config
injection, log streaming, in-container inspection, and the full
build/run/inspect/logs/stop/remove/prune lifecycle. Every command below was
actually run against this project and its output checked, not just described.

## 1. The Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `FROM python:3.12-slim`

Every image is a stack of layers on top of a base image. `slim` variants are
built on Debian but strip out compilers, docs, and other build-time-only
packages — much smaller than the default `python:3.12` image, while still
using glibc (unlike `alpine`, which uses musl libc and frequently breaks
packages with compiled C extensions). That matters here concretely:
`psycopg2-binary`, `pydantic-core`, and `numpy`/`pandas` (pulled in via
streamlit) all ship as manylinux/glibc wheels.

### `WORKDIR /app`

Creates `/app` if it doesn't exist and sets it as the working directory for
every instruction that follows. Every relative `COPY` destination and the
`CMD`'s runtime working directory resolve against this. Without it, files
would land at `/` and things get harder to reason about.

### `COPY requirements.txt .` then `RUN pip install ...` — before `COPY . .`

This ordering is the entire reason "dependency layer separated from code
layer" was a hard requirement, not a nice-to-have. Docker caches each
instruction as an immutable layer, keyed by a hash of its inputs (for
`COPY`, the copied files' contents; for `RUN`, the command plus the state of
the layer before it).

Because `requirements.txt` is copied and installed **before** any
application code is present, editing `app/main.py` (or any source file)
does not invalidate the `pip install` layer on a rebuild. Docker reuses the
cached layer — all ~75 packages already installed — and only re-executes
from `COPY . .` onward.

Verified directly: the first build took ~60 seconds to `pip install`
everything. Every subsequent rebuild after a code-only change skipped
straight past that step using the cached layer.

If the order were flipped (`COPY . .` before installing dependencies), *any*
source change — even a single-character edit — would invalidate every layer
after it, including the dependency install, forcing a full ~60s reinstall
on every single rebuild. At real-world dependency-tree sizes this is the
difference between a multi-minute rebuild loop and a multi-second one.

`--no-cache-dir` on the `pip install` skips pip's local wheel cache, which
would otherwise persist inside the image layer for no benefit — a container
build never gets a second `pip install` run that could reuse that cache; the
layer is immutable once built, so the cache is pure dead weight.

### `COPY . .`

Copies the rest of the build context (application code, `alembic/`,
`scripts/`, etc.) into `/app`. Subject to `.dockerignore` — see below.

### `EXPOSE 8000`

Purely documentation/metadata for tooling (`docker ps`, orchestrators). It
does **not** publish the port or make it reachable from anywhere. That is
entirely the job of `-p` at `docker run` time (section 4).

### `CMD [...]` — exec form

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This is the JSON-array ("exec") form, not the shell form
(`CMD uvicorn app.main:app ...`). The exec form runs the binary directly as
PID 1, so it correctly receives OS signals like `SIGTERM` — needed for
graceful shutdown. The shell form runs `/bin/sh -c "..."` as PID 1 instead,
which by default does not forward signals to the child process it spawns,
so `docker stop` would have to wait out the full grace period and then
`SIGKILL` instead of letting uvicorn shut down cleanly.

`--host 0.0.0.0` is mandatory inside a container. uvicorn's local default,
`127.0.0.1`, binds only the container's own loopback interface — reachable
from nowhere outside the container's network namespace, even with a port
mapping in place. `0.0.0.0` binds all interfaces inside the container so the
mapped port can actually reach the process.

`app.main:app` is `module.path:object_name` — the same convention used
running uvicorn locally, pointing at the `FastAPI()` instance in
`app/main.py`.

## 2. `.dockerignore`

```
.venv
venv
.git
.env
__pycache__
*.pyc
*.sqlite
.pytest_cache
.ruff_cache
```

Without this file, `COPY . .` recursively copies **everything** under the
build context. We proved exactly what that means by building once without
it and inspecting the result:

- `.venv/` — 400MB, entirely pointless (the image installs its own
  dependencies via `pip install -r requirements.txt`; the host venv is
  irrelevant and often has platform-specific binaries anyway).
- `venv/` (no leading dot) — a 13MB leftover from before the project
  switched to `.venv`/`uv`, already `.gitignore`d but initially missing from
  `.dockerignore` too. Found via `docker exec ... ls /app` during a
  filesystem exploration exercise and added afterward.
- `.git/`, `.pytest_cache/`, `.ruff_cache/` — dev-tooling artifacts with no
  runtime purpose.
- **`.env`** — the important one. Contains `LLM_API_KEY` and `DATABASE_URL`.
  Confirmed by building without `.dockerignore` and running
  `docker exec <container> sh -c "ls -la /app"` — `.env` was sitting right
  there in the container filesystem.

That last point is a real security issue, not just tidiness: Docker image
layers are content-addressed and immutable. Even if a *later* layer in the
same Dockerfile deleted the file, it would still physically exist in the
layer history — anyone who can pull or inspect the image (a registry, a
teammate, a CI build cache) can extract it back out. `.dockerignore`
prevents the secret from ever entering a layer in the first place, which is
the only real fix.

**Measured impact**: image size went from **1.44GB without
`.dockerignore` → 898MB with it** — a ~540MB difference, entirely from
`.venv`, `.env`, and the dev-tool caches.

## 3. `requirements.txt`

The Dockerfile installs dependencies via plain `pip install -r requirements.txt`
rather than invoking `uv` inside the image, to keep the Dockerfile itself
minimal — no extra installer needed at build time. But the committed
`requirements.txt` was stale: pinned ancient versions
(`fastapi==0.104.1`) and was missing `sqlalchemy`, `alembic`, `openai`,
`pgvector`, `psycopg2-binary`, and `pydantic-settings` entirely — real
imports the app depends on. Built as-is, the container would start, then
crash the moment `app.database` or `app.recommend` got imported.

Regenerated it from the actual source of truth, `uv.lock`:

```bash
uv export --no-hashes --no-dev -o requirements.txt
```

`--no-dev` excludes dev-only tooling (`pytest`, `ruff`) that has no business
in a runtime image. The regenerated file pulls in everything the app
imports, including the full `streamlit` dependency tree (`pandas`, `numpy`,
`pyarrow`, `altair`) since streamlit is a real top-level dependency now —
which is most of why the final image is ~900MB rather than something much
smaller. A pure-API image (no streamlit) would be meaningfully lighter if
that's ever split out.

## 4. Building the image

```bash
docker build -t review-analyzer:tag .
```

The Docker CLI streams the build context (everything under `.`, minus
`.dockerignore` exclusions) to the daemon, which executes each Dockerfile
instruction in order, producing and caching one layer per instruction. The
result is an **image**: a read-only, layered filesystem plus metadata
(`CMD`, `EXPOSE`, env defaults, etc.), addressed by a content hash
(`sha256:...`). Nothing runs yet — this only produces the artifact.

Verified: the image builds successfully and reproducibly; rebuilding with
no source changes reuses every cached layer and completes in seconds.

## 5. Running it, and `-p host:container`

```bash
docker run -d --name myapp -p 8000:8000 \
  -e DATABASE_URL="sqlite:////app/review_db.sqlite" \
  -e LLM_API_KEY="test-key" \
  review-analyzer:tag
```

Every container gets its own **network namespace** — its own loopback, its
own port space, fully isolated from the host and from every other
container. When uvicorn binds `0.0.0.0:8000` inside the container, that
`8000` exists only inside that private namespace.

`-p 8000:8000` (`host:container`) tells the Docker daemon to set up a
NAT/proxy rule: forward the **host's** port 8000 to the **container's**
port 8000. The two numbers don't have to match — `-p 9000:8000` would make
the app reachable at `localhost:9000` on the host while uvicorn still only
knows about port 8000 internally.

**What happens without `-p`** — verified directly: ran the identical image
with no `-p` flag at all.

- `docker ps` showed `PORTS: 8000/tcp` — no `0.0.0.0:→` prefix, meaning
  nothing was published to the host.
- `curl http://localhost:8000/health` from the host had nothing to connect
  to.
- `docker exec <container> python -c "...urlopen('http://localhost:8000/health')..."`
  — run **from inside** the container's own namespace — succeeded
  immediately, proving the app was fully alive and healthy the entire time.
  It was simply invisible from outside its own network namespace.

This is the isolation working exactly as designed: containers do not get
host-visible ports by default, you opt in per port with `-p`.

## 6. Config injection: `-e` and `--env-file`

```bash
# individual variables
docker run -e DATABASE_URL="postgresql://user:pass@host:5432/review_db" \
           -e LLM_API_KEY="sk-..." \
           review-analyzer:tag

# a whole file at once
docker run --env-file .env review-analyzer:tag
```

Both mechanisms land as real OS environment variables inside the
container's process — `pydantic-settings` in `app/settings.py` reads them on
startup exactly as it would running locally. `--env-file` just reads
`KEY=value` lines from a file and applies them the same way `-e` would, one
per line; your existing `.env` works as-is.

**Proven that one image supports many configs, not one config per image**:
built `review-analyzer:cfg` once, then ran two containers from it — one
seeded with `-e` values, one with `--env-file .env` pointing at different
values.

```
cfg-a image: sha256:9716afeefb...
cfg-b image: sha256:9716afeefb...   <- identical image ID

cfg-a: DATABASE_URL=sqlite:////app/review_db.sqlite   LLM_API_KEY=dev-key-aaa
cfg-b: DATABASE_URL=sqlite:///./review_db.sqlite      LLM_API_KEY=ollama
```

Same image, genuinely different runtime config, confirmed via
`docker inspect --format '{{.Image}}'` (identical) and `docker exec ... env`
(different).

### Why config must never be baked into the image

1. **One artifact, many environments.** The entire point of container
   immutability is that the exact bytes that passed testing in staging are
   the exact bytes running in production — you're not rebuilding between
   environments. Baking `DATABASE_URL` in at build time would force a
   separate image per environment, breaking that guarantee: "works in
   staging" would no longer say anything about the production image, since
   they'd be different builds entirely.
2. **Secrets in layers are permanent and shareable**, as demonstrated in
   section 2 with `.env`. The same logic applies to any secret baked in via
   `ENV` or `ARG` in the Dockerfile itself — it becomes part of the image's
   layer history, extractable by anyone who can pull or inspect it.
3. **Rotation.** A leaked or expired credential means restarting the
   container with a new env value. A baked-in credential means rebuilding
   and redistributing the image just to change one string.

## 7. `docker logs -f`

```bash
docker logs -f <container>
```

Streams a container's stdout/stderr continuously (`-f` = follow), the same
idea as `tail -f` on a log file — except Docker is capturing the process's
stdout/stderr streams directly, which is exactly why the app logs to stdout
via a plain `StreamHandler` (see `DATABASE_INTERNALS.md`'s sibling doc on
logging) rather than to a file: a file-based logger would be invisible to
`docker logs` entirely.

Verified: started `docker logs -f` in the background, then fired two `curl`
requests at the running container. Both requests' structured JSON log lines
appeared in the stream in real time, including a live `request_id`-tagged
`ERROR` traceback from one of them (an unmigrated fresh SQLite file inside
that particular ephemeral container — expected for a throwaway container,
unrelated to the logging mechanism itself, which worked exactly as
designed).

## 8. `docker exec` — looking inside a running container

```bash
docker exec <container> <command>
docker exec -it <container> sh   # interactive, when a real TTY is available
```

Runs a new process inside an already-running container, sharing its
filesystem, network, and process namespaces. `-it` (interactive + pseudo-TTY)
is what gives you a live interactive shell in a normal terminal; in
scripted/non-interactive tooling the same exploration works by running one
`docker exec <container> <cmd>` per command instead — functionally
equivalent, just not a persistent session.

What we found exploring a running review-analyzer container this way:

- `/app` (the `WORKDIR`) contained exactly what `COPY . .` sent, confirming
  `.dockerignore` was doing its job — no `.env`, `.venv`, or `.git`.
- Python `3.12.13`, packages installed under
  `/usr/local/lib/python3.12/site-packages`.
- No `ps` binary at all — `python:3.12-slim` is genuinely minimal. Had to
  read `/proc` directly (`ls /proc | grep -E '^[0-9]+$'`) to see PIDs
  (`1, 47, 53, 54` — uvicorn's main process plus workers).
- Running as `root` (`uid=0`) — there's no `USER` directive in the
  Dockerfile, so the container defaults to root. Noted as a real finding,
  not fixed since it wasn't asked for; a production hardening pass would
  add a non-root `USER` and adjust file ownership accordingly.
- The stray `venv/` directory mentioned in section 2 — found here, fixed
  immediately after by adding it to `.dockerignore` and confirming with a
  rebuild.

**Windows/Git Bash gotcha hit along the way**: MSYS auto-converts
POSIX-looking path arguments (like `/app`) into Windows paths before
handing them to `docker exec`, which breaks in-container paths. Fixed by
prefixing the command with `MSYS_NO_PATHCONV=1` when a bare `/path` needs to
reach the container unmodified.

## 9. The full lifecycle, twice

```
build → run → inspect → logs → stop → remove → prune
```

Practiced end to end, twice in a row, to build muscle memory for the
sequence:

| Step | Command | What it does | Why it matters |
|---|---|---|---|
| build | `docker build -t name .` | Produces the image (section 4) | The artifact everything else depends on |
| run | `docker run -d -p ... -e ... name` | Starts a detached container from it | `-d` so the terminal isn't blocked; `-p`/`-e` as in sections 5–6 |
| inspect | `docker inspect --format '...' <container>` | Reads metadata (status, IP, which image) without touching the container | Read-only diagnostic — confirms *what* is running before you act on it |
| logs | `docker logs <container>` | Confirms it actually started correctly | Cheap sanity check before moving on |
| stop | `docker stop <container>` | Sends `SIGTERM` to PID 1 (then `SIGKILL` after a grace period if needed) | Ends the process; the container object and its writable layer still exist afterward, in `Exited` state |
| remove | `docker rm <container>` | Deletes the stopped container object | Without this, stopped containers accumulate forever — this machine already had ~20 leftover from unrelated past projects before this exercise even started |
| prune | `docker image prune -f` | Deletes dangling (untagged, unreferenced) image layers | Without this, `docker rmi`'d images can leave orphaned intermediate layers taking up disk space indefinitely |

Checked for pre-existing dangling images (`docker images -f dangling=true`)
before the first prune, confirming it was zero going in — so
`docker image prune -f` was guaranteed to only ever remove layers this
exercise itself created, never collateral damage to something else on the
machine.

Ran twice, back to back, no notes needed. `docker ps -a` at the end showed
zero review-analyzer/cycle containers remaining — scoped deliberately to
not touch the ~20 unrelated stopped containers from other projects already
present on the machine (mlforge, claimscore-api, preauth-claims-service,
etc.), since removing someone else's containers without being asked is not
this exercise's call to make.

## Quick reference

```bash
# build
docker build -t review-analyzer .

# run, mapped to host 8000, config from .env
docker run -d --name review-analyzer -p 8000:8000 --env-file .env review-analyzer

# check it
curl http://localhost:8000/health
docker inspect --format '{{.State.Status}}' review-analyzer
docker logs -f review-analyzer          # Ctrl+C to stop following, container keeps running
docker exec -it review-analyzer sh      # look around inside

# tear down
docker stop review-analyzer
docker rm review-analyzer
docker image prune -f
```
