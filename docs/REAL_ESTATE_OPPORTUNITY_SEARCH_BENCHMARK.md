# Real Estate Opportunity Search Benchmark

Use a small labeled query set before changing ranking weights or relevance thresholds. Labels must be reviewed by a broker and reference opportunity IDs from the same company.

## File format

```json
[
  {
    "name": "Two-bedroom Marina purchase",
    "activity_type": "buying",
    "query": "2 bedroom apartment in Dubai Marina under AED 2 million",
    "relevant_ids": [101, 119]
  }
]
```

Cover all four lanes, exact and flexible budgets, locality aliases, property types, bedrooms, intentionally irrelevant searches, and common broker shorthand. Keep the file outside source control if it contains production-derived data.

## Run

```powershell
python manage.py benchmark_opportunity_search --company company-slug --file .\benchmark.json
```

Use `--relevance all`, `--relevance strong`, or `--group-duplicates` to compare policies. The report provides Top-1 accuracy, mean reciprocal rank, and Recall@5. Running the benchmark calls the configured embedding provider once per case.
