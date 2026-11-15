# Full-stack delivery (WS4, R01–R04/S03)

Public deployment verified 2026-11-15: **https://errante.34-148-242-13.sslip.io**.
Project `project-4c470287-a034-43da-bf6`, VM `errante`, zone `us-east1-b`, reserved IP `34.148.242.13`.
Initial application release: `642ea686ce54a1460d6e2d7e6c102bc8b99c8540` (includes WS5 light-curve panel #83).
See [production.json](production.json) for acceptance evidence and limitations. The sslip.io hostname is
temporary third-party DNS; it can be replaced by an owned domain without moving the VM or state.

The image serves the existing frontend, API, real PNGs and precomputed light curves on one origin.
Jobs are enabled. Five real fields and WS1 search snapshots are bundled; a fresh runtime volume is
seeded once. Existing manifests and jobs are preserved on restart. Runtime products and private
cache/SQLite live in separate directories in the `runtime` named volume, outside source/seed data.
The image runs as UID 10001. One application instance owns SQLite and the worker; do not scale replicas.

From the repository root:

```bash
docker compose -f backend/deploy/compose.yaml up --build -d app
python scripts/smoke_delivery.py http://localhost:8000
python scripts/smoke_delivery.py http://localhost:8000 --live-job
```

Open `http://localhost:8000`. The last command performs a real coordinate build and verifies served PNGs.
An archive outage may use a dated, explicitly stale WS1 snapshot. It is not proof of fresh coverage or R05
scientific validation. CI verifies the shipped frontend, real fields/PNGs, jobs enabled and light curves
without depending on live archives. The offline regression suite also covers interrupted seeding, restart
preservation and SPA routing without hiding missing API/data/assets behind HTML.

## Chosen deployment shape: one Google Compute Engine VM

Use a single Linux VM with 2 vCPU, 8 GiB RAM and a 30 GiB or larger durable disk as an initial configuration,
then measure resources. This supports local SQLite/WAL, the background worker and persistent generated PNGs.
The supplied Compose caps application CPU/RAM/processes and keeps port 8000 on loopback. Optional Caddy
exposes HTTP/HTTPS and persists certificates. Point an available domain (including the GoDaddy offer if
claimed) to the VM's reserved public IP. Azure VM with the same resources is also compatible.

The participant offer does not establish a credit amount, billing status or VM availability. Account/project,
credits and billing must be verified by the team before creating resources. This repository does not create
resources or activate billing automatically. VM, IP, disk and egress may incur charges; check the account's
estimate/budget. Cloud Run's ephemeral in-memory filesystem and autoscaling need a different persistence
design for this SQLite worker; do not mount a Cloud Storage bucket as its database.

The user confirmed a fresh USD 300 / 90-day trial; this project's billing link was verified before deployment.
A **USD 20 monthly usage alert** is configured at 50%, 90% and 100%, excluding credits from the calculation
so promotional credits do not hide consumption. It is a notification, not a spending cap or shutdown rule.
Base estimate for the chosen VM + 30 GiB balanced disk + in-use IPv4 is about USD 56/month, excluding
traffic/taxes and subject to the account's actual prices. No paid-account upgrade or commitment was made.

## Redeploy as a teammate

Each operator uses their own Google account with project access and their own Git checkout. No shared
password, SSH private key, service-account JSON or access token is needed. Google Cloud Console's browser
SSH is also available on the VM page. For CLI use, install Google Cloud CLI (or use Cloud Shell), then:

```bash
gcloud auth login
git fetch origin
python scripts/deploy_vm.py --ref origin/main
python scripts/smoke_delivery.py https://errante.34-148-242-13.sslip.io --live-job
```

Deploy changes after merging their PR. The helper archives committed files only, uploads with `gcloud
compute scp`, and uses SSH/sudo on the existing VM. A server-side lock serializes team deployments; releases
are stored under `/opt/errante/releases/<commit>`. All releases use Compose project `errante`, preserving
runtime and HTTPS volumes. The latest helper-deployed revision is recorded in `/opt/errante/current-revision`.
The helper does not create VMs, change billing or destroy/prune volumes. Optional flags override project,
zone, instance, domain and the gcloud path. If Windows batch wrappers fail, it uses the SDK Python entry point.

Inspect or restart from Cloud Shell/your authenticated terminal:

```bash
gcloud compute ssh errante --project project-4c470287-a034-43da-bf6 --zone us-east1-b
sudo docker ps
sudo docker logs --tail 80 errante-app-1
sudo docker restart errante-app-1
```

The initial VM was created without a service account: the app only needs public astronomy services.
Operators' SSH access uses their own IAM-authorized keys. The bootstrap script is tracked at
`backend/deploy/google-startup.sh`; pass it as startup metadata when recreating the VM.

Once the team has an authenticated Google Cloud project and has accepted its resource estimate, these are
the concrete creation parameters (replace `PROJECT_ID`; commands create chargeable resources):

```bash
gcloud compute addresses create errante-ip --project PROJECT_ID --region us-east1
gcloud compute instances create errante --project PROJECT_ID --zone us-east1-b \
  --machine-type e2-standard-2 --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
  --boot-disk-size 30GB --boot-disk-type pd-balanced --no-boot-disk-auto-delete \
  --address RESERVED_IP --tags errante-web --no-service-account --no-scopes \
  --metadata-from-file startup-script=backend/deploy/google-startup.sh
gcloud compute firewall-rules create errante-web --project PROJECT_ID --network default \
  --allow tcp:80,tcp:443 --target-tags errante-web
```

Install Docker Engine and its Compose plugin on the VM using the official Ubuntu instructions below.
Upload a tracked release archive (`git archive --format=tar.gz -o errante-release.tar.gz HEAD`) rather than
copying a developer workspace with credentials/downloads. Extract it in a release directory, then:

```bash
export ERRANTE_DOMAIN=your-actual-domain.example
docker compose -p errante -f backend/deploy/compose.yaml --profile https up --build -d
python3 scripts/smoke_delivery.py https://your-actual-domain.example --live-job
```

Keep `-p errante` and the same Docker host on upgrades so named volumes persist. `docker compose down`
preserves volumes; `down -v` destroys state. Stop the application before backing up its volume/SQLite.
Keep the boot disk when deleting/replacing a VM and restore volumes before starting the replacement.
Allow outbound HTTPS to IRSA/S3/catalogs and inbound 80/443. Caddy obtains HTTPS after DNS points to the VM.
Verify all five targets and the coordinate flow from the public URL, in an incognito browser and a phone.
Public HTTPS/API acceptance is recorded in production.json. Edge rendered all five targets at desktop and
mobile viewport sizes; the mobile screenshot showed horizontal overflow in the existing WS5 layout. This
is not full mobile usability certification: WS5 should fix that layout and the team should review on a phone.

## Cross-origin embedding: WS4 handoff for V19/C06

The public full-stack origin supports being loaded inside an iframe on another origin. The embedded
document still makes API/image requests to its own application origin; embedding alone needs no extra
CORS origin entry. The existing deployment does not impose a frame-blocking policy.

```html
<iframe src="https://errante.34-148-242-13.sslip.io/#/field/barnards-star"
        title="Errante SPHEREx sequence" width="100%" height="1050"></iframe>
```

Repeat the browser acceptance from a separate local HTTP parent (optional developer dependency):

```bash
python -m pip install playwright
python scripts/smoke_embed.py https://errante.34-148-242-13.sslip.io --out-dir data/cache/embed-check
# Explicitly submit a real coordinate job through the iframe UI:
python scripts/smoke_embed.py https://errante.34-148-242-13.sslip.io --live-job --out-dir data/cache/embed-job
```

The script defaults to installed Edge; `--browser-path` accepts another Chromium executable. It checks
40 image loads and frame stepping. `--live-job` checks submission/polling/result display from inside the
frame; `--job-id ID` resumes a saved job, including after a redeploy. Screenshots/JSON are saved only in
the requested output directory. The parent server and browser are closed after the check.

**WS4 delivery is ready; WS5's compact view is still separate.** The current field URL embeds the full
application. WS5 should add the compact URL/layout, retain date/mission/provenance and synthetic labels,
and then run this check against that view. No `embed` parameter or automatic cross-origin `postMessage`
control API is claimed here. R05 human review is not established by this technical acceptance.

## GitHub administration handoff

At the 2026-11-15 check, `rpccp` has push access but `admin: false`; the repo is private and Pages is disabled.
The owner must verify `Settings → Rules → Rulesets` (or branch protection): PRs required, `python` and
`frontend` checks required, one independent approval if the team adopts WS4-1, and no force-push/deletion.
For Pages, enable GitHub Actions as source and `ENABLE_PAGES=true`; the workflow now defaults to `real`.
Private-repository Pages availability depends on the repository plan. For separate web/API hosting, set
`VITE_DATA_MODE=api`, `VITE_API_BASE` to the public API origin and restrict `ERRANTE_CORS_ORIGINS` to the web origin.
The one-origin image does not need Pages, a repository visibility change or a separate frontend host.
Team membership, assignment of WS5/WS6 and scientific review must be confirmed by the people responsible;
deployment code cannot complete those human decisions.

Primary references checked 2026-11-15: [durable disks](https://docs.cloud.google.com/compute/docs/disks),
[VM creation](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create),
[Cloud Run runtime](https://docs.cloud.google.com/run/docs/container-contract),
[Google Cloud free-program conditions](https://docs.cloud.google.com/free/docs/free-cloud-features),
[Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
