#!/bin/sh
set -e

N="${1:?usage: delete-node.sh <number>}"

k3d node delete "k3d-dev-agent-${N}-0"
kubectl delete node "k3d-dev-agent-${N}-0"

kubectl get nodes
