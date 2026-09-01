# k8s-rollback-lab

> **Deployment Reliability & Rollback Experiment**  
> Simulating SDV/ADAS-style release risk management in a cloud-native environment

---

## Background & Motivation

During my internship in a Kubernetes-based MES environment, I encountered situations where the hardest part of a failure was not the failure itself, but:

- Taking too long to identify the root cause
- Not knowing the blast radius quickly enough
- Struggling to make the rollback decision under pressure

I worked on Grafana/Loki observability dashboards, restart monitoring, release coordination, Node-RED version upgrade risk discussions, and troubleshooting distributed software dependencies.

This led me to think more deeply about **"how to build systems that fail safely and recover quickly."**

Reading about SDV/ADAS software platforms — OTA, staged rollouts, Adaptive AUTOSAR, and automotive CI/CD — I realized that the same core challenges apply, but with stricter constraints:

| Challenge | Cloud-native | Automotive/ADAS |
|-----------|-------------|-----------------|
| Deployment reliability | Rolling update | OTA with safety gate |
| Observability | Prometheus/Loki | AUTOSAR Diag / health monitor |
| Rollback | `kubectl rollout undo` | Fallback partition / A/B update |
| Blast radius | Pod/namespace scope | Vehicle-wide, safety-critical |

This experiment is not about building a perfect production system.  
The goal is to deeply understand: **"How can software changes be deployed safely, monitored effectively, and recovered quickly when failures happen?"**

---

## Experiment Goals

Simulate a simplified SDV/ADAS-style deployment reliability workflow, focused on:

- **Deployment risk** — what can go wrong during a release
- **Observability** — detecting failure before users/operators do
- **Rollback** — how fast and how reliably can we recover
- **Operational stability** — minimizing service impact during recovery

---

## Experiment Results (Minikube)

> Conducted on local Minikube cluster (Docker driver, Windows 10)

### Scenario: Faulty v2 release → automatic stall → manual rollback

**Step 1 — Deploy v1 (stable)**
```bash
kubectl apply -f k8s/deployment.yaml   # APP_VERSION=1.0.0, FORCE_NOT_READY=false
kubectl apply -f k8s/service.yaml
```
→ Both Pods reached `1/1 Running` in **~18 seconds**  
→ `/info` confirmed: `version: 1.0.0`, `force_not_ready: false`

**Step 2 — Deploy v2 (faulty)**
```bash
# image: rollback-lab:v2, FORCE_NOT_READY=true
kubectl apply -f k8s/deployment.yaml
```
→ v2 Pods started (`0/1 Running`) but never became Ready  
→ readinessProbe failed every 10s (failureThreshold: 3)  
→ RollingUpdate **stalled** — last v1 Pod preserved automatically  
→ `kubectl rollout status` output:
```
Waiting for deployment "rollback-lab" rollout to finish: 1 old replicas are pending termination...
```

**Step 3 — Rollback**
```bash
kubectl rollout undo deployment/rollback-lab
```
→ v1 Pod restored in **~16 seconds**  
→ `/info` confirmed: `version: 1.0.0`, `force_not_ready: false`

### Timing Summary

| Event | Time |
|-------|------|
| v1 deploy → fully ready | ~18s |
| v2 readinessProbe failure detection | ~35s (initialDelay 5s + period 10s × 3) |
| RollingUpdate stall (v1 preserved) | automatic, no intervention needed |
| `rollout undo` → v1 fully recovered | ~16s |

### Key Observation

`/health` (livenessProbe) returned 200 throughout the entire v2 failure period.  
`/ready` (readinessProbe) returned 503, which was the only signal Kubernetes needed to block traffic and halt the rollout.

This confirms the readiness/liveness separation is not just theoretical — **it was the actual mechanism that prevented the faulty release from reaching users.**

---

## Project Structure

```
k8s-rollback-lab/
├── app/
│   ├── main.py            # FastAPI: /health /ready /info
│   ├── test_main.py       # pytest
│   └── requirements.txt
├── k8s/
│   ├── deployment.yaml    # RollingUpdate + readinessProbe + livenessProbe
│   └── service.yaml
├── .github/
│   └── workflows/
│       └── ci.yml         # pytest → docker build + kubeconform → automated kind-cluster rollback test (CT)
└── Dockerfile
```

---

## Endpoints

| Path | Purpose |
|------|---------|
| `GET /health` | livenessProbe — always 200 if process is alive |
| `GET /ready` | readinessProbe — 503 if not ready (rollback trigger point) |
| `GET /info` | Returns version + env (used to verify rollback success) |

---

## Probe Design

