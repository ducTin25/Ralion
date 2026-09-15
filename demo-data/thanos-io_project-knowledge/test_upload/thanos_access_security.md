# Thanos Access and Security Guide

- **Project:** Thanos (`thanos-io/thanos`)
- **Ralion category:** Access & security
- **Audience:** Contributors, reviewers, and engineers operating a Thanos development or test environment
- **Source baseline:** `main` branch, reviewed 2026-08-24
- **Purpose:** Explain what access a contributor actually needs, where credentials appear, and the security boundaries an engineer must preserve when developing or deploying Thanos.

> This guide separates **upstream Thanos behavior** from **recommended deployment practice**. Recommendations below are security defaults for a production-style environment; they are not presented as undocumented requirements of the open-source project.

## 1. Security model in one minute

Thanos treats metric data as sensitive. The upstream security policy also notes that external labels and query API parameters are less sensitive because they may appear in logs, metrics, or traces.

A normal contributor does not need privileged production access. The repository is public; development can be done from a fork, and local tests can be run without cloud object-store credentials by using the repository's local test targets.

The main security boundaries to understand are:

1. **GitHub contribution access** — fork, branch, PR, review, DCO sign-off.
2. **HTTP API/UI exposure** — do not assume a tenant header is authenticated identity.
3. **gRPC component traffic** — protect StoreAPI and other internal component traffic with network controls and TLS/mTLS where appropriate.
4. **Object storage** — credentials can grant read, write, or delete access to historical metrics; scope them by component.
5. **Local TSDB/cache data** — upstream does not provide built-in encryption of metric data stored on local disk.
6. **Vulnerability disclosure** — security issues are reported privately, not opened as public GitHub issues.

## 2. Contributor access

For normal development, the expected contribution flow is:

1. fork `thanos-io/thanos` into your GitHub account;
2. clone your fork locally;
3. add `https://github.com/thanos-io/thanos.git` as `upstream`;
4. create a topic branch from current `main`;
5. push the branch to your fork and open a pull request;
6. obtain review from maintainers/write-access reviewers.

Thanos uses the Developer Certificate of Origin. Commits must include a `Signed-off-by` trailer; `git commit -s` is the normal way to add it.

A contributor does **not** need write access to the canonical repository for ordinary pull requests.

## 3. Secrets and credentials

### 3.1 What counts as a secret in this project

Common examples include:

- object-store access keys or service-account credentials;
- cloud IAM credentials used by live acceptance tests;
- TLS private keys;
- bearer tokens or basic-auth passwords for downstream services;
- credentials embedded in Alertmanager, Query, tracing, or cache configuration;
- any credential granting access to a real metrics bucket.

### 3.2 Rules for local development

**Do not commit real credentials to the repository.** Keep local secrets outside tracked files and inject them through an appropriate environment, local secret file, cloud workload identity, or secret-management system.

Use `make test-local` when you do not need live object-store acceptance tests. It skips the supported live cloud-store integrations and avoids the most common reason a new contributor reaches for unnecessary cloud credentials.

The Thanos CLI also deliberately redacts the values of `objstore.config` and `objstore.config-file` when building the exposed flag map, because those configurations can contain credentials. That redaction is a defense-in-depth measure, not permission to place secrets in source control.

## 4. Object-store permissions

Object storage is a high-value boundary because it contains historical metric blocks and metadata.

Upstream component documentation identifies the components that should write to object storage:

- **Sidecar** — can upload blocks.
- **Receive** — can upload blocks produced from received metrics.
- **Rule** — can upload blocks produced by rule evaluation.
- **Compact** — writes compacted/downsampled blocks and is the component that may delete data.
- **Store Gateway** — reads historical blocks; it should not require normal write/delete privileges.

Only grant the actions required by the component. In particular, a Store Gateway should not inherit the Compactor's delete capability.

Live provider acceptance tests may require broader temporary permissions, including bucket creation/deletion depending on the test. Treat those as test credentials, not as the permission model for a deployed component.

### Recommended production practice

