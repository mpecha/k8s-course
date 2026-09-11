#!/bin/sh
set -e

N="${1:?usage: create-node.sh <number>}"

IMAGE="$(docker inspect k3d-dev-server-0 --format '{{.Config.Image}}')"

k3d node create "dev-agent-${N}" \
  --cluster dev \
  --role agent \
  --image "$IMAGE" \
  --k3s-node-label workload=general \
  --wait

kubectl get nodes
