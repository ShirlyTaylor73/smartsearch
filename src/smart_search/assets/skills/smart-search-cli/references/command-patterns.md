# Command Patterns

```bash
smart-search search answer "QUESTION" --format json
smart-search search sources "QUERY" --limit 5 --include-highlights --format json
smart-search docs resolve nextjs "app router" --format json
smart-search docs search "QUERY" --source owner/repo --format json
smart-search docs tree owner/repo --path src --format json
smart-search docs read owner/repo README.md --format content
smart-search fetch content URL --format content
smart-search fetch extract URL --schema '{"type":"object"}' --format json
smart-search map site URL --search authentication --sitemap include --limit 50 --format json
```