```yaml
readinessProbe:   # Controls traffic routing
  httpGet:
    path: /ready
  failureThreshold: 3   # 3 failures → removed from Service endpoints

livenessProbe:    # Controls container restart
  httpGet:
    path: /health
  failureThreshold: 3   # 3 failures → Pod restarted
```

> **Note:** This project does not handle real sensor data. The analogies below are **conceptual** — intended to map cloud-native patterns to automotive equivalents, not to claim functional equivalence.

Conceptual parallel to automotive/ADAS:
- `readinessProbe` → software maturity gate (analogous to a pre-routing validation before a component receives live data)
- `livenessProbe` → watchdog / health monitor (analogous to ECU-level reset trigger on unresponsive process)

---

## CI/CD Pipeline

### Role Separation

| Layer | Tool | Responsibility |
|-------|------|----------------|
| CI | GitHub Actions | Code quality gate (test, build, manifest validation) |
| CT | GitHub Actions | Automated deploy/rollback regression test (ephemeral kind cluster) |
| CD | ArgoCD (GitOps) — design only, not yet deployed | Automated cluster deployment & Self-Healing |

### CI (GitHub Actions)

```
push / PR
  └─ pytest                    ← blocks everything downstream on failure
       ├─ Docker build          (local only, no push)
       └─ k8s manifest validate (kubeconform, no cluster needed)
            └─ CT: automated deploy/rollback verification (see below)
```

### CT (GitHub Actions)

Once `pytest`, `Docker build`, and `k8s manifest validate` all pass, a fourth job spins up an ephemeral [`kind`](https://kind.sigs.k8s.io/) cluster inside the runner and re-runs the exact Minikube scenario above as an automated regression test:

```
1. Create a kind cluster (discarded at the end of the job)
2. Build the image and load it into kind (no registry push needed)
3. Apply k8s/deployment.yaml (v1) → confirm /ready returns 200
4. Inject the fault via `kubectl set env FORCE_NOT_READY=true` (the committed
   manifest always stays in its stable v1 state — faults are injected at
   runtime, not baked into the repo)
5. Assert the rollout stalls (a rollout that *succeeds* here is the failure case)
6. `kubectl rollout undo` → confirm the deployment recovers and /ready returns 200 again
```

This turns the manual Minikube walkthrough above into a repeatable check that runs on every pull request, rather than a one-off manual verification.

### CD (ArgoCD)

```
main branch updated
  └─ ArgoCD watches k8s/ directory
       ├─ deployment.yaml changed → auto-sync to cluster
       ├─ Self-Healing: cluster drift from Git state → auto-revert
       └─ Rollback: git revert → ArgoCD deploys previous version
```

### Why ArgoCD over GitHub Actions CD

Instead of a **Push-based** approach (Actions runs `kubectl apply` directly), ArgoCD was chosen for the following reasons:

- **Security**: Push-based CD requires storing cluster credentials in GitHub Secrets. ArgoCD runs inside the cluster and pulls from Git — no credentials exposed externally
- **GitOps**: `k8s/` directory is the Single Source of Truth. Declared state always matches actual cluster state
- **Self-Healing**: If someone modifies the cluster directly, ArgoCD automatically reverts to the Git state — operational stability guaranteed
- **Rollback**: A single `git revert` redeploys the previous version. No separate rollback command needed

### ArgoCD Setup (Minikube)

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access dashboard
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

> ArgoCD Application manifest (`k8s/argocd-app.yaml`) — implementation in progress.

---

## Local Setup

```bash
pip install -r app/requirements.txt
cd app && pytest test_main.py -v
```

```bash
# Run the server
cd app
uvicorn main:app --reload
# → http://localhost:8000/health
```

```bash
# Validate k8s manifests without a cluster
kubectl apply -f k8s/deployment.yaml --dry-run=client
kubectl apply -f k8s/service.yaml --dry-run=client
```

---

## Key Concepts Being Explored

- Why rollback matters in operational systems
- Why observability is the prerequisite to release decisions
- Why deployment itself is a risk event, not just a delivery event
- How "detect → isolate → recover" translates across cloud-native and automotive environments
- The gap between "it works locally" and "operational reliability"

---

## Roadmap

- [x] FastAPI app with health/ready/info endpoints
- [x] Kubernetes deployment with probes
- [x] CI pipeline (pytest + docker build + dry-run)
- [x] Prometheus metrics (`/metrics` endpoint)
- [x] Grafana + Prometheus stack via docker-compose
- [x] Faulty release simulation (v2 with broken readiness)
- [x] Rollback timing measurement
- [x] Minikube-based full end-to-end run
- [x] Automated CT job (GitHub Actions + kind) verifying the deploy/rollback scenario on every PR
