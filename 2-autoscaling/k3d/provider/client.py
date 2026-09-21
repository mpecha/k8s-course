"""Call the provider by hand, the way the Cluster Autoscaler does.

usage: client.py groups | nodes | increase N | delete NODE_NAME
"""

import sys

import grpc

import externalgrpc_pb2 as pb
import externalgrpc_pb2_grpc as pb_grpc

GROUP = "agents"

api = pb_grpc.CloudProviderStub(grpc.insecure_channel("127.0.0.1:8086"))
cmd, arg = (sys.argv[1:] + [None, None])[:2]

if cmd == "groups":
    for g in api.NodeGroups(pb.NodeGroupsRequest()).nodeGroups:
        size = api.NodeGroupTargetSize(pb.NodeGroupTargetSizeRequest(id=g.id)).targetSize
        print(f"{g.id} min={g.minSize} max={g.maxSize} target={size}")
elif cmd == "nodes":
    for i in api.NodeGroupNodes(pb.NodeGroupNodesRequest(id=GROUP)).instances:
        print(i.id, pb.InstanceStatus.InstanceState.Name(i.status.instanceState))
elif cmd == "increase":
    api.NodeGroupIncreaseSize(pb.NodeGroupIncreaseSizeRequest(id=GROUP, delta=int(arg)))
elif cmd == "delete":
    api.NodeGroupDeleteNodes(pb.NodeGroupDeleteNodesRequest(
        id=GROUP, nodes=[pb.ExternalGrpcNode(name=arg, providerID=f"k3s://{arg}")]))
else:
    sys.exit(__doc__)
