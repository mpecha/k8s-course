#!/bin/bash

docker compose run --rm k8s \
  kind delete cluster --name dev

docker compose run --rm k8s sh -lc '
  rm -rf .kube
'

docker compose down \
  --rmi local \
  --volumes \
  --remove-orphans
