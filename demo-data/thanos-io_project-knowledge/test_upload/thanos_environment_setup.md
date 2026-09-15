# Thanos Development Environment Setup

- **Project:** Thanos (`thanos-io/thanos`)
- **Ralion category:** Environment setup
- **Audience:** Engineers contributing to or debugging the Thanos codebase
- **Source baseline:** `main` branch, reviewed 2026-08-24
- **Purpose:** Get a new engineer from a clean workstation to a reproducible local build, test run, and development loop.

> This document is an onboarding guide, not an alternative build system. When this guide and the repository disagree, the checked-out repository (`go.mod`, `Makefile`, scripts, and CI configuration) is authoritative.

## 1. What you should have working at the end

A successful setup means you can:

1. clone your fork and track `thanos-io/thanos` as `upstream`;
2. build the `thanos` binary from source;
3. run local unit tests without cloud object-store credentials;
4. run formatting and lint checks relevant to a pull request;
5. optionally start the repository quickstart or Docker-based end-to-end tests;
6. find the generated binary and invoke `thanos --help`.

For normal backend work, you do **not** need production credentials or access to a real object-storage account.

## 2. Supported development environment

The upstream contribution guide recommends Linux or macOS. Windows development is possible through WSL 2. If you run a local Kubernetes cluster under WSL 2, be aware of the documented `ClientIP` session-affinity limitation around the `xt_recent` kernel module.

### Required tools

| Tool | When required | Notes |
|---|---|---|
| Git | Always | Used by the Makefile and contribution workflow. |
| Go | Always | The current `main` branch declares **Go 1.26.0** in `go.mod`. Use the version required by your checked-out revision. |
| GNU Make | Always | The repository exposes the normal development workflow through `make` targets. |
| Docker | E2E tests / container builds | Required for Docker-based E2E tests. |
| Node.js + pnpm | React UI work and the full `make lint` target | `make lint` includes React linting; React sources live under `pkg/ui/react-app`. |

The upstream `CONTRIBUTING.md` currently says Go 1.22.x or higher, but `go.mod` on `main` requires Go 1.26.0. For reproducibility, treat `go.mod` as the version constraint for the revision you are building.

## 3. Clone the repository

For a contribution, the normal workflow is to fork the repository first and keep the canonical repository as `upstream`.

```bash
mkdir -p ~/Repos
cd ~/Repos

git clone https://github.com/<your-github-id>/thanos.git
cd thanos

git remote add upstream https://github.com/thanos-io/thanos.git
git remote -v
```

If you only need a read-only local checkout, cloning `https://github.com/thanos-io/thanos.git` directly is sufficient.

Before starting new work, update from upstream:

```bash
git checkout main
git fetch upstream
git rebase upstream/main
```

Create a focused branch for the change:

```bash
git checkout -b <short-topic-branch>
```

## 4. Verify the toolchain

From the repository root:

```bash
go version
git --version
make --version
make help
```

If your task uses Docker:

```bash
docker version
```

If your task changes the React UI **or you intend to run the full `make lint` target**:

```bash
node --version
pnpm --version
```

`make help` is the preferred discovery mechanism for repository-supported commands. Do not copy an old command list from an onboarding document when the Makefile has changed.

## 5. Go environment

The Makefile derives `GOPATH` from `go env GOPATH` when it is not set and exports `GOBIN`. The upstream contribution guide also documents an isolated setup if you want repository-local tooling.

A simple setup is usually enough:

```bash
export GOPATH="$(go env GOPATH)"
export GOBIN="${GOPATH}/bin"
export PATH="${GOBIN}:${PATH}"
export GOPROXY="https://proxy.golang.org"
```

You can place persistent environment configuration in your shell profile or an environment manager such as `direnv`.

Do not set cloud credentials just to make the basic build pass. Object-store integration tests are a separate concern.

## 6. Build Thanos

Run:

```bash
make build
```

The build target verifies Git availability, ensures Go dependencies are consistent, prepares build tooling, and builds the `thanos` binary through the repository build tooling. The binary is written under the configured `GOBIN`/build prefix.

Verify it:

```bash
which thanos || true
"${GOBIN}/thanos" --help
```

If `thanos` is not on your `PATH`, invoke it by its full path or add `GOBIN` to `PATH`.

### Dependency changes

Thanos uses Go modules. When intentionally adding or updating a dependency, update `go.mod`/`go.sum` and run:

```bash
make deps
```

The target performs `go mod tidy` and `go mod verify`. Dependency-file changes should be committed with the code that requires them.

## 7. Run tests locally

Choose the smallest test scope that proves your change.

### Fast local confidence

```bash
make test-local-short
```

This skips live object-store integrations and runs quick tests only.

### Normal local unit/integration tests without cloud credentials

```bash
make test-local
```

`make test-local` configures the test run to skip GCS, S3, Azure, Swift, COS, Aliyun OSS, BOS, OCI, and OBS live object-store integrations, then runs the repository test target.

Use this target when a normal `make test` fails only because you do not have cloud credentials.

### Full Go test target

```bash
make test
```

The full target runs Thanos Go tests while excluding `./test/e2e`. Some object-store acceptance paths may expect real provider credentials unless they are explicitly skipped.

### Target a package during development

For a tight edit/test loop, use normal Go tooling against the package you are modifying, for example:

```bash
go test ./pkg/query/...
go test ./pkg/store/...
go test ./pkg/receive/...
```

Before submitting a PR, return to the repository Make targets that correspond to your change.

## 8. End-to-end tests

