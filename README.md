# k8s-course

Local multi-node Kubernetes clusters in Docker, for learning and
experimenting. Everything runs in containers; the host only needs Docker.

Repository: `git@github.com:mpecha/k8s-course.git`

## Contents

| Directory | Description |
|-----------|-------------|
| [`k8s-cluster/kind`](k8s-cluster/kind/README.md) | Cluster built with [kind](https://kind.sigs.k8s.io/): 1 control-plane + 5 workers |
| [`k8s-cluster/k3d`](k8s-cluster/k3d/README.md) | Cluster built with [k3d](https://k3d.io/) (k3s in Docker): 1 server + 5 agents, nodes can be added and removed at runtime |

Both variants share the same layout and workflow:

```text
k8s-cluster/<flavour>/
├── Dockerfile          tools image: kind or k3d, kubectl, helm
├── compose.yaml        tools container with Docker socket and host network
├── <flavour>.yaml      cluster definition
└── scripts/
    ├── create-cluster.sh
    ├── delete-cluster.sh
    ├── create-node.sh  (k3d only)
    └── delete-node.sh  (k3d only)
```

## Quick start

Pick a flavour and run the scripts through the tools container:

```sh
cd k8s-cluster/k3d        # or k8s-cluster/kind

docker compose run --rm k8s scripts/create-cluster.sh   # create cluster "dev"
docker compose run --rm k8s kubectl get nodes           # run any command
docker compose run --rm k8s                             # or open a shell

scripts/delete-cluster.sh                               # tear everything down
```

The kubeconfig is written to `.kube/config` inside the flavour directory.
To use `kubectl` from the host:

```sh
export KUBECONFIG=$PWD/.kube/config
```

## kind vs k3d

| | kind | k3d |
|---|---|---|
| Distribution | upstream Kubernetes | k3s |
| Add/remove nodes on a running cluster | no, edit `kind.yaml` and recreate | yes, `create-node.sh` / `delete-node.sh` |
| Node memory limit | no | yes, `agentsMemory` in `k3d.yaml` |
| Startup | slower, larger images | faster, smaller images |

See the README in each directory for details.
