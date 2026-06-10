# Silver Calendar Grain Check

`silver_calendar` is modeled at one row per `listing_id + calendar_date`.

Current approach:

1. Clean and type raw Bronze calendar fields.
2. Keep only rows with valid `listing_id` and `calendar_date`.
3. Enforce the target grain with a dbt uniqueness test on `listing_id + calendar_date`.

Why there is no heuristic dedup rule right now:

- A direct MotherDuck profile run on June 11, 2026 found `0` duplicate keys for `listing_id + calendar_date` in `bronze_calendar`.
- Adding a tie-break rule without actual duplicate keys would only make the model more complex without improving data quality.
- If duplicate keys appear later, the project already has a profiling query ready to guide a real dedup rule.

How to re-check this assumption:

```bash
dbt compile --select bronze_calendar_duplicate_profile
```

Then open the compiled SQL under `target/compiled/.../analyses/bronze_calendar_duplicate_profile.sql` and run it against your Bronze database.

Inspect:

- how many duplicate keys exist
- which fields conflict most often across duplicate keys
