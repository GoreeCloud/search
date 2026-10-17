#!/usr/bin/env python3
"""Ephemeral Docker topology proof for PRIVATE Search staging.

The GitHub-hosted runner is disposable. The synthetic provider, gateway and
visitor exchange only a fixed marker, never a real search query or credentials.
Tests do not use production Docker networks, external services, or public ports.
The gateway here is a SMALL TEST FIXTURE, not the real GoreeCloud SOCKS server.
This does NOT attest actual provider-visible public IP or firewall enforcement
for a future Search hosting environment.
"""
import errno
import json
import os
import re
import subprocess
import sys
import time
import uuid

IMAGE = "python:3.12-alpine"
MARKER = "gc-synthetic-topology-v1"

PROVIDER = """
import json,socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('0.0.0.0',18443));s.listen(8);s.settimeout(35)
while True:
 c,addr=s.accept()
 try:
  c.settimeout(4)
  received=c.recv(128).decode('ascii','replace')
  c.sendall((json.dumps({'peer':addr[0],'accepted':received=='gc-synthetic-topology-v1'})+'\\n').encode())
 finally:
  c.close()
"""
GATEWAY = """
import socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('0.0.0.0',19050));s.listen(8);s.settimeout(35)
while True:
 c,addr=s.accept()
 try:
  c.settimeout(4)
  data=c.recv(128)
  if data!=b'gc-synthetic-topology-v1':
   c.sendall(b'REJECTED\\n');continue
  with socket.create_connection(('fixture-provider',18443),timeout=4) as upstream:
   upstream.sendall(b'gc-synthetic-topology-v1')
   c.sendall(upstream.recv(512))
 finally:
  c.close()
"""
CLIENT = """
import json,os,socket,sys,time
provider=os.environ['PROVIDER_IP'];visitor=socket.gethostbyname(socket.gethostname())
egress=os.environ['GATEWAY_EGRESS_IP']
def refused(address,port):
 try:
  with socket.create_connection((address,port),timeout=1):return False
 except OSError as exc:
  return exc.errno in (101,113,100,1,13)

assert refused(provider,18443),'visitor reached provider directly'
assert refused('169.254.169.254',80),'visitor reached metadata directly'
assert refused('1.1.1.1',443),'visitor reached public IP directly'
for i in range(25):
 try:
  with socket.create_connection(('fixture-gateway',19050),timeout=2) as s:
   s.sendall(b'gc-synthetic-topology-v1')
   result=json.loads(s.recv(512).decode())
  break
 except OSError:
  time.sleep(.25)
else:raise AssertionError('gateway unavailable')
assert result['accepted'] is True
assert result['peer']==egress,(result['peer'],egress)
assert result['peer']!=visitor,'provider saw visitor network address'
print(json.dumps({'synthetic_provider_through_gateway':'PASS',
 'visitor_direct_provider_denied':True,'visitor_public_egress_denied':True,
 'visitor_metadata_denied':True,'provider_peer_was_gateway':True,
 'public_provider_ip_masking_qualified':False,'host_firewall_qualified':False}))
"""


def docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=95,
    )
    return result.stdout.strip()


def inspect_network_ip(container: str, network: str) -> str:
    data = json.loads(docker("inspect", container))
    return data[0]["NetworkSettings"]["Networks"][network]["IPAddress"]


def run() -> None:
    suffix = re.sub(r"[^a-z0-9]", "", os.environ.get("GITHUB_RUN_ID", "local").lower())[-10:]
    ident = suffix + "-" + uuid.uuid4().hex[:6]
    private_network = "gc-search-ci-private-" + ident
    egress_network = "gc-search-ci-egress-" + ident
    names = ("gc-search-ci-visitor-" + ident, "fixture-gateway", "fixture-provider")
    # The two fixed names are only used in this disposable runner's namespace.
    # CI job is serialized; a unique visitor and networks prevent overlap.
    created_networks: list[str] = []
    containers: list[str] = []
    try:
        docker("network", "create", "--driver", "bridge", "--internal",
               "--label", "goreecloud.scope=disposable-search-ci",
               private_network)
        created_networks.append(private_network)
        docker("network", "create", "--driver", "bridge",
               "--label", "goreecloud.scope=disposable-search-ci",
               egress_network)
        created_networks.append(egress_network)
        provider = names[2]
        gateway = names[1]
        # No public ports, host network, production mounts, env secrets or privileges.
        common = ("--read-only", "--cap-drop", "ALL", "--security-opt",
                  "no-new-privileges", "--pids-limit", "32",
                  "--memory", "96m", "--cpus", "0.25", "--user", "65534:65534")
        docker("run", "-d", "--name", provider, "--network", egress_network,
               "--network-alias", "fixture-provider",
               *common, IMAGE, "python", "-u", "-c", PROVIDER)
        containers.append(provider)
        docker("run", "-d", "--name", gateway, "--network", private_network,
               "--network-alias", "fixture-gateway",
               *common, IMAGE, "python", "-u", "-c", GATEWAY)
        containers.append(gateway)
        docker("network", "connect", egress_network, gateway)
        provider_ip = inspect_network_ip(provider, egress_network)
        gateway_egress_ip = inspect_network_ip(gateway, egress_network)
        # The visitor only joins the internal bridge.
        visitor = names[0]
        outcome = docker("run", "--rm", "--name", visitor, "--network", private_network,
                         *common, "-e", "PROVIDER_IP=" + provider_ip,
                         "-e", "GATEWAY_EGRESS_IP=" + gateway_egress_ip,
                         IMAGE, "python", "-u", "-c", CLIENT)
        print(outcome, flush=True)
        print("EPHEMERAL_NETWORK_TOPOLOGY_PASS", flush=True)
        print("NOT_QUALIFIED: public provider IP, production firewall, hosted Search, DNS rebinding", flush=True)
    finally:
        for container in reversed(containers):
            subprocess.run(["docker", "rm", "-f", container],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=20)
        for network in reversed(created_networks):
            subprocess.run(["docker", "network", "rm", network],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=20)


if __name__ == "__main__":
    try:
        run()
    except (KeyError, ValueError, subprocess.SubprocessError, OSError, AssertionError) as exc:
        print("EPHEMERAL_NETWORK_TOPOLOGY_FAILED:", type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None
