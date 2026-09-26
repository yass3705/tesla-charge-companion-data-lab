#!/usr/bin/env bash
set -euo pipefail

# myAtlante 2.1.0 (Android versionCode 4519), pinned so the technical app
# configuration can be reproduced without a user-managed credential.
readonly VERSION_CODE="4519"
readonly XAPK_SHA256="d2d02ba197a6e39d7db212fff879e8ca1bb6f528c96887c0a551b29f4127301e"
readonly XAPK_URL="https://d.apkpure.net/b/XAPK/com.atlante.charging?versionCode=${VERSION_CODE}"

if [[ -n "${ATLANTE_API_SUBSCRIPTION_KEY:-}" ]]; then
  echo "::add-mask::${ATLANTE_API_SUBSCRIPTION_KEY}"
  echo "Using ATLANTE_API_SUBSCRIPTION_KEY supplied by the runtime."
  exit 0
fi

if [[ -z "${GITHUB_ENV:-}" ]]; then
  echo "GITHUB_ENV is required when the runtime key is absent." >&2
  exit 1
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

curl --fail --location --retry 3 --connect-timeout 20 --max-time 240 \
  --output "$workdir/myatlante.xapk" "$XAPK_URL"

actual_sha="$(sha256sum "$workdir/myatlante.xapk" | awk '{print $1}')"
if [[ "$actual_sha" != "$XAPK_SHA256" ]]; then
  echo "Pinned myAtlante XAPK checksum mismatch; refusing to inspect an unverified package." >&2
  exit 1
fi

unzip -p "$workdir/myatlante.xapk" com.atlante.charging.apk > "$workdir/base.apk"
unzip -p "$workdir/base.apk" assets/index.android.bundle > "$workdir/index.android.bundle"

python -m pip install --disable-pip-version-check --quiet "hermes-dec==0.1.7"
hbc-decompiler "$workdir/index.android.bundle" "$workdir/decompiled.js" >/dev/null

mapfile -t keys < <(
  sed -n "s/.*'API_SUBSCRIPTION_KEY': '\([^']*\)'.*/\1/p" "$workdir/decompiled.js" |
    awk 'NF && !seen[$0]++'
)
if [[ "${#keys[@]}" -ne 1 || "${#keys[0]}" -lt 16 ]]; then
  echo "Unable to recover exactly one technical API subscription key from the pinned app." >&2
  exit 1
fi

echo "::add-mask::${keys[0]}"
printf 'ATLANTE_API_SUBSCRIPTION_KEY=%s\n' "${keys[0]}" >> "$GITHUB_ENV"
echo "Recovered the technical Atlante API header from pinned myAtlante ${VERSION_CODE}."
