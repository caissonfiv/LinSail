#!/bin/sh
# Standalone Linux x86_64 installer: no Python required.
set -eu
[ "$(uname -s)" = Linux ] || { echo '此安装包仅支持 Linux。' >&2; exit 1; }
[ "$(id -u)" != 0 ] || { echo '请以普通用户运行，不要使用 sudo。' >&2; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo '独立版目前支持 x86_64；其他架构请使用 install-python.sh。' >&2; exit 1; }
command -v bash >/dev/null 2>&1 || { echo '请先通过系统包管理器安装 Bash。' >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo '请安装 coreutils（需要 sha256sum 校验下载内容）。' >&2; exit 1; }
base=https://github.com/caissonfiv/LinSail/releases/download/v0.1.0a3
asset=linsail-linux-x86_64
local_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT HUP INT TERM
if [ -f "$local_dir/$asset" ] && [ -f "$local_dir/SHA256SUMS" ]; then
    cp "$local_dir/$asset" "$stage/$asset"
    cp "$local_dir/SHA256SUMS" "$stage/SHA256SUMS"
else
    download() {
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --silent --show-error --connect-timeout 20 --max-time 300 "$1" -o "$2"
        elif command -v wget >/dev/null 2>&1; then
            wget -q --timeout=60 -O "$2" "$1"
        else
            echo "没有 curl / wget。可在另一台电脑从 $base 下载 $asset、install.sh 和 SHA256SUMS，复制到同一目录后执行 sh install.sh；运行程序不需要下载工具。" >&2
            return 1
        fi
    }
    download "$base/$asset" "$stage/$asset"
    download "$base/SHA256SUMS" "$stage/SHA256SUMS"
fi
cd "$stage"
awk -v name="$asset" '$2 == name {print}' SHA256SUMS > selected.sha256
[ "$(wc -l < selected.sha256)" -eq 1 ] || { echo '缺少或重复的校验值，已取消安装。' >&2; exit 1; }
sha256sum --check selected.sha256
chmod 755 "$asset"
"$stage/$asset" install
