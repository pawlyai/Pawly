# GitHub Actions self-hosted runner — Pawly VPS

The regression workflows (`regression-light.yml`, `regression-full.yml`)
are pinned to `runs-on: [self-hosted, pawly-vps]`, meaning they execute
on a runner installed on our deploy VPS rather than GitHub-hosted cloud
runners. This doc gets you from "no runner" to "PR triggers actually fire".

## Why self-hosted

- Reuse the VPS's existing `.env` (DEEPSEEK / GOOGLE / OPENAI keys), no need to mirror to GitHub Secrets and worry about rotation drift.
- Reuse the VPS's running Postgres / Redis containers — agent envs would have to bring those up from scratch.
- 223-case regression takes 1-3 hours; GitHub-hosted runner has a 6-hour limit and you pay per minute over the free tier.
- The VPS is already on 24/7 for the deployed services. Idle CPU is free.

Cost: zero extra. Risk: a malicious PR could exec arbitrary code on the VPS via the workflow. **Mitigation: only use self-hosted runners on private repos with trusted committers** (which is our case — `pawlyai/Pawly` is private, only @huihuicaigogogo + Atlas push).

## One-time setup (do this once on the VPS)

### 0. Install build prerequisites

`make` and `python3-venv` are required by the regression Makefile targets.
On a fresh Ubuntu/Debian VPS:

```bash
sudo apt update
sudo apt install -y make python3 python3-venv
```

(Ubuntu 24.04+ also enforces PEP 668, which is why `make install` uses a
project-local `.venv/` instead of pip-installing into the system Python.)

### 1. Create the runner directory

```bash
sudo mkdir -p /opt/actions-runner
sudo chown $(whoami):$(whoami) /opt/actions-runner
cd /opt/actions-runner
```

### 2. Download GitHub's runner agent

Go to **github.com/pawlyai/Pawly → Settings → Actions → Runners → New self-hosted runner → Linux x64**. Copy the download + config commands GitHub generates (they include a registration token that expires in ~1h).

```bash
# Example — use the exact URL/version from the GitHub UI
curl -O -L https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz
tar xzf ./actions-runner-linux-x64-2.319.1.tar.gz
```

### 3. Register the runner

```bash
./config.sh \
    --url https://github.com/pawlyai/Pawly \
    --token <FROM-GITHUB-UI> \
    --name pawly-vps-1 \
    --labels self-hosted,pawly-vps \
    --work _work \
    --unattended \
    --replace
```

The `--labels self-hosted,pawly-vps` is critical — workflow files reference `runs-on: [self-hosted, pawly-vps]`.

### 4. Run as a systemd service (so it survives reboots)

```bash
sudo ./svc.sh install $(whoami)
sudo ./svc.sh start
sudo ./svc.sh status        # should be "active (running)"
```

### 5. Verify `/opt/pawly/.env` is readable by the runner

The workflows source `/opt/pawly/.env` at run-time and pull `DEEPSEEK_API_KEY` / `GOOGLE_API_KEY` / `OPENAI_API_KEY` from it. **Keys are NOT stored in GitHub Secrets** — they live only on the VPS, so a compromised GitHub account can't exfiltrate them.

This means the runner's Linux user needs read access to `/opt/pawly/.env`. Check:

```bash
# Run as the same user the runner runs as (whoami inside the runner service)
cat /opt/pawly/.env | head -1
# Should print the first line of the env file. If "permission denied":
sudo chmod 644 /opt/pawly/.env       # readable by anyone on the VPS
# Or, more locked-down:
sudo chown root:runner-group /opt/pawly/.env
sudo chmod 640 /opt/pawly/.env
sudo usermod -aG runner-group $(whoami)
```

The workflows fail-loud if `/opt/pawly/.env` is missing or the required keys aren't in it, so you'll see the error immediately on the first PR run.

**Tradeoff vs. GitHub Secrets**: this approach loses the GitHub UI audit log of "who used the key when" and locks the workflow to this specific machine. For a single-VPS personal project that's a fine trade — keys never leave the box, no GitHub-side breach can leak them, no rotation drift. If you ever scale to multiple runners or hosted GitHub-cloud runners, you'll want to migrate to `${{ secrets.* }}` instead and re-add the secrets via the UI.

### 6. Add labels to the repo

Both regression workflows are opt-in via PR labels — by default a PR runs
nothing. Create both at **github.com/pawlyai/Pawly → Issues → Labels → New label**:

| Label | Suggested color | Purpose |
|---|---|---|
| `lite-regression` | red `#de053d` | Triggers `regression-light.yml` (30 cases, ~20 min, ~$2). Re-runs on every new commit while the label is present. |
| `full-regression` | dark red `#a01030` | Triggers `regression-full.yml` (223 cases, 1–3 hours, ~$50). Fires only on label-add (not on subsequent commits) — to re-run, remove and re-add the label. |

Color is purely cosmetic; the workflows match by exact label name. Use
visually-distinct colors so a glance at the PR list shows what's being
spent where.

