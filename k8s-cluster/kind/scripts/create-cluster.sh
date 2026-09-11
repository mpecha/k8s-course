#!/bin/sh
set -e

mkdir -p .kube

kind create cluster \
  --name dev \
  --config kind.yaml

kubectl get nodes