Docker-based end-to-end tests live under `test/e2e`.

```bash
make test-e2e
```

This requires access to a Docker daemon and builds the E2E image unless explicitly configured otherwise.

To run E2E tests while skipping live object-store providers:

```bash
make test-e2e-local
```

For a single E2E test, the Makefile supports `SINGLE_E2E_TEST`:

```bash
make test-e2e SINGLE_E2E_TEST='TestName'
```

E2E execution can be resource intensive. Prefer focused package tests while iterating and use E2E for behavior that crosses component boundaries.

## 9. Start a local Thanos topology

For an interactive multi-component development environment, use the repository quickstart after choosing an object-store mode. The current script requires either an object-store config via `OBJSTORECFG_FILE` or local MinIO mode via `MINIO_ENABLED` (with the required MinIO executables available). For example, with a prepared local object-store config:

```bash
export OBJSTORECFG_FILE=/path/to/bucket.yml
make quickstart
```

The target builds Thanos, installs integration-test tool dependencies, and runs `scripts/quickstart.sh`. The script starts multiple Prometheus and Thanos processes, so treat it as an integration playground rather than the minimum setup required for normal package development.

The upstream single-host guide uses the following port layout for local experimentation:

| Component | Interface | Port |
|---|---|---:|
| Sidecar | gRPC | 10901 |
| Sidecar | HTTP | 10902 |
| Query | gRPC | 10903 |
| Query | HTTP | 10904 |
| Store | gRPC | 10905 |
| Store | HTTP | 10906 |
| Receive | gRPC / StoreAPI | 10907 |
| Receive | HTTP / remote write | 10908 |
| Receive | HTTP | 10909 |
| Rule | gRPC | 10910 |
| Rule | HTTP | 10911 |
| Compact | HTTP | 10912 |
| Query Frontend | HTTP | 10913 |

This single-host topology is for development and learning. Upstream documentation explicitly does not recommend a single-node Thanos topology for production.

## 10. Formatting, linting, docs, and generated files

Before opening a PR, run checks appropriate to the files you changed.

### Go or shell changes

```bash
make format
make lint
```

`make format` formats Go and shell sources and removes repository-defined whitespace noise. The full `make lint` target runs Go, React, and shell linting, so it requires the UI toolchain as well. For a backend-only iteration where Node/pnpm is intentionally unavailable, run the narrower repository targets such as `make go-lint` and `make shell-lint`, then use the full CI-equivalent checks before submission when possible.

### Documentation changes

```bash
make changed-docs
```

For broader validation:

```bash
make docs
make check-docs
```

`make check-docs` additionally validates documentation consistency and links and can take longer than the edit loop.

### Protobuf changes

```bash
make proto
```

Do not hand-edit generated protocol output when the source definition and generation target should be changed instead.

### React UI changes

React source code is under `pkg/ui/react-app`. Useful repository targets include:

```bash
make react-app
make react-app-lint
make react-app-test
```

The built React assets are emitted under `pkg/ui/static/react`.

## 11. Typical development loop

A practical loop for most Go changes is:

```bash
git fetch upstream
git rebase upstream/main

make build

go test ./pkg/<area>/...

make format
make test-local
make lint

git status
```

For documentation-only changes, replace the test/lint sequence with the relevant docs targets. For changes spanning component boundaries, add the relevant E2E test.

## 12. Pull-request readiness

Thanos requires Developer Certificate of Origin (DCO) sign-off on commits. Create signed-off commits with:

```bash
git commit -s -m '<message>'
```

Keep pull requests as small and focused as practical. Large features or new components should be discussed with maintainers and are expected to start with a proposal describing motivation, design decisions, and alternatives.

A PR is locally ready when:

- the repository builds from a clean checkout;
- targeted tests pass;
- relevant `make` validation passes;
- generated files are up to date;
- `git status` contains only intentional changes;
- commits carry the required DCO sign-off.

## 13. Common setup failures

### `go.mod requires go >= ...`

Your Go toolchain is older than the checked-out revision. Install the Go version required by that revision's `go.mod` and retry.

### Tests fail with cloud credential errors

You probably invoked a test path that expects live object stores. For normal local development, start with:

```bash
make test-local
```

Only configure real provider credentials when you intentionally need provider acceptance tests.

### `thanos` builds but the shell cannot find it

Check:

```bash
go env GOPATH
echo "$GOBIN"
echo "$PATH"
```

Then add the relevant binary directory to `PATH`.

### E2E tests cannot reach Docker

Confirm the Docker daemon is running and the current user can access it:

```bash
docker version
docker ps
```

### WSL 2 + local Kubernetes networking behaves unexpectedly

Check the upstream WSL 2 note before debugging Thanos itself, especially if the Kubernetes Service uses `sessionAffinity: ClientIP`.

### UI build fails but backend build succeeds

UI work has an additional Node.js/pnpm toolchain. Run the React-specific targets and ensure `pnpm` is available.

## 14. Source references

This guide is derived from the current upstream repository, principally:

- `go.mod`: https://github.com/thanos-io/thanos/blob/main/go.mod
- `Makefile`: https://github.com/thanos-io/thanos/blob/main/Makefile
- `CONTRIBUTING.md`: https://github.com/thanos-io/thanos/blob/main/CONTRIBUTING.md
- Getting Started: https://github.com/thanos-io/thanos/blob/main/docs/getting-started.md
- Main repository: https://github.com/thanos-io/thanos

When upgrading the demo corpus, re-check these sources because toolchain versions and Make targets are expected to evolve.
