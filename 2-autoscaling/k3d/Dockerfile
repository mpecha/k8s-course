FROM alpine:3.22

RUN apk add --no-cache \
    bash \
    curl \
    docker-cli \
    ca-certificates \
    python3

ARG K3D_VERSION=v5.8.3
ARG KUBECTL_VERSION=v1.34.1
ARG HELM_VERSION=v3.18.6

RUN ARCH="$(uname -m)" && \
    case "$ARCH" in \
      x86_64) ARCH=amd64 ;; \
      aarch64) ARCH=arm64 ;; \
    esac && \
    curl -Lo /usr/local/bin/k3d \
      "https://github.com/k3d-io/k3d/releases/download/${K3D_VERSION}/k3d-linux-${ARCH}" && \
    chmod +x /usr/local/bin/k3d && \
    curl -Lo /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" && \
    chmod +x /usr/local/bin/kubectl && \
    curl -L \
      "https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" \
      | tar xz && \
    mv "linux-${ARCH}/helm" /usr/local/bin/helm && \
    rm -rf "linux-${ARCH}"

# gRPC runtime for the provider, and Python stubs generated from the proto
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir grpcio grpcio-tools

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/opt/stubs \
    PYTHONUNBUFFERED=1

COPY provider/externalgrpc.proto /opt/stubs/
RUN python3 -m grpc_tools.protoc -I /opt/stubs \
      --python_out=/opt/stubs --grpc_python_out=/opt/stubs \
      /opt/stubs/externalgrpc.proto

WORKDIR /workspace

CMD ["bash"]
