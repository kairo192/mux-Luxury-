## Summary

<!-- 1–3 lines: what this PR changes and why. -->

## Scope

- [ ] Backend
- [ ] Storefront
- [ ] Desktop CMS / POS
- [ ] Infrastructure / CI / CD
- [ ] Documentation only

## Database

- [ ] No schema change
- [ ] Schema change — migration file added at `backend/migrations/versions/NNN_*.sql`
      and respects the forward-only rules (`docs/cicd/MIGRATIONS.md`)
- [ ] POS protocol change — `POS_API_CONTRACT_VERSION` / `POS_MIN_SUPPORTED_VERSION`
      updated in `docs/cicd/POS_UPDATE_STRATEGY.md`

## Test plan

<!-- How did you verify this? A reviewer must be able to repeat this. -->

- [ ] `python -m unittest discover -s backend/tests -v` is green
- [ ] Storefront builds (`npm --prefix apps/storefront run build`)
- [ ] CMS builds (`npm --prefix apps/desktop-cms run build`)

## Rollback plan

<!-- One line. Usually "flip the symlink back". For schema changes, name the
     specific backup archive that would restore the pre-migration state. -->
