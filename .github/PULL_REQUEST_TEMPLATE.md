## What this changes

## Why

## Checklist
- [ ] `make ci` passes (lint, mypy, tests with the engine's coverage gate, audit, receipt gates)
- [ ] The judged path still runs live (`make demo`) — no mock, no offline flag introduced
- [ ] A regression test is named for the defect it pins, if this fixes one
- [ ] Any new number on a judge-facing surface is greppable in code or in a committed receipt
- [ ] `make site` re-rendered if a template or a receipt changed (`make check` fails otherwise)

## Related issues
Closes #
