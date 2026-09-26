#!/usr/bin/env bash
# /srv/scoremate/prune.sh — 오래된 이미지 정리. 돌고 있는 버전과 되돌릴 만큼의 이전 버전만 남긴다.
# EarthThruTime3D prune.sh 동형. 이 서비스의 저장소 이름만 건드린다 — 호스트에 다른 서비스가 여럿이라 전역 prune 은 하지 않는다.
# Usage: KEEP=3 DRY_RUN=1 /srv/scoremate/prune.sh
set -euo pipefail
cd "$(dirname "$0")"
keep=${KEEP:-3}                 # 돌고 있는 것 포함 몇 개를 남기나
repository=honestjung/scoremateserver
dry_run=${DRY_RUN:-0}

[[ -f .env ]] || { echo 'No .env; nothing has been deployed here.' >&2; exit 1; }
current=$(sed -n 's/^IMAGE_TAG=//p' .env)
[[ -n "$current" ]] || { echo 'No IMAGE_TAG in .env.' >&2; exit 1; }

mapfile -t versions < <(docker images "$repository" --format '{{.Tag}}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -Vru || true)

survivors=("$current")
for version in "${versions[@]}"; do
    [[ "$version" == "$current" ]] && continue
    (( ${#survivors[@]} >= keep )) && break
    survivors+=("$version")
done
keeping=" ${survivors[*]} "
echo "Running $current; keeping${keeping% }."

removed=0
for version in "${versions[@]}"; do
    [[ "$keeping" == *" $version "* ]] && continue
    echo "removing $repository:$version"
    removed=$((removed + 1))
    (( dry_run )) && continue
    # 쓰는 중인 이미지는 지워지지 않는다 — 그게 안전망이다
    docker image rm "$repository:$version" >/dev/null 2>&1 || echo "  image in use or absent"
done
(( dry_run )) && echo "Dry run: $removed versions would be removed." || echo "Removed $removed versions."
