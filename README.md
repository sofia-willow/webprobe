# 🔍 WebProbe

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Async](https://img.shields.io/badge/async-aiohttp-orange)

**Fast, async website health checker and performance analyzer.** Check response times, status codes, SSL certificate expiry, and redirect chains for any number of URLs — all at once.

---

## ✨ Features

- **⚡ Async Engine** — Check hundreds of URLs concurrently with aiohttp
- **🔒 SSL Analysis** — Detect expiring certificates (warns at <30 days)
- **🔄 Redirect Tracking** — Full redirect chain with status codes
- **📊 Multiple Outputs** — Color-coded table, JSON, or CSV
- **📁 File Input** — Read URLs from a file, one per line
- **🔧 Pipe-Friendly** — Works with stdin/stdout for shell pipelines

## 🚀 Quick Start

```bash
git clone https://github.com/sofia-willow/webprobe.git
cd webprobe
pip install -e .
```

### Check a single URL

```bash
python -m webprobe https://example.com
```

### Check multiple URLs

```bash
python -m webprobe https://google.com https://github.com https://httpbin.org/status/404
```

### Read from file

```bash
python -m webprobe -f urls.txt
```

### Output as JSON

```bash
python -m webprobe -o json https://example.com https://github.com
```

### Pipe from other tools

```bash
cat urls.txt | python -m webprobe -o csv > results.csv
```

## 📖 Usage

```
usage: webprobe [-h] [-f FILE] [-o {table,json,csv}] [-c CONCURRENCY]
                [-t TIMEOUT] [--no-redirects] [urls ...]

🔍 WebProbe — Fast, async website health checker

positional arguments:
  urls                  URLs to check

options:
  -f, --file FILE       Read URLs from file (one per line)
  -o, --output          Output format: table, json, csv (default: table)
  -c, --concurrency     Max concurrent connections (default: 20)
  -t, --timeout         Timeout per request in seconds (default: 30)
  --no-redirects        Don't follow redirects
```

## 🏗️ Architecture

```
webprobe/
├── __init__.py     # Package metadata
├── __main__.py     # python -m webprobe entry point
├── cli.py          # Argument parsing and CLI commands
├── models.py       # ProbeResult and RedirectHop dataclasses
├── checker.py      # Core async probing engine
└── output.py       # Table, JSON, and CSV formatters
```

**Data flow:** `CLI → URL list → probe_many() → async checks → format → output`

## 🧪 Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

**Built by [Sofia Willow](https://github.com/sofia-willow)**
