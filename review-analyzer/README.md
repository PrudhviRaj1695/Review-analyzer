# Review Analyzer

## Run it

```bash
git clone git@github.com:PrudhviRaj1695/Review-analyzer.git
cd Review-analyzer/review-analyzer
docker compose up --build
```

Open http://localhost:8000/docs.

Postgres data persists in a named Docker volume across restarts. To wipe it, run `docker compose down -v`.
