# Autoscaling on k3d, the way it works on AWS

Local simulation of Kubernetes autoscaling on AWS/EKS. Only Docker is required.

```text
load ↑ → HPA adds pods → pods Pending → Cluster Autoscaler grows the node group → new node joins
load ↓ → HPA removes pods → node empty → Cluster Autoscaler drains it and shrinks the node group
```

Everything is real except AWS itself. The **real Cluster Autoscaler** (same image
as on EKS) uses its `externalgrpc` cloud provider to talk to a small service that
plays the Auto Scaling group: it adds and removes k3d agent nodes.

| On AWS / EKS | In this lab |
|---|---|
| EC2 instance | k3d agent container, made to look like a 2-CPU machine |
| Auto Scaling group, min 1 / max 5 | node group `agents` in `provider/provider.py` |
| `SetDesiredCapacity`, `TerminateInstance` | `k3d node create`, `k3d node delete` |
| Cluster Autoscaler Deployment, `--cloud-provider=aws` | compose service `autoscaler`, `--cloud-provider=externalgrpc` |
| Cloud controller removes the Node of a terminated instance | provider runs `kubectl delete node` |
| metrics-server + HPA | the same (k3s ships metrics-server) |

Moving to AWS means replacing the provider with `--cloud-provider=aws` and an ASG;
the app, the HPA and the autoscaler flags stay the same.

## Nodes

```text
NAME                     STATUS   ROLES
k3d-auto-server-0        Ready    control-plane,master
k3d-auto-app-0           Ready    app
k3d-auto-app-<id>-0      Ready    app                    (added and removed by the autoscaler)
k3d-auto-load-0          Ready    load
```

| Role | Label | Runs | Autoscaled |
|---|---|---|---|
| `app` | `workload=app` | only the `php-apache` pods; looks like a 2-CPU machine, 4 pods fill it | yes, 1 to 5 nodes |
| `load` | `workload=load`, taint `workload=load:NoSchedule` | only the load generator, which tolerates the taint | no, always 1 |
| `control-plane` | | k3s server and system pods | no |

## Layout

| File | Purpose |
|------|---------|
| `Dockerfile` | Tools image (k3d, kubectl, helm) plus Python gRPC for the provider |
| `compose.yaml` | Services `k8s` (tools), `provider`, `autoscaler` |
| `k3d.yaml` | Cluster `auto`: k3s version and 1 server; the agents are added by `scripts/create-node.sh` |
| `provider/provider.py` | The fake Auto Scaling group (gRPC server on `127.0.0.1:8086`) |
| `provider/client.py` | Call the provider by hand: `groups`, `nodes`, `increase N`, `delete NODE` |
| `provider/externalgrpc.proto` | Cluster Autoscaler provider API, copied from upstream |
| `autoscaler/cloud-config.yaml` | Tells the autoscaler where the provider listens |
| `manifests/app.yaml` | `php-apache` Deployment (500m CPU per pod), Service, HPA 1 to 6 pods at 50 % CPU |
| `manifests/load.yaml` | Load generator: 4 "visitors", running only on the `workload=load` agent |
| `scripts/create-cluster.sh`, `scripts/delete-cluster.sh` | Create and delete everything |
| `scripts/create-node.sh` | Adds a named agent (`app` or `load`); also called by the provider on scale-up |
| `scripts/watch.sh` | One-screen live view of the demo |

## Build

```sh
docker compose build
```

Builds the image `autoscaling-tools` from `Dockerfile`; the services `k8s` and
`provider` both use it. The `autoscaler` image is not built, it is pulled from
`registry.k8s.io` on first start.

Building by hand is optional: the first `docker compose run` or `docker compose up`
builds the image if it is missing. Rebuild after changing:

| Changed file | What to do |
|---|---|
| `Dockerfile`, `provider/externalgrpc.proto` | `docker compose build`, then `docker compose up -d provider` |
| `provider/provider.py` | `docker compose restart provider` (the directory is mounted, no rebuild) |
| `compose.yaml` | `docker compose up -d provider autoscaler` (recreates what changed) |
| `autoscaler/cloud-config.yaml` | `docker compose restart autoscaler` |

Tool versions are build arguments, for example:

```sh
docker compose build --build-arg KUBECTL_VERSION=v1.33.5
docker compose build --no-cache        # rebuild everything from scratch
```

## Run it

```sh
docker compose run --rm k8s scripts/create-cluster.sh
docker compose up -d provider autoscaler
docker compose run --rm k8s kubectl apply -f manifests/app.yaml
```

Wait about 2 minutes until the HPA shows a CPU value instead of `<unknown>`:

```sh
docker compose run --rm k8s kubectl get hpa
```

Open a second terminal to watch. The script redraws one screen every 5 seconds
(pass another number of seconds as argument):

```sh
docker compose run --rm k8s scripts/watch.sh
```

