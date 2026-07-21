# GPU warm start(cuOpt)

[← User Manual Index](index.en.md)

!!! info "Scope of this page"
    Covers the setup procedure for cuopt in WSL2/Docker and configuration of the CLI/HTTP backend. For principles on how it works, when it doesn't work, and actual measured effects, refer to [Method Guide 7. GPU warm start](../playbook/07-gpu.en.md).

`mk.cuopt_warmstart` encapsulates the division of labor "GPU searches for feasible solutions, CPU proves optimality" into a single function.
It runs NVIDIA cuOpt (MIP heuristics on the GPU) for a short time to find a feasible solution, injects it into SCIP via `addSol`, and then continues with standard `optimize()`. Since cuOpt itself does not prove optimality, improving the lower bound and proving optimality is left to the SCIP side. For the effects of the method and conditions where it is ineffective, refer to [Method Guide 7. GPU warm start](../playbook/07-gpu.en.md).

## Installation (WSL2)

Keep SCIP/PySCIPOpt on Windows as is, and place only the cuOpt core as a separate environment on WSL2 Ubuntu (since cuOpt assumes Linux + NVIDIA GPU).

```bash
# Inside WSL2 Ubuntu
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 ~/cuopt-env
source ~/cuopt-env/bin/activate
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-cu13==25.10.*"
```

After installation, `~/cuopt-env/bin/cuopt_cli` will be the CLI executable file.

## Behavior in environments without a GPU (Design)

- The GPU feature is **completely optional**. Nothing is added to the dependencies of the minlpkit core (gpu.py uses only stdlib + pyscipopt), and since the cuOpt core is placed in a separate venv on the WSL2 side, **minlpkit will never download anything on an environment where it is not installed**.
- You can check if it is installed using `mk.cuopt_available()` (bool, in-process cache). If you call `cuopt_warmstart`/`cuopt_concurrent` without it being installed, it raises a `RuntimeError` with installation instructions (it does not output a raw subprocess error).
- For the triggering conditions of the diagnostic rule `gpu_primal` (the design where it triggers even if the GPU is not installed and the reasons for it), refer to the "What you can learn from the diagnostics" section in [Method Guide 7. GPU warm start](../playbook/07-gpu.en.md). The recipe includes a reference to the installation procedure on this page.

## Example usage

```python
import minlpkit as mk

m = build_model()          # PySCIPOpt Model (before optimization)
res = mk.cuopt_warmstart(m, time_limit=15)
print(res["objective"], res["accepted"])  # Objective value found by cuOpt / Whether it can be injected into SCIP

m.setParam("limits/time", 60)
m.optimize()                # SCIP continues the proof starting from the injected solution
```

- You can swap the startup command with `cuopt_cmd`. The default value assumes the environment on WSL2.
  (Example: `["wsl", "-d", "Ubuntu", "--", "/home/username/cuopt-env/bin/cuopt_cli"]`)
  If the beginning of the command list does not start with `"wsl"`, it is considered a native execution, and path conversion from Windows to WSL is skipped.
- If cuOpt fails to obtain a feasible solution (when `.sol` is a dummy filled with zero objective values), injection is skipped and `res["accepted"]` becomes `False`.
- A worked example of a 4-arm comparison (pure SCIP / cuOpt alone / hybrid / concurrent):
  `experiments/run_gpu_heuristic.py` → `results/gpu/<model>_<scale>_compare.csv`.

## Resident type (Concurrent): `mk.cuopt_concurrent`

While `cuopt_warmstart` is a serial type that waits for the GPU to finish, `cuopt_concurrent` is a concurrent type that immediately enters `optimize()` while running cuOpt as a subprocess. As soon as cuOpt finishes, an event handler injects the solution into the running SCIP (zero serial time waiting for the GPU).

```python
h = mk.cuopt_concurrent(m, time_limit=15, num_cpu_threads=8)
m.setParam("limits/time", 60)
m.optimize()               # Runs concurrently with cuOpt. Injects into incumbent as soon as it finishes
info = h.result()          # injected / objective / inject_time / wall_time
```

- Actual measurement (gap large): Serial hybrid = GPU 17s + SCIP 60s = 77s total, whereas concurrent = 60s total yielding the same solution.
- The injection timing is rate-limited by SCIP's event firing interval (the granularity of one root LP re-solve).
  **At a scale where the root LP itself consumes all the time budget (e.g., gap xl = 240,000 binaries), the event will not fire and injection cannot be performed** — in that case, use the serial `cuopt_warmstart` (actual measurements for their appropriate usage are in FINDINGS Section 7). If `n_events` in `h.result()` is 0, this state is occurring.
