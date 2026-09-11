#!/bin/bash

docker compose run --rm k8s \
  k3d cluster delete dev

docker compose run --rm k8s sh -lc '
  rm -rf .kube
'

docker compose down \
  --rmi local \
  --volumes \
  --remove-orphans
