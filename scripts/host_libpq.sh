# Source this (`. scripts/host_libpq.sh`) before any host-side Python that opens Supabase/PostgreSQL (pytest, probes, workers).
# 2026-10-07 16:21 (A105): Windows Smart App Control (policy {0283ac0f-fff1-49ae-ada1-8a933130cad6}, CI event 3077) started blocking
# the unsigned libpq/libssl DLLs bundled in psycopg_binary (.venv314/Lib/site-packages/psycopg_binary.libs). psycopg then falls back
# to its pure-Python wrapper, which only needs a *signed* libpq.dll on PATH — LibreOffice ships one (Authenticode valid).
# Point LIBPQ_DIR at another signed copy if LibreOffice is not installed. Nothing in the product changes; only the host loads a
# different libpq. Turning Smart App Control off is the user's call (one-way switch) — see HANDOFF A105.
LIBPQ_DIR="${LIBPQ_DIR:-/c/Program Files/LibreOffice/program}"
if [ -f "$LIBPQ_DIR/libpq.dll" ]; then
  case ":$PATH:" in *":$LIBPQ_DIR:"*) ;; *) export PATH="$LIBPQ_DIR:$PATH";; esac
fi
