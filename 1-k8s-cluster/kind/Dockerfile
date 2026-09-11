FROM alpine:3.22

RUN apk add --no-cache \
    bash \
    curl \
    docker-cli \
    ca-certificates

ARG KIND_VERSION=v0.33.0
ARG KUBECTL_VERSION=v1.34.1
ARG HELM_VERSION=v3.18.6

RUN ARCH="$(uname -m)" && \
    case "$ARCH" in \
      x86_64) ARCH=amd64 ;; \
      aarch64) ARCH=arm64 ;; \
    esac && \
    curl -Lo /usr/local/bin/kind \
      "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${ARCH}" && \
    chmod +x /usr/local/bin/kind && \
    curl -Lo /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" && \
    chmod +x /usr/local/bin/kubectl && \
    curl -L \
      "https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz" \
      | tar xz && \
    mv "linux-${ARCH}/helm" /usr/local/bin/helm && \
    rm -rf "linux-${ARCH}"

WORKDIR /workspace

CMD ["bash"]
