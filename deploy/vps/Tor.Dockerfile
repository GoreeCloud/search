# Private SOCKS5H gateway sharing a network namespace with GoreeCloud Search.
FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends tor ca-certificates \
    && rm -rf /var/lib/apt/lists/*
USER debian-tor
CMD ["tor", "--RunAsDaemon", "0", "--ClientOnly", "1", "--SocksPort", "127.0.0.1:9050", "--DataDirectory", "/tmp/goreecloud-search-tor", "--Log", "notice stdout"]
