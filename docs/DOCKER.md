# Docker workbench

Docker Desktop (macOS/Windows) or Docker Engine with Compose 2.20+ runs the local workbench. The root `compose.yaml` and the existing `backend/docker/docker-compose.yml` use the same project and named volumes. Run commands below from the repository root.

```bash
docker compose up --build -d --wait
```

Open http://127.0.0.1:8000 and select the synthetic demo. Stop any native server already using port 8000 before starting Compose. The image builds the static frontend in a separate Node stage; the running container contains Python and the static assets, with no Node runtime, optional models, or host data. Only the core dependencies are installed.

```bash
docker compose ps
docker compose logs --tail=100 workbench
docker compose stop          # keep containers and data
docker compose down          # remove containers; preserve named volumes
```

The workbench runs as UID 10001 with a read-only root filesystem, dropped capabilities, localhost-only published ports, a 2 GiB memory ceiling, two CPUs, a bounded temporary filesystem, and rotated logs. Uploads and SQLite state live in the `variantrag_workbench-data` named volume. Delete old runs through the UI to manage growth. Do not start multiple workbench replicas against this volume. Existing native runs are not automatically imported.

These settings use standard [Compose service controls](https://docs.docker.com/reference/compose-file/services/). Docker Desktop stores images and volumes in its Linux VM, so space consumption will not appear in the repository's size. The first build also needs temporary space for Node dependencies and image layers. Inspect actual use with `docker system df`; builds use no persistent pip/npm download cache. Avoid global prune commands that could delete unrelated projects. `docker compose down --volumes` permanently deletes this project's stored runs and optional reference cache; it is not routine shutdown.

## Optional normalization

```bash
docker compose --profile research up --build -d --wait
```

The normalizer listens on http://127.0.0.1:5000/api and uses its own named reference cache. It has a 1 GiB memory ceiling. Test without downloading reference sequences:

```bash
curl 'http://127.0.0.1:5000/api/normalize/2del?only_variants=true&sequence=AAAA'
```

The expected normalized description is `4del`. Container clients use `http://mutalyzer:5000/api`; `localhost` inside a container refers to that container. The web demo remains offline and does not automatically invoke normalization. The CLI can opt in explicitly, for example with inputs mounted read-only:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/tests/fixtures:/inputs:ro" workbench \
  python -m variantrag.cli run --vcf /inputs/demo.vcf \
  --online --mutalyzer-url http://mutalyzer:5000/api \
  --out /app/backend/data/cli-run
```

Cold reference lookup requires internet access and can time out. The optional research profile adds Mutalyzer only; it does not download MedCPT/Docling or install the larger research dependency set. Model-assisted retrieval still follows the separate walkthrough and is not included in this core image.

## Validation and Nextflow

```bash
docker compose --profile research build
python3 scripts/docker_smoke.py --research
```

The smoke test creates an isolated Compose project, publishes no host ports, checks non-root execution, the static UI, a three-candidate demo, run persistence after restart, and real normalization across the container network. It removes only its own test containers and volumes, even on failure. Omitting `--research` tests just the core image. GitHub CI runs the full test on Linux amd64. Local architecture and results are recorded below; image tags are versioned but base images are not pinned by digest.

Nextflow remains a host orchestrator; the image can execute its Python tasks:

```bash
docker compose build workbench
nextflow run backend/main.nf -profile demo,docker --outdir results/docker-nextflow
```

Java and Nextflow must be installed on the host. The Nextflow Docker profile runs tasks with the host user's UID/GID so bind-mounted task outputs remain writable on Linux. The web service still runs as UID 10001. Do not mount the Docker socket into the web workbench.

This is a local research deployment. It does not add public hosting, authentication, TLS, or biological validation.

## Local verification — 2026-09-11

Both images built on Docker Desktop with Linux arm64. The isolated full smoke test passed (static UI, three demo candidates, persistence after restart, and `2del` → `4del` normalization over service DNS). All 51 regression tests passed in a disposable Linux container, with two upstream deprecation warnings. Nextflow 26.04.6 completed parse, evidence assembly, and ranking using the Docker profile. The build includes `procps` for Nextflow task metrics and confines Mutalyzer's compiler/Git/CMake tools to its builder stage. The core build context was about 178 KB; generated data and host dependencies were excluded.

Linux amd64 validation is configured in GitHub Actions but has not yet run remotely. This integration check is not a fresh OS-image vulnerability scan. The September 9 audit remains the dated record of dependency advisory checks.