- Use separate identities/service accounts for different Thanos roles where practical.
- Apply least-privilege bucket policies.
- Restrict delete access to the Compactor workflow that requires it.
- Prefer short-lived workload identity over long-lived static keys.
- Enable object-store server-side encryption.
- Rotate credentials and revoke unused test identities.

These are deployment recommendations; the exact IAM mechanism depends on the chosen object-store provider.

## 5. HTTP access and authentication

Current Thanos components expose HTTP endpoints and support an `--http.config` file described by the CLI as an experimental way to enable TLS or authentication for HTTP endpoints.

However, **HTTP authentication and tenant identity are not the same thing**.

The Query documentation explicitly warns that Thanos does not itself authenticate an arbitrary tenant value in the request header. A caller that can reach Query can otherwise set a tenant header value, and the Query UI also allows a tenant to be selected. If tenant isolation matters, put an authentication/authorization layer in front of Query and bind authenticated identity to the tenant that the request is allowed to access.

### Recommended deployment practice

- Expose user-facing Query/Query Frontend through an authenticated reverse proxy or gateway.
- Have the gateway set or validate the tenant header; do not trust an arbitrary client-supplied tenant ID.
- Do not expose a multi-tenant Query UI directly to untrusted users when they can choose another tenant.
- Restrict admin/debug/status endpoints to the intended network and audience.
- Treat `--http.config` as a useful transport/authentication feature, but not as a complete authorization system for multi-tenant deployments.

## 6. Tenant isolation

Thanos Query supports tenancy-related options, including a configurable tenant header, a default tenant, and tenant enforcement.

When tenant enforcement is enabled, Query restricts series by a configured tenant label whose value corresponds to the request tenant. This assumes the stored metrics were labeled consistently at ingestion time.

Important boundary:

- **tenant enforcement constrains data selection**;
- **authentication establishes who the caller is**;
- **authorization establishes which tenant(s) that caller may use**.

Do not use a freely client-controlled header as the sole proof of tenant identity.

Query Frontend also contains tenant-header handling and can derive tenant information from a client TLS certificate field in supported configurations. If you use certificate-derived tenancy, ensure certificate issuance and trust are controlled by your platform security model.

## 7. gRPC / StoreAPI security

Thanos components use gRPC extensively, including the StoreAPI between Query and store-like components.

The common gRPC server configuration supports:

- a server certificate and private key;
- a client CA for client certificate verification (mTLS);
- a configurable minimum TLS version, currently defaulting to TLS 1.3 in the common CLI configuration;
- TLS cipher/curve configuration.

### Recommended deployment practice

- Keep StoreAPI endpoints on private service networks; they are inter-component APIs, not public user APIs.
- Use TLS for cross-host/cross-zone traffic when the network is not already providing an equivalent trusted transport boundary.
- Use mTLS when component identity is security relevant.
- Avoid `skip-verify` outside controlled debugging; it removes certificate verification.
- Rotate certificates through the deployment platform rather than baking long-lived private keys into images.

## 8. Receive endpoint

`thanos receive` exposes a distinct remote-write HTTP endpoint in addition to the component's normal HTTP/gRPC interfaces. Receive has separate TLS configuration for the remote-write server and client communication.

Do not assume that securing the generic component HTTP endpoint automatically secures every Receive ingestion path. Review the current Receive flags and deployment topology explicitly.

For a production-style deployment:

- expose remote write only to authorized Prometheus/agents or trusted gateways;
- apply TLS/mTLS at Receive or at the ingress/gateway layer;
- use network policy/firewall rules to limit who can send metrics;
- validate the current release behavior before relying on basic authentication for the remote-write ingestion endpoint.

## 9. Data at rest

The upstream `SECURITY.md` states that Thanos does not encrypt metric data in local storage itself and does not provide client-side object-store encryption. It recommends server-side encryption for object storage.

Consequences for operators:

- protect disks/volumes containing local TSDB/cache data with platform-level disk encryption when required;
- use provider-side bucket encryption and appropriate KMS controls for object storage;
- restrict filesystem and volume access to the Thanos workload identity;
- remember that deleting a local Store Gateway cache is different from deleting historical object-store data.

## 10. Logging, tracing, and sensitive data

The upstream security policy states that TSDB metric data should not be put into logs or instrumentation. It also calls out external labels and query parameters as less sensitive because they can appear in telemetry.

