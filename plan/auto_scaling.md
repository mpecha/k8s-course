# Plan: local simulation of AWS-style autoscaling (`2-autoscaling/k3d`)

## Context

Goal is to learn Kubernetes autoscaling as it works on AWS/EKS, but first on the
laptop with only Docker. On EKS the chain is:

```
load ↑ → HPA adds pods → pods Pending → Cluster Autoscaler grows the ASG → new EC2 node joins
load ↓ → HPA removes pods → node empty → Cluster Autoscaler drains it and shrinks the ASG
```

Locally we keep every piece real except AWS itself: the **real Cluster Autoscaler
binary** (same image as on EKS) uses its `externalgrpc` cloud provider to talk to a
tiny service that plays the role of the ASG/EC2 API by running `k3d node create` /
`k3d node delete`. Moving to AWS later means swapping `--cloud-provider=externalgrpc`
for `aws`; the HPA, the app and the autoscaler flags stay the same.

Chosen by the user: real Cluster Autoscaler + k3d provider, HPA + node scaling,
delete the leftover clusters first.

## Step 0 - clean up leftovers (cluster `dev` is not touched)

Containers from an earlier attempt are still running but their directory is gone.

- `cd 1-k8s-cluster/k3d && docker compose run --rm -T k8s k3d cluster delete auto`
- `cd 1-k8s-cluster/kind && docker compose run --rm -T k8s kind delete cluster --name mgmt`
- `docker rm -f k3d-cloud-provider-1 auto-lb auto-gg6qr-fq4q5 auto-md-0-s2hjm-r64k8-jjjlg`
- List (`docker ps -a`, `docker network ls`) before and after to confirm only `k3d-dev-*` remains.

## Layout (same conventions as `1-k8s-cluster/k3d`)

```text
2-autoscaling/k3d/
├── README.md
├── Dockerfile               tools image + provider runtime (one image for both)
├── compose.yaml             services: k8s (tools), provider, autoscaler
├── k3d.yaml                 cluster "auto": 1 server, 1 agent labelled workload=general
├── autoscaler/cloud-config.yaml     address: localhost:8086   (no TLS)
├── provider/
│   ├── externalgrpc.proto   trimmed copy of the upstream proto (see below)
│   └── provider.py          ~120 lines, the fake "ASG API"
├── manifests/
│   ├── app.yaml             php-apache Deployment + Service + HPA
│   └── load.yaml            busybox load generator
└── scripts/
    ├── create-cluster.sh
    └── delete-cluster.sh
```

## Pieces

**Dockerfile** - copy of `1-k8s-cluster/k3d/Dockerfile` (k3d, kubectl, helm, docker-cli)
plus `python3`, `grpcio`, `grpcio-tools`; compiles `provider/externalgrpc.proto` to
Python stubs at build time.

**compose.yaml** - all services on `network_mode: host`, like lab 1.
- `k8s`: identical to lab 1 tools service.
- `provider`: same image, `command: python3 provider/provider.py`, Docker socket +
  `.kube/config` mounted, env `CLUSTER=auto MIN=1 MAX=5 NODE_CPU=2`.
- `autoscaler`: `registry.k8s.io/autoscaling/cluster-autoscaler:v1.33.x`, `user: "0"`
  (kubeconfig is root-owned 0600), `restart: unless-stopped`, args:
  `--cloud-provider=externalgrpc --cloud-config=/config/cloud-config.yaml
  --kubeconfig=/kube/config --leader-elect=false --scan-interval=10s
  --scale-down-unneeded-time=1m --scale-down-delay-after-add=1m -v=2`.
  Running it out-of-cluster avoids Helm, RBAC and TLS secrets; on EKS the same
  binary runs as a Deployment.

**k3d.yaml** - cluster `auto`, k3s image pinned to the same minor as the autoscaler
(v1.33), 1 server + 1 agent, label `workload=general` on agents.

**Small nodes** - the host has 20 cores, so nothing would ever go Pending. Agents are
made to look like 2-CPU machines with `--kubelet-arg=system-reserved=cpu=$(nproc)-NODE_CPU`
(the trick already documented in `1-k8s-cluster/k3d/README.md`). `create-cluster.sh`
passes it via `--k3s-arg ...@agent:*`; the provider passes the same arg to
`k3d node create`, so new nodes match.

**provider.py** - stateless; one node group `agents`, source of truth is
`docker ps --filter label=k3d.cluster=auto --filter label=k3d.role=agent`.

