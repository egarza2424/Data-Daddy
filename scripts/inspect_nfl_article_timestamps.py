
"""Inspect NFL article timestamp metadata without verifying it."""

import json
import re
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path


class TimestampParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = []
        self.json_ld = []
        self.in_json_ld = False
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
                or ""
            )
            if any(word in key.lower() for word in (
                "publish", "modif", "update", "date", "time"
            )):
                self.metadata.append({
                    "key": key,
                    "value": attributes.get("content", ""),
                })

        if tag == "script" and (
            "ld+json" in attributes.get("type", "").lower()
        ):
            self.in_json_ld = True
            self.buffer = []

    def handle_data(self, data):
        if self.in_json_ld:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json_ld:
            raw = "".join(self.buffer).strip()
            try:
                self.json_ld.append(json.loads(raw))
            except (ValueError, TypeError):
                pass
            self.in_json_ld = False
            self.buffer = []


def find_dates(value, path="$"):
    results = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if any(word in key.lower() for word in (
                "publish", "modif", "update", "date", "time"
            )):
                results.append((child_path, child))
            if isinstance(child, (dict, list)):
                results.extend(find_dates(child, child_path))

    elif isinstance(value, list):
        for index, child in enumerate(value):
            results.extend(find_dates(child, f"{path}[{index}]"))

    return results


def main():
    discovery = json.loads(
        Path("data/nfl_inactive_report_candidates.json")
        .read_text(encoding="utf-8")
    )

    candidates = discovery["candidates"]

    if len(candidates) != 1:
        raise SystemExit("Expected exactly one discovered article")

    url = candidates[0]["url"]

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(
        request, timeout=45
    ) as response:
        html = response.read().decode(
            "utf-8", errors="replace"
        )
        headers = dict(response.headers.items())

    parser = TimestampParser()
    parser.feed(html)

    print("Article:", url)

    print("\nHTTP timestamp headers:")
    for key, value in headers.items():
        if key.lower() in {"date", "last-modified"}:
            print(f"{key}: {value}")

    print("\nTimestamp meta tags:")
    for item in parser.metadata:
        print(f"{item['key']}: {unescape(item['value'])}")

    print("\nStructured-data timestamp fields:")
    for index, document in enumerate(parser.json_ld):
        for path, value in find_dates(document):
            print(f"JSON-LD[{index}]{path}: {value}")

    print("\nTimestamp-like HTML fields:")
    patterns = [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateModified"\s*:\s*"([^"]+)"',
        r'"publishedAt"\s*:\s*"([^"]+)"',
        r'"updatedAt"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:
        matches = sorted(set(re.findall(pattern, html)))
        print(pattern, matches[:10])

    print("\nINSPECTION ONLY: timestamps are not verified.")


if __name__ == "__main__":
    main()
