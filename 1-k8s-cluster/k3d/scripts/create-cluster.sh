#!/bin/sh
set -e

mkdir -p .kube

k3d cluster create \
  --config k3d.yaml

kubectl get nodes