```text
19:46:18 UTC   refresh 5s, Ctrl+C to stop

LOAD    4 visitors
HPA     cpu 78% of target 50%   replicas 4 -> 6   (min 1, max 6)
PODS    4 running, 0 starting, 2 waiting for a node

AGENTS  1
  k3d-auto-app-0               Ready     4 pods

AUTOSCALER (UTC)
  19:47:06  Pod default/php-apache-d87786b54-wsfqp is unschedulable
  19:47:06  Scale-up: setting group agents size to 2

PROVIDER (UTC)
  19:47:06  scale up agents: 1 -> 2
  19:47:06  + scripts/create-node.sh app 519b9f
```

| Line | Meaning |
|---|---|
| `LOAD` | running load generator pods ("visitors") |
| `HPA` | average CPU of the app pods against the target; `replicas current -> desired` |
| `PODS` | `waiting for a node` = Pending because no agent has 500m free; this triggers a scale-up |
| `AGENTS` | nodes of the group with the number of app pods on each (4 fill a node) |
| `AUTOSCALER`, `PROVIDER` | the last decisions of the Cluster Autoscaler and the node actions that followed |

To watch a single resource, wrap the command in `watch` on the host. It redraws
one table every second, so each node or pod appears once:

```sh
watch -n 1 docker compose run --rm -T k8s kubectl get nodes -o wide
watch -n 1 docker compose run --rm -T k8s kubectl get hpa,pods -o wide
```

Do not use `kubectl get ... -w` for this: it prints a new line for every change of
an object, so the same node shows up many times.

Logs of the two services: `docker compose logs -f provider autoscaler`.

### Scale up

```sh
docker compose run --rm k8s kubectl apply -f manifests/load.yaml
```

1. CPU rises above 50 %, the HPA adds pods (1 → 2 → 4 → 6).
2. One agent fits 4 pods; the rest stay `Pending` with `Insufficient cpu`.
3. Autoscaler logs `Scale-up: setting group agents size to 2`, the provider logs
   `create-node.sh app <id>`, the node turns `Ready` and the Pending pods start.
4. Ends at 6 pods on 2 agents after about 4 minutes.

### Scale down

```sh
docker compose run --rm k8s kubectl delete -f manifests/load.yaml
```

1. After 2 to 3 minutes the HPA is back at 1 pod.
2. The autoscaler taints unneeded agents `DeletionCandidateOfClusterAutoscaler`, waits
   1 minute, then logs `Scale-down: removing node ...` (pods still on the node are
   evicted first); the provider logs `k3d node delete`.
3. Ends at 1 agent (the group minimum) after 3 to 6 minutes.

The autoscaler publishes its view of the node group here:

```sh
docker compose run --rm k8s kubectl -n kube-system describe cm cluster-autoscaler-status
```

## Play the autoscaler yourself

With the `autoscaler` service stopped, call the provider by hand:

```sh
docker compose stop autoscaler
docker compose run --rm k8s python3 provider/client.py groups      # agents min=1 max=5 target=1
docker compose run --rm k8s python3 provider/client.py increase 1
docker compose run --rm k8s python3 provider/client.py nodes
docker compose run --rm k8s python3 provider/client.py delete k3d-auto-app-<id>-0
```

## Delete everything

```sh
scripts/delete-cluster.sh
```

Runs from the host. Stops provider and autoscaler, deletes the cluster, removes
`.kube` and the tools image.

## Troubleshooting

**New node never becomes Ready, provider logs `create ... failed, removing it`.**
Check `docker logs <node>` while it exists. `too many open files` means the host
ran out of inotify instances (default 128, every k3s node needs some). Raise the
limit or stop another cluster (`k3d cluster stop dev` in lab 1):

```sh
sudo sysctl fs.inotify.max_user_instances=1024 fs.inotify.max_user_watches=524288
```

The autoscaler retries on its own, as it does when an EC2 launch fails.

## Notes

- Demo timers (`--scale-down-unneeded-time=1m` and others in `compose.yaml`, HPA
  `stabilizationWindowSeconds: 60`) are much shorter than the defaults of 10 and
  5 minutes. Do not copy them to production.
- The provider speaks plain gRPC without TLS and listens on localhost only.
  Upstream recommends mTLS for anything real.
- Node size is set with `NODE_CPU` in `compose.yaml`; group size with `MIN` / `MAX`.
- The provider counts only agents with the Docker label `autoscaling.group=agents`
  (set by `create-node.sh app`) as members of its group, so the autoscaler never
  touches the load node. On AWS these would be two node groups, of which only one
  is registered with the Cluster Autoscaler.
- The role shown by `kubectl get nodes` is the label `node-role.kubernetes.io/<role>`.
  A kubelet may not give it to itself, so `create-node.sh` sets it with `kubectl label`
  once the node has joined. Pods therefore select nodes by `workload=`, a label the
  node has from its first second.
- The demo is sized to need 2 agents (6 pods, 4 visitors), which fits a host with
  the default inotify limit. For a bigger run raise the limit (see Troubleshooting),
  then raise `maxReplicas` in `app.yaml` and `replicas` in `load.yaml`: one visitor
  keeps about two pods busy at the 50 % target, and 4 pods fill an agent.
