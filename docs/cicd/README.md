# CI/CD for Mus Luxury

Operational handbook for every automated step between `git push` and a live
production release. Start here, then read the document that matches what
you're about to do.

| I want to…                              | Read                              |
| --------------------------------------- | --------------------------------- |
| Understand the whole pipeline           | `CI_CD_ARCHITECTURE.md`           |
| Know how branches and releases work     | `BRANCHING_STRATEGY.md`, `RELEASES.md` |
| Set up a brand-new VPS                  | `VPS_PREPARATION.md`              |
| Understand the three environments       | `ENVIRONMENTS.md`                 |
| Write or review a schema change         | `MIGRATIONS.md`                   |
| Know where secrets live                 | `SECRETS.md`                      |
| Roll back a bad release                 | `ROLLBACK.md`                     |
| Ship a Desktop CMS update               | `POS_UPDATE_STRATEGY.md`          |
| Recover from an incident                | `INCIDENT_RECOVERY.md`            |
| Restore a backup                        | `../OPERATIONS_GUIDE.md` §5.3     |

The whole pipeline can be exercised from a phone; nothing in it requires a
local laptop with build tools once the VPS is bootstrapped.
