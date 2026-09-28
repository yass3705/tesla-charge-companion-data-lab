#!/usr/bin/env bash
set -u
mkdir -p reports/belgium/totalenergies
OUT=reports/belgium/totalenergies/bemo-host-diag-2026-09-28.txt
{
  echo "=== DNS ==="
  getent ahosts map.be-mo.io || true
  command -v dig >/dev/null && dig +short map.be-mo.io CNAME && dig +short map.be-mo.io A || true
  echo
  echo "=== TLS CERT ==="
  timeout 20 openssl s_client -connect map.be-mo.io:443 -servername map.be-mo.io </dev/null 2>/dev/null |
    openssl x509 -noout -subject -issuer -ext subjectAltName 2>/dev/null || true
  echo
  echo "=== CURL VERBOSE HEAD ==="
  curl -vkI --connect-timeout 15 --max-time 30 https://map.be-mo.io/ 2>&1 | tail -120 || true
  echo
  echo "=== CURL INSECURE BODY HEAD ==="
  curl -kLsS --connect-timeout 15 --max-time 30 -D - https://map.be-mo.io/ | head -120 || true
} > "$OUT"
cat "$OUT"