| RPC | Implementation |
|---|---|
| `NodeGroups` | one group `agents`, min 1, max 5 |
| `NodeGroupForNode` | `agents` if node name starts with `k3d-auto-agent-`, else empty (server is ignored) |
| `NodeGroupNodes` | instance id `k3s://<container name>` (= k3s `spec.providerID`) |
| `NodeGroupTargetSize` | running agents + creates in flight |
| `NodeGroupIncreaseSize` | background thread: `k3d node create auto-agent-<rand> --cluster auto --role agent --k3s-node-label workload=general --k3s-arg <cpu arg>` x delta (same command as `1-k8s-cluster/k3d/scripts/create-node.sh`) |
| `NodeGroupDeleteNodes` | `k3d node delete` + `kubectl delete node` (same as `delete-node.sh`; on AWS the cloud-controller removes the Node object) |
| `Refresh`, `Cleanup`, `GPULabel`, `GetAvailableGPUTypes`, `NodeGroupDecreaseTargetSize` | trivial / empty |
| `Pricing*`, `NodeGroupTemplateNodeInfo`, `NodeGroupGetOptions` | `UNIMPLEMENTED` (allowed; with min=1 the autoscaler uses the existing agent as template) |

**externalgrpc.proto** - upstream file (release-1.33) imports the full Kubernetes API
protos only for the template-node and options responses, which we do not implement.
The vendored copy drops those two imports and empties those two response messages;
everything else is verbatim. A header comment says so and links the original.

**manifests/app.yaml** - standard HPA walkthrough app `registry.k8s.io/hpa-example`,
`requests.cpu: 500m` (about 3 pods per 2-CPU node), `nodeSelector: workload=general`,
HPA `autoscaling/v2` CPU 50 %, min 1, max 10, `scaleDown.stabilizationWindowSeconds: 60`.
k3s ships metrics-server, nothing to install.

**manifests/load.yaml** - busybox `while true; do wget -q -O- http://php-apache; done`.

**scripts** - `create-cluster.sh`: as lab 1 plus the CPU arg. `delete-cluster.sh`:
as lab 1, `docker compose down` also stops provider and autoscaler.

**Docs / memory** - `2-autoscaling/k3d/README.md` (the chain diagram, local vs AWS
mapping table, run-through below); add a row to the root `README.md` table; update the
`no-kubectl-on-host` memory (the `capi` lab no longer exists).

## Verification (end to end)

```sh
cd 2-autoscaling/k3d
docker compose run --rm k8s scripts/create-cluster.sh      # 1 server + 1 agent
docker compose up -d provider autoscaler
docker compose run --rm k8s kubectl apply -f manifests/app.yaml
docker compose run --rm k8s kubectl apply -f manifests/load.yaml
```

Expect, watching `kubectl get hpa,pods,nodes` and `docker compose logs -f autoscaler provider`:

1. HPA raises replicas 1 → 10, some pods go `Pending`.
2. Autoscaler logs `Scale-up: setting group agents size to N`; provider logs
   `k3d node create`; new `k3d-auto-agent-*` nodes turn `Ready`; Pending pods run.
3. `kubectl delete -f manifests/load.yaml` → HPA drops to 1 after ~1 min → autoscaler
   marks nodes unneeded, drains and removes them → back to 1 agent after ~2-3 min.
4. `kubectl -n kube-system describe cm cluster-autoscaler-status` shows group `agents` 1/1.
5. `scripts/delete-cluster.sh` leaves only `k3d-dev-*` containers.

Things to confirm while implementing: exact `cluster-autoscaler` and `rancher/k3s`
v1.33 patch tags exist; `k3d node create --k3s-arg` works with k3d v5.8.3.

## Open questions (undecided)

- **App via Helm?** Plan uses one plain `app.yaml`. Alternatives: public `podinfo`
  chart with its built-in HPA (no app YAML, needs a stronger load generator) or an
  own local chart (same YAML plus chart wrapper files).
- **Autoscaler via Helm?** Plan runs it as a compose service. Alternative: official
  `autoscaler/cluster-autoscaler` chart, as on EKS; runs in-cluster and reaches the
  provider via `host.k3d.internal:8086`, needs RBAC from the chart.
- `manifests/load.yaml` can be dropped either way in favour of a one-liner:
  `kubectl run load --image=busybox -- sh -c "while true; do wget -q -O- http://php-apache; done"`.
