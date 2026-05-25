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

## Planned Scenario

### 1. Deploy Stable Version (v1)
- Application running, health checks passing
- Metrics and logs collected via Prometheus + Loki

### 2. Introduce a Faulty Release (v2)
Examples:
- Intentionally broken `/ready` endpoint (simulating a failed integration)
- Slow response / memory pressure
- Crash-loop via bad configuration

### 3. Observe the Failure
Using: logs, restart count, latency, pod health, error rate  
→ Identify: what failed, impact scope, whether rollback is required

### 4. Rollback & Recover
```bash
kubectl rollout undo deployment/rollback-lab
kubectl rollout history deployment/rollback-lab
```

Focus: rollback speed, service recovery time, operational impact minimization

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
│       └── ci.yml         # pytest → docker build → kubectl dry-run
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

## CI Pipeline

```
push / PR
  └─ pytest               ← gates everything downstream
       ├─ Docker build     (local only, no push)
       └─ kubectl dry-run  (--dry-run=client, no cluster needed)
```

The pipeline is intentionally minimal — the focus is on the **deployment reliability concepts**, not CI tooling complexity.

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
- [ ] Prometheus metrics (`/metrics` endpoint)
- [ ] Grafana + Loki stack via docker-compose
- [ ] Faulty release simulation (v2 with broken readiness)
- [ ] Rollback timing measurement
- [ ] Minikube-based full end-to-end run
