#!/bin/sh
set -e

mkdir -p .kube

# Make every agent look like a NODE_CPU-core machine to the scheduler
RESERVED="$(( $(nproc) - ${NODE_CPU:-2} ))"

k3d cluster create \
  --config k3d.yaml \
  --k3s-arg "--kubelet-arg=system-reserved=cpu=${RESERVED}@agent:*"

kubectl get nodes
