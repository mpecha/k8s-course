"""Fake "AWS Auto Scaling group" for a k3d cluster.

Implements the Cluster Autoscaler externalgrpc API. One node group, "agents":
growing it runs `k3d node create`, shrinking it runs `k3d node delete`.
The list of Docker containers is the only state.
"""

import os
import subprocess
import threading
import uuid
from concurrent import futures

import grpc

import externalgrpc_pb2 as pb
import externalgrpc_pb2_grpc as pb_grpc

CLUSTER = os.environ.get("CLUSTER", "auto")
MIN = int(os.environ.get("MIN", "1"))
MAX = int(os.environ.get("MAX", "5"))
PORT = os.environ.get("PORT", "8086")

GROUP = "agents"
# Members of the group are the "app" nodes made by scripts/create-node.sh: Docker
# label autoscaling.group=agents, Kubernetes label workload=app. The load node
# belongs to no group, so the autoscaler leaves it alone.
DOCKER_LABEL = f"autoscaling.group={GROUP}"
NODE_LABEL = ("workload", "app")

lock = threading.Lock()
creating = set()  # node names with `k3d node create` in flight
deleting = set()  # node names with `k3d node delete` in flight


def run(*cmd):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def running():
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}",
         "--filter", f"label=k3d.cluster={CLUSTER}",
         "--filter", f"label={DOCKER_LABEL}"],
        check=True, capture_output=True, text=True).stdout
    return set(out.split())


def members():
    """Node name -> state, for every node that counts towards the group size."""
    with lock:
        nodes = {n: pb.InstanceStatus.instanceRunning for n in running()}
        nodes.update({n: pb.InstanceStatus.instanceCreating for n in creating})
        for n in deleting:
            nodes.pop(n, None)
    return nodes


def node_name(node_id):
    return f"k3d-{CLUSTER}-app-{node_id}-0"


def create_node(node_id):
    name = node_name(node_id)
    try:
        run("scripts/create-node.sh", "app", node_id)
    except subprocess.CalledProcessError as e:
        # Like an EC2 instance that fails to launch: remove it, the group shrinks
        # back and the autoscaler tries again
        print(f"create {name} failed, removing it: {e.stderr[-300:]}")
        subprocess.run(["k3d", "node", "delete", name], capture_output=True)
    finally:
        with lock:
            creating.discard(name)


def delete_node(name):
    try:
        run("k3d", "node", "delete", name)
        # On AWS the cloud controller removes the Node object of a terminated instance
        run("kubectl", "delete", "node", name, "--ignore-not-found")
    except subprocess.CalledProcessError as e:
        print(f"delete {name} failed: {e.stderr}")
    finally:
        with lock:
            deleting.discard(name)


class Provider(pb_grpc.CloudProviderServicer):
    # RPCs not defined here (pricing, template node, per-group options) answer
    # UNIMPLEMENTED, which the autoscaler accepts.

    def NodeGroups(self, request, context):
        return pb.NodeGroupsResponse(
            nodeGroups=[pb.NodeGroup(id=GROUP, minSize=MIN, maxSize=MAX)])

    def NodeGroupForNode(self, request, context):
        if request.node.labels.get(NODE_LABEL[0]) == NODE_LABEL[1]:
            return pb.NodeGroupForNodeResponse(
                nodeGroup=pb.NodeGroup(id=GROUP, minSize=MIN, maxSize=MAX))
        return pb.NodeGroupForNodeResponse(nodeGroup=pb.NodeGroup())

    def NodeGroupNodes(self, request, context):
        # k3s sets spec.providerID to k3s://<node name>
        return pb.NodeGroupNodesResponse(instances=[
            pb.Instance(id=f"k3s://{name}",
                        status=pb.InstanceStatus(instanceState=state))
            for name, state in sorted(members().items())])

    def NodeGroupTargetSize(self, request, context):
        return pb.NodeGroupTargetSizeResponse(targetSize=len(members()))

    def NodeGroupIncreaseSize(self, request, context):
        size = len(members())
        if request.delta <= 0 or size + request.delta > MAX:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          f"size {size} + delta {request.delta} is outside 1..{MAX}")
        print(f"scale up {GROUP}: {size} -> {size + request.delta}")
        for _ in range(request.delta):
            node_id = uuid.uuid4().hex[:6]
            with lock:
                creating.add(node_name(node_id))
            threading.Thread(target=create_node, args=(node_id,)).start()
        return pb.NodeGroupIncreaseSizeResponse()

    def NodeGroupDeleteNodes(self, request, context):
        names = [n.name for n in request.nodes]
        size = len(members())
        if size - len(names) < MIN:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          f"size {size} - {len(names)} is below min {MIN}")
        print(f"scale down {GROUP}: {size} -> {size - len(names)} {names}")
        for name in names:
            with lock:
                deleting.add(name)
            threading.Thread(target=delete_node, args=(name,)).start()
        return pb.NodeGroupDeleteNodesResponse()

    def NodeGroupDecreaseTargetSize(self, request, context):
        return pb.NodeGroupDecreaseTargetSizeResponse()

    def Refresh(self, request, context):
        return pb.RefreshResponse()

    def Cleanup(self, request, context):
        return pb.CleanupResponse()

    def GPULabel(self, request, context):
        return pb.GPULabelResponse()

    def GetAvailableGPUTypes(self, request, context):
        return pb.GetAvailableGPUTypesResponse()


if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_CloudProviderServicer_to_server(Provider(), server)
    server.add_insecure_port(f"127.0.0.1:{PORT}")
    server.start()
    print(f"node group '{GROUP}' of cluster '{CLUSTER}': min {MIN}, max {MAX}, "
          f"listening on 127.0.0.1:{PORT}")
    server.wait_for_termination()
