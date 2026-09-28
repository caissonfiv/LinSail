# LinSail · 启航

A small Linux terminal agent for natural-language setup and a persistent human-operated shell.

**0.1.0a4 — Alpha.** The Linux x86_64 / ARM64 executables bundles Python. Runtime requires glibc 2.35+, Bash, system CA certificates and a TTY; Python, pip and curl are not required. Download `linsail-linux-x86_64` from Releases:

```sh
chmod +x linsail-linux-x86_64
./linsail-linux-x86_64 install
export PATH="$HOME/.local/bin:$PATH"
linsail
```

First launch guides model setup. The installer adds PATH for Bash/Zsh/Fish and backs up existing startup files. With the executable, `install.sh` and `SHA256SUMS` in one folder, `sh install.sh` verifies and installs offline. Online installation uses either curl or wget. Without either tool, copy the release files from another computer. Keep the release's third-party notices when redistributing.

Use `linsail-linux-arm64` on ARM64. These builds do not target 32-bit ARM, Alpine/musl or Windows. Its temporary directory must allow execution. `linsail.pyz` and `install-python.sh` remain available for systems with Python 3.10+. The Python installer can offer to install missing dependencies with apt-get/dnf and sudo; set `LINSAIL_INSTALL_DEPS=0` to forbid package changes.

Configure a tool-capable Chat Completions endpoint and your model ID. Enter your own API key at startup or supply it through the configured environment variable. Hosted provider profiles use the same protocol; LinSail's paid hosted service is not launched yet.

Every AI command requires explicit approval. `/shell` opens the same persistent Bash session. `Ctrl+]` hands execution to you, or returns from manual mode after interrupting the foreground job. Directories and exported variables persist. Manual terminal output is not automatically shared with the model. Approved automated command output is shared with the selected endpoint. `sudo` passwords are typed locally.

Run as an ordinary user, including over SSH with a TTY. This is not a sandbox, and commands run with your account's permissions. Full-screen terminal programs should be used in manual mode. Root startup is disabled. The shell does not source user rc files.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 dist/linsail.pyz --terminal
```

See the [Chinese guide](README.md), [security boundaries](SECURITY.md), [architecture](docs/ARCHITECTURE.md) and [hosted service plan](docs/HOSTED_MODELS.md). MIT licensed.

## Maintenance

Install once with the a4 installer to register the executable. Use `linsail update --check`, `linsail update`, `linsail update --to 0.1.0a4`, `linsail rollback`, or `linsail uninstall`. Alpha installations follow the alpha channel by default; stable installations follow stable. There are no background updates.

Updates validate the SHA256 and run the candidate version check before replacing the program. One prior version is kept; normal write failures attempt restoration. Power loss and forced termination are not transactionally protected. Uninstallation preserves model configuration and shell backups, and removes only unchanged managed PATH blocks. It leaves the small concurrency lock file. Package-manager installations are not managed by these commands.
