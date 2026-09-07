#!/bin/sh
# Selected fields only: never serialize Config.Env or credentials.
set -eu
mode=$1
project=$2
storage=$3
ids=$(docker ps -aq --filter "label=com.docker.compose.project=$project")
test -n "$ids"
# Docker IDs contain only hexadecimal characters; word splitting is intentional.
docker inspect --format '{"service":{{json (index .Config.Labels "com.docker.compose.service")}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"memory":{{.HostConfig.Memory}},"nano_cpus":{{.HostConfig.NanoCpus}},"logs":{{json .HostConfig.LogConfig}},"readonly":{{.HostConfig.ReadonlyRootfs}},"user":{{json .Config.User}},"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}},"oom":{{.State.OOMKilled}},"restarts":{{.RestartCount}},"status":{{json .State.Status}},"exit_code":{{.State.ExitCode}}}' $ids | docker compose -p "$project" -f compose.yaml -f "compose.$mode.yaml" exec -T api python /checks/verify_runtime_contract.py "$mode" "$project" "$storage"
docker stats --no-stream --format '{{.Name}} {{.MemUsage}} {{.CPUPerc}}' $ids
