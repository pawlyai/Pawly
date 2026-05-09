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

### 5. Add API keys to GitHub repo secrets

Even though the runner has the VPS's `.env`, the workflows fetch keys via `${{ secrets.DEEPSEEK_API_KEY }}` etc. so they're auditable in workflow logs and can be rotated without re-deploying. Add them at:

**github.com/pawlyai/Pawly → Settings → Secrets and variables → Actions → New repository secret**

Required:
- `DEEPSEEK_API_KEY` — chat default
- `GOOGLE_API_KEY` — Gemini fallback + judge
- `OPENAI_API_KEY` — embedding model (used by some test fixtures)

### 6. Add `regression` label to the repo

For the full-223 workflow's label trigger:

**github.com/pawlyai/Pawly → Issues → Labels → New label** → name = `regression`, color = orange-ish.

### 7. Configure branch protection

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
