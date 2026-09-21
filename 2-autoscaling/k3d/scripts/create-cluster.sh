#!/bin/sh
set -e

mkdir -p .kube

# Server only; agents are added by name below
k3d cluster create \
  --config k3d.yaml

scripts/create-node.sh app    # k3d-auto-app-0: first node of the autoscaled group
scripts/create-node.sh load   # k3d-auto-load-0: fixed node for the load generator

kubectl get nodes
