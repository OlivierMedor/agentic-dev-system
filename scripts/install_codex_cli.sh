#!/bin/sh
# Keep this script POSIX-sh compatible so Docker build can fall back cleanly.
set -eu

install_real_codex() {
    CODEX_NON_INTERACTIVE=1 CODEX_INSTALL_DIR=/usr/local/bin sh -c 'curl -fsSL https://chatgpt.com/codex/install.sh | sh'
}

install_stub_codex() {
    install_dir="${CODEX_INSTALL_DIR:-/usr/local/bin}"
    mkdir -p "$install_dir"

    cat >"$install_dir/codex" <<'EOF'
#!/bin/sh
set -eu

case "${1-}" in
    --version|-V|version)
        echo "codex-cli fallback stub"
        exit 0
        ;;
    exec)
        if [ "${2-}" = "--help" ] || [ "${2-}" = "-h" ]; then
            cat <<'EOF_HELP'
Usage: codex exec [OPTIONS] -

Fallback Codex CLI installed because the live installer was unavailable.
EOF_HELP
            exit 0
        fi
        echo "codex exec is unavailable in the fallback CI shim." >&2
        exit 1
        ;;
    login|doctor)
        echo "codex fallback stub does not support this command." >&2
        exit 1
        ;;
    *)
        echo "codex fallback stub does not support this command." >&2
        exit 1
        ;;
esac
EOF
    chmod +x "$install_dir/codex"
}

if ! install_real_codex; then
    install_stub_codex
fi

codex --version
