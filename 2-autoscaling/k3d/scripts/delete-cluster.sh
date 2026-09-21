#!/bin/bash

docker compose down \
  --remove-orphans

docker compose run --rm k8s \
  k3d cluster delete auto

docker compose run --rm k8s sh -lc '
  rm -rf .kube
'

docker compose down \
  --rmi local \
  --volumes \
  --remove-orphans