- MPS/.sol is automatically staged to native WSL/tmp (because I/O on 9p `/mnt/` at this size is dominantly slow, taking +20s for reads / +19s for writes. FINDINGS Section 7).
- `num_cpu_threads` throttles the CPU-side B&B threads of cuOpt, suppressing CPU contention with the concurrently running SCIP.

## Remote Server Configuration (cuOpt self-hosted HTTP backend)

Instead of striking the WSL2 CLI on the same machine, it also supports a configuration where a **cuOpt server (REST API) is set up on a GPU machine on the LAN and struck via HTTP**. On the client side, by simply setting the environment variable `MINLPKIT_CUOPT_URL` (or the `server_url=` argument), `mk.cuopt_warmstart` / `mk.cuopt_concurrent` / `mk.cuopt_available` automatically switches to the HTTP backend (resolution order: Argument > Environment Variable > CLI).

**API specifications (investigation results, with sources)**: The official client `cuopt-sh-client` parses the MPS into a cuOpt data model JSON **on the client side**, and sends it as JSON to `POST /cuopt/request` (there is no HTTP endpoint that accepts raw MPS). This backend also builds the same data model JSON (`csr_constraint_matrix` / `constraint_bounds` / `objective_data` / `variable_bounds` / `variable_types` / `variable_names` / `solver_config`) directly from the PySCIPOpt linear structure and sends it (to avoid the `cuopt_mps_parser` dependency. **Dedicated for linear MILP** — cuOpt itself is dedicated for MILP). If the response is only `{"reqId": ...}`, it polls `GET /cuopt/solution/{reqId}`, extracts `response.solver_response.solution.vars` (variable name -> value) / `primal_objective` / `status`, converts it to a SCIP-compatible .sol, and injects it using `readSolFile` + `addSol`. Health check is `GET /cuopt/health` (200).
(Sources: [cuOpt self-hosted server (25.10)](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/quick-start.html), [client-api reference](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/client-api/sh-cli-api.html), [LP/MILP examples](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/examples/milp-examples.html), wire format is in `python/cuopt_self_hosted/cuopt_sh_client` of [NVIDIA/cuopt](https://github.com/NVIDIA/cuopt))

> **Validation scope of the implementation**: Compliance with official specs + mock contract tests (`tests/test_gpu_http.py`, a mock server faithful to the official request/response shapes), plus E2E connectivity tests against a real server (health check → submit an ultra-small MILP → retrieve cuOpt objective value → `addSol` injection into SCIP) have been confirmed. Infinite bounds are rounded to the `±1e20` sentinel because JSON cannot represent Infinity; thus, strictness on problems containing infinite bounds requires validation depending on the environment.

### Setup on the GPU server side

Set up the cuOpt server on a host with a GPU (Linux, or Windows with WSL2 enabled) using one of the following methods.

**Method A: Official Docker container (Recommended)**

```bash
# On the GPU host (with Docker + NVIDIA Container Toolkit installed)
# Log in to NGC (requires NVIDIA AI Enterprise / NGC API Key)
docker login nvcr.io          # Username: $oauthtoken / Password: <NGC API Key>

# Start the cuOpt server container (Expose all GPUs, listen for REST API on port 8000)
docker run --gpus all -d --rm -p 8000:8000 -e CUOPT_SERVER_PORT=8000 \
  nvcr.io/nvidia/cuopt/cuopt:25.10
```

Confirm the exact image tag by looking at the "pull tag" in the [NGC Catalog](https://catalog.ngc.nvidia.com/) (e.g., `nvcr.io/nvidia/cuopt/cuopt:<tag>` depending on the version. The above assumes the 25.10 series).
Be sure to open the port in the host's firewall to make it reachable from the client.

**Method B: Start directly from the pip package (When an existing Python environment like WSL2 is available)**

```bash
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-server-cu13==25.10.*"
CUOPT_SERVER_PORT=8000 python -m cuopt_server.cuopt_service   # Follow the provided startup command
```

Since the package name and startup command can vary by version, check the exact names for your target version in the [self-hosted server overview](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/index.html). If you want to forward a port from WSL2 to the LAN, `netsh interface portproxy` and opening the firewall for the corresponding port is required.

### Client side (This repository)

```python
import os, minlpkit as mk
os.environ["MINLPKIT_CUOPT_URL"] = "http://<gpu-host>:8000"   # Just this
m = build_model()                       # Linear MILP, before optimization
res = mk.cuopt_warmstart(m, time_limit=15)
m.setParam("limits/time", 60); m.optimize()
```

After setting up the server, first do an E2E check using the connectivity check script (2 steps: health + ultra-small MILP):

```bash
uv run python experiments/check_cuopt_server.py --url http://<gpu-host>:8000
```

API: [`mk.cuopt_warmstart`/`mk.cuopt_concurrent`](../api/live.en.md).