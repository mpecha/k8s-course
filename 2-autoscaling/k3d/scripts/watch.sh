#!/bin/bash
# One-screen live view of the demo, redrawn every few seconds.
# usage: docker compose run --rm k8s scripts/watch.sh [seconds]

INTERVAL="${1:-5}"

# Last interesting log lines of a compose service, as "HH:MM:SS  message"
events() {
  docker logs --timestamps "autoscaling-$1-1" 2>&1 \
    | grep -E "$2" \
    | tail -n 4 \
    | sed -E -e 's/^[^T]*T([0-9:]{8})[^ ]* /\1  /' \
             -e 's/[IWE][0-9]{4} [0-9:.]+ +[0-9]+ [A-Za-z_.]+:[0-9]+\] //' \
    | cut -c1-110
}

while true; do
  hpa="$(kubectl get hpa php-apache -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}% of target {.spec.metrics[0].resource.target.averageUtilization}%   replicas {.status.currentReplicas} -> {.status.desiredReplicas}   (min {.spec.minReplicas}, max {.spec.maxReplicas})' 2>/dev/null)"
  pods="$(kubectl get pods -l app=php-apache --no-headers \
    -o custom-columns='PHASE:.status.phase,NODE:.spec.nodeName' 2>/dev/null)"
  nodes="$(kubectl get nodes -l workload=app --no-headers 2>/dev/null | awk '{print $1, $2}')"
  load="$(kubectl get deploy load -o jsonpath='{.status.readyReplicas}' 2>/dev/null)"

  out="$(
    echo "$(date +%T) UTC   refresh ${INTERVAL}s, Ctrl+C to stop"
    echo
    echo "LOAD    ${load:-0} visitors"
    echo "HPA     cpu ${hpa:-no data yet}"
    # Pending without a node = no room anywhere, this is what triggers a scale-up
    echo "PODS    $(echo "$pods" | grep -c Running) running," \
         "$(echo "$pods" | awk '$1 == "Pending" && $2 != "<none>"' | grep -c .) starting," \
         "$(echo "$pods" | awk '$1 == "Pending" && $2 == "<none>"' | grep -c .) waiting for a node"
    echo
    echo "AGENTS  $(echo "$nodes" | grep -c .)"
    echo "$nodes" | while read -r name status; do
      [ -n "$name" ] && printf '  %-28s %-9s %s pods\n' "$name" "$status" \
        "$(echo "$pods" | awk -v n="$name" '$2 == n' | grep -c .)"
    done
    echo
    echo "AUTOSCALER (UTC)"
    events autoscaler 'Scale-up:|Scale-down: removing|unschedulable$' | sed 's/^/  /'
    echo
    echo "PROVIDER (UTC)"
    events provider '^[^+]*(scale |create .* failed)|create-node.sh|k3d node delete' \
      | sed -E -e 's/ --cluster.*//' -e 's/^/  /'
  )"

  printf '\033[H\033[2J%s\n' "$out"
  sleep "$INTERVAL"
done
