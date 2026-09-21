#!/bin/sh
# Adds a named agent to the cluster. Used by create-cluster.sh for the two initial
# agents and by the provider for every node the Cluster Autoscaler asks for.
#
# usage: create-node.sh app [id]   ->  node k3d-auto-app-0 or k3d-auto-app-<id>-0
#        create-node.sh load       ->  node k3d-auto-load-0
set -e

KIND="${1:?usage: create-node.sh app|load [id]}"
CLUSTER="${CLUSTER:-auto}"
NAME="${CLUSTER}-${KIND}${2:+-$2}"
NODE="k3d-${NAME}-0"

IMAGE="$(docker inspect "k3d-${CLUSTER}-server-0" --format '{{.Config.Image}}')"

case "$KIND" in
  app)
    # Looks like a NODE_CPU-core machine to the scheduler. The Docker label marks
    # it as a member of the autoscaled group (see provider/provider.py).
    RESERVED="$(( $(nproc) - ${NODE_CPU:-2} ))"
    set -- --k3s-arg "--kubelet-arg=system-reserved=cpu=${RESERVED}" \
           --runtime-label autoscaling.group=agents
    ;;
  load)
    set --
    ;;
  *)
    echo "unknown kind: $KIND" >&2
    exit 1
    ;;
esac

k3d node create "$NAME" \
  --cluster "$CLUSTER" \
  --role agent \
  --image "$IMAGE" \
  --k3s-node-label "workload=${KIND}" \
  "$@" \
  --wait --timeout 2m

# Shown in the ROLES column. A kubelet may not set node-role labels on itself,
# so this is done after the node has joined.
kubectl label node "$NODE" "node-role.kubernetes.io/${KIND}=true" --overwrite

# Only pods that tolerate the taint (the load generator) run on the load node.
# Set here and not with --node-taint: k3d builds a new agent as a copy of an
# existing one, k3s arguments included, so the taint would leak to app nodes.
if [ "$KIND" = load ]; then
  kubectl taint node "$NODE" workload=load:NoSchedule --overwrite
fi