**Important**: there is **no required status check** for either label. A
PR can merge without running regression — the labels are author-driven
opt-in, not gating. If the change warrants regression (touches prompts /
models / orchestrator / scoring), the author is responsible for adding
the label. See `docs/regression-runbook.md` for the decision matrix.

### 7. Create the regression cache directory

The CI workflows persist baseline + per-tree report cache here. It lives
*outside* the runner workdir so that `actions/checkout`'s `git clean` can't
wipe it between runs. Without this dir the workflows still work — they
just behave as if every run is the first, so every PR gets a "first run"
summary instead of a real diff.

```bash
sudo mkdir -p /opt/pawly/regression-cache/reports-light-30
sudo chown -R $(whoami) /opt/pawly/regression-cache
# Verify the runner user can write to it:
touch /opt/pawly/regression-cache/.write-test && rm /opt/pawly/regression-cache/.write-test
```

What ends up in here over time:

```
/opt/pawly/regression-cache/
├── baseline-light-30.json                          ← what every PR's diff compares against
└── reports-light-30/
    └── deepseek-v4-pro/
        ├── <tree-sha-1>.json                       ← report from PR whose HEAD tree was sha-1
        ├── <tree-sha-2>.json
        └── ...
```

The per-tree cache lets `refresh-baseline` short-circuit on push-to-main
when the merge commit's tree matches one we already ran (common for squash
merges where main hadn't moved). Without the cache, every push-to-main
re-runs light-30, double-billing every merge.

**Pruning** (do this every 2-3 months):

```bash
# Drop tree-SHA cache entries older than 90 days. baseline-light-30.json
# is overwritten in place on each refresh, so it doesn't need pruning.
find /opt/pawly/regression-cache/reports-light-30 -name '*.json' -mtime +90 -delete
```

### 8. Configure branch protection

So the PR can't merge with red regression-light:

**github.com/pawlyai/Pawly → Settings → Branches → main → Edit → Protect matching branches → Require status checks to pass before merging** → search for `light-30 / blackbox-multiturn` and add it.

(Optional but recommended: also tick "Require linear history" and "Require pull request reviews".)

## Verifying the runner is alive

```bash
# On the VPS
sudo systemctl status actions.runner.pawlyai-Pawly.pawly-vps-1.service

# In GitHub UI
# Settings → Actions → Runners → should show "Idle" with green dot
```

## What gets run

```
~/_work/Pawly/Pawly/   ← runner clones the PR commit here
                        each workflow run starts from a clean checkout
                        (the runner persists between runs, but the workdir
                        is wiped at the start of each job)
```

The workflow installs deps via `make install` (fresh pip install each run — slow but predictable). Reports get written under `~/_work/Pawly/Pawly/tests/blackbox_multiturn/results/` and uploaded as workflow artifacts.

## Common problems

**Runner shows "Offline" in GitHub UI**

```bash
sudo systemctl restart actions.runner.pawlyai-Pawly.pawly-vps-1.service
sudo journalctl -u actions.runner.pawlyai-Pawly.pawly-vps-1.service -n 50
```

If logs show auth failures, the runner registration may have expired (rare). Re-run `config.sh remove` then `config.sh` with a fresh token.

**Workflow stuck in "Queued"**

GitHub is looking for a runner with both `self-hosted` AND `pawly-vps` labels and finding none. Check the runner has both labels in the GitHub UI; re-register if missing.

**Disk full mid-run**

Reports + logs + checked-out repos accumulate under `~/_work/`. Clean periodically:

```bash
# On the VPS
du -sh ~/_work/Pawly/Pawly/tests/blackbox_multiturn/results/
# If huge, archive then prune:
tar czf /backup/regression-reports-$(date +%Y%m).tar.gz tests/blackbox_multiturn/results/
find ~/_work/Pawly/Pawly/tests/blackbox_multiturn/results/ -name '*.json' -mtime +30 -delete
```

**Workflow times out at 45/240 min**

Light-30 should never need >45min on this VPS; full-223 should fit in 240min. If you're hitting the limit, suspect:

1. DeepSeek / Gemini rate limits (429 retries blow up wall time)
2. Postgres container restarting mid-run
3. A test case in an infinite turn loop (look at the run's `.jsonl` log under `logs/`)

## Decommissioning the runner

```bash
cd /opt/actions-runner
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token <FROM-GITHUB-UI>
```

Then unregister in the GitHub UI.

## Trust model recap

Self-hosted runners on private repos are safe **as long as**:

1. Only trusted contributors can open PRs (private repo + branch protection).
2. The workflow YAML doesn't run untrusted code from the PR (e.g. `pip install` is OK because it's pinned to the dependency in the PR; `bash <(curl untrusted-url)` would NOT be OK).
3. Secrets are scoped: the regression workflows get LLM API keys, NOT SSH keys, NOT DB write creds.

Re-audit if the repo goes public or external contributors get push access.
