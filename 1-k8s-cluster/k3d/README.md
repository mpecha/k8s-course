# k3d cluster

Local Kubernetes cluster using [k3d](https://k3d.io/) (k3s in Docker), run
from a small tools container so you do not need k3d, kubectl or helm installed
on the host. Only Docker is required.

## Layout

| File | Purpose |
|------|---------|
| `Dockerfile` | Alpine image with k3d, kubectl and helm |
| `compose.yaml` | Tools container: host network, Docker socket, this dir mounted at `/workspace` |
| `k3d.yaml` | Cluster definition: 1 server, 5 agents labelled `workload=general` |
| `scripts/create-cluster.sh` | Creates cluster `dev` |
| `scripts/delete-cluster.sh` | Deletes cluster `dev` and cleans up |
| `scripts/create-node.sh N` | Adds agent node `k3d-dev-agent-N-0` |
| `scripts/delete-node.sh N` | Removes agent node `k3d-dev-agent-N-0` |

## Create the cluster

```sh
docker compose run --rm k8s scripts/create-cluster.sh
```

The kubeconfig is written to `.kube/config` in this directory.

## Use the cluster

Run any command inside the tools container:

```sh
docker compose run --rm k8s kubectl get nodes
docker compose run --rm k8s helm list -A
```

Or open a shell:

```sh
docker compose run --rm k8s
```

To use `kubectl` from the host instead:

```sh
export KUBECONFIG=$PWD/.kube/config
```

## Add or remove a node

```sh
docker compose run --rm k8s scripts/create-node.sh 5
docker compose run --rm k8s scripts/delete-node.sh 5
```

The number is appended to the node name. The initial agents are numbered
0 to 4, so start at 5. Added nodes get the same image and `workload=general`
label as the initial agents. k3d always appends `-0` to manually created
nodes, so the node appears as `k3d-dev-agent-5-0`.

## Delete the cluster

```sh
scripts/delete-cluster.sh
```

Runs from the host. Deletes the cluster, removes `.kube` and the tools image.

## Node resources

k3d can limit memory but has no CPU flag. To make agents look like 1 CPU / 2 GiB
to the scheduler, add to `k3d.yaml` (replace 19 with host cores minus 1):

```yaml
options:
  runtime:
    agentsMemory: 2g
  k3s:
    extraArgs:
      - arg: --kubelet-arg=system-reserved=cpu=19
        nodeFilters:
          - agent:*
```

To actually cap CPU usage as well, apply a Docker limit after creation:

```sh
docker update --cpus 1 k3d-dev-agent-0
```