When adding instrumentation:

- do not log raw metric samples or secret configuration;
- do not add tokens, private keys, passwords, or object-store credentials to labels, traces, or error messages;
- consider query expressions, external labels, tenant IDs, and request metadata observable information;
- preserve existing redaction behavior for object-store configuration.

## 11. Security-sensitive code areas

A change deserves additional review when it touches any of the following:

- `pkg/tls` or common HTTP/gRPC server configuration;
- `pkg/tenancy` or tenant-header propagation/enforcement;
- object-store configuration or IAM assumptions;
- Receive ingestion and forwarding;
- Query/Query Frontend request forwarding;
- request logging/tracing middleware;
- secret-bearing CLI/config fields;
- Compactor deletion behavior;
- authentication/TLS configuration.

For such changes, add tests that demonstrate the security property rather than only testing the happy path.

## 12. Vulnerability reporting

Do **not** disclose a suspected security vulnerability in a public issue before coordinating with the maintainers.

The upstream security policy asks reporters to contact the Thanos team privately at:

`thanos-io@googlegroups.com`

For ordinary bugs and feature requests, use GitHub Issues according to the contribution guide.

## 13. Access matrix for a typical development environment

The following is a recommended onboarding baseline, not an upstream RBAC product feature.

| Capability                    | New contributor |  Integration-test engineer |           Production operator |
| ----------------------------- | --------------: | -------------------------: | ----------------------------: |
| Read public repository        |             Yes |                        Yes |                           Yes |
| Push branch to own fork       |             Yes |                        Yes |                      Optional |
| Open PR                       |             Yes |                        Yes |                      Optional |
| Write canonical `main`        |              No |                         No |                 No by default |
| Local `make test-local`       |             Yes |                        Yes |                      Optional |
| Real object-store credentials |              No |          As needed, scoped |            Component-specific |
| Object-store delete           |              No | Only if a test requires it | Compactor only where required |
| Production Query access       |              No |              No by default |                 Role-specific |
| Production StoreAPI access    |              No |              No by default |       Service-to-service only |
| Production secret access      |              No |              No by default |               Least privilege |

## 14. Security checklist before merging or deploying

For a code change:

- [ ] No real secret or credential is committed.
- [ ] Logs/traces do not expose metric data or secret-bearing config.
- [ ] Authorization assumptions are explicit when tenant headers are involved.
- [ ] New network endpoints have a documented trust boundary.
- [ ] TLS/authentication behavior is covered by tests when changed.
- [ ] Object-store permissions have not been widened unnecessarily.
- [ ] Security-sensitive behavior has an appropriate reviewer.

For a deployment:

- [ ] User-facing Query access is authenticated when required.
- [ ] Tenant identity cannot be freely spoofed by the caller.
- [ ] StoreAPI/other internal ports are network restricted.
- [ ] gRPC/HTTP transport security matches the threat model.
- [ ] Object-store identities are least privilege.
- [ ] Delete permissions are tightly controlled.
- [ ] Server-side object-store encryption is enabled when required.
- [ ] Local volumes use platform encryption when required.
- [ ] Secrets come from a secret-management mechanism, not source control.

## 15. Source references

This guide is derived from current upstream sources, principally:

- `SECURITY.md`: https://github.com/thanos-io/thanos/blob/main/SECURITY.md
- `CONTRIBUTING.md`: https://github.com/thanos-io/thanos/blob/main/CONTRIBUTING.md
- Query component: https://github.com/thanos-io/thanos/blob/main/docs/components/query.md
- Receive component: https://github.com/thanos-io/thanos/blob/main/docs/components/receive.md
- Store component: https://github.com/thanos-io/thanos/blob/main/docs/components/store.md
- Compact component: https://github.com/thanos-io/thanos/blob/main/docs/components/compact.md
- Object storage configuration: https://github.com/thanos-io/thanos/blob/main/docs/storage.md
- Common server configuration: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/config.go
- CLI entry point/redaction behavior: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/main.go

Security behavior changes over time. Validate the exact release or commit you deploy rather than assuming a guide written against `main` is identical to an older binary.
