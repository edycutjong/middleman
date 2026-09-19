# Security Policy

## Supported versions
| Version | Supported |
|---|---|
| latest (`main`) | ✅ |

## Reporting a vulnerability
Please **do not** open a public issue for anything exploitable. Instead:

- open a [private security advisory](../../security/advisories/new) (Security → Report a vulnerability), or
- email **edy.cu@live.com**.

You will get an acknowledgment within 48 hours and a resolution timeline after triage. Please
allow a reasonable window to patch before public disclosure.

## Secrets posture
**This project ships no secrets, by design.** The judged code path — the CLI, the deployed page,
the paste box and the `/api/swaps` proxy — uses CoinMarketCap's keyless `/public-api` surface,
so there is no API key in the repository, in CI, or in the deployment: not hidden, simply not
required. The only credential the project can read at all is an *optional* `CMC_API_KEY`
exported in a reader's own shell as an escape hatch for a throttled IP; it is never read from
disk, never printed, a keyed run announces itself on its first line and in its receipt, and
`scripts/seed.py` refuses to record one.

## The claims are tested, not asserted
- `test_with_every_key_variable_unset_no_credential_header_is_sent` unsets every CoinMarketCap
  variable the project could read and runs the real fetch path — if a key ever leaks into the
  judged path, that test fails.
- `test_no_key_variable_is_referenced_by_the_deployment` inspects `api/*.js` and `vercel.json`
  for any key variable or `process.env` on every run.
- `tests/test_proxy_boundary.py` drives the one deployed function with `fetch` stubbed and
  proves its least-privilege boundary: it can reach exactly one keyless CoinMarketCap URL,
  refuses any other host, path, platform or cursor without making a call, and never forwards
  a caller's key, bearer token, cookie or forwarded-host header upstream.
- `test_a_keyed_run_announces_itself_on_the_first_line_and_in_the_receipt` and
  `test_seed_refuses_to_record_a_keyed_receipt` keep a keyed run from ever passing as one of
  the published keyless receipts.

## Scanning
`gitleaks` on every push over the full history (`.gitleaks.toml` allowlists public contract
addresses, never credentials), CodeQL on Python and JavaScript weekly and on every push,
`pip-audit` in CI, Dependabot monthly for pip and GitHub Actions.
