# LinSail · 启航

A small Linux terminal agent for natural-language setup and a persistent human-operated shell.

**0.1.0a1 — Alpha.** Requires Linux, Python 3.10+, Bash and an interactive terminal. No third-party runtime dependencies. The CLI currently uses Chinese labels; prompts and model responses can use other languages.

Download `linsail.pyz`, `install.sh` and `SHA256SUMS` from the same GitHub pre-release:

```bash
python3 linsail.pyz configure
python3 linsail.pyz
# Optional user-local installation:
sh install.sh
```

Configure a tool-capable Chat Completions endpoint and your model ID. Enter your own API key at startup or supply it through the configured environment variable. Hosted provider profiles use the same protocol; LinSail's paid hosted service is not launched yet.

Every AI command requires explicit approval. `/shell` opens the same persistent Bash session. `Ctrl+]` hands execution to you, or returns from manual mode after interrupting the foreground job. Directories and exported variables persist. Manual terminal output is not automatically shared with the model. Approved automated command output is shared with the selected endpoint. `sudo` passwords are typed locally.

Run as an ordinary user, including over SSH with a TTY. This is not a sandbox, and commands run with your account's permissions. Full-screen terminal programs should be used in manual mode. Root startup is disabled. The shell does not source user rc files.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 dist/linsail.pyz --terminal
```

See the [Chinese guide](README.md), [security boundaries](SECURITY.md), [architecture](docs/ARCHITECTURE.md) and [hosted service plan](docs/HOSTED_MODELS.md). MIT licensed.
