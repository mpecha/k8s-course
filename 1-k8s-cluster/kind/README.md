# kind cluster

Local Kubernetes cluster using [kind](https://kind.sigs.k8s.io/), run from a
small tools container so you do not need kind, kubectl or helm installed on
the host. Only Docker is required.

## Layout

| File | Purpose |
|------|---------|
| `Dockerfile` | Alpine image with kind, kubectl and helm |
| `compose.yaml` | Tools container: host network, Docker socket, this dir mounted at `/workspace` |
| `kind.yaml` | Cluster definition: 1 control-plane, 5 workers labelled `workload=general` |
| `scripts/create-cluster.sh` | Creates cluster `dev` |
| `scripts/delete-cluster.sh` | Deletes cluster `dev` and cleans up |

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

## Delete the cluster

```sh
scripts/delete-cluster.sh
```

Runs from the host. Deletes the cluster, removes `.kube` and the tools image.

## Change the node layout

Edit `kind.yaml` and recreate the cluster. kind cannot add or remove nodes
from a running cluster.
