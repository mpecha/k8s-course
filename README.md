# k8s-course

Local multi-node Kubernetes clusters in Docker, for learning and
experimenting. Everything runs in containers; the host only needs Docker.

Repository: `git@github.com:mpecha/k8s-course.git`

## Contents

| Directory | Description |
|-----------|-------------|
| [`1-k8s-cluster/kind`](1-k8s-cluster/kind/README.md) | Cluster built with [kind](https://kind.sigs.k8s.io/): 1 control-plane + 5 workers |
| [`1-k8s-cluster/k3d`](1-k8s-cluster/k3d/README.md) | Cluster built with [k3d](https://k3d.io/) (k3s in Docker): 1 server + 5 agents, nodes can be added and removed at runtime |
| [`2-autoscaling/k3d`](2-autoscaling/k3d/README.md) | Autoscaling as on AWS/EKS: HPA plus the real Cluster Autoscaler, with k3d agents standing in for an EC2 Auto Scaling group |

Both `1-k8s-cluster` variants share the same layout and workflow:

```text
1-k8s-cluster/<flavour>/
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
cd 1-k8s-cluster/k3d        # or 1-k8s-cluster/kind

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
