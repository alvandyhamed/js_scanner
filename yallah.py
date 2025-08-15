#!/usr/bin/env python3


import base64
import json
import re
import sys
import urllib.parse
from typing import Dict, List, Optional

import requests


def determine_env_type(hostname: str) -> str:

    parts = hostname.split(".")
    if not parts:
        return "prod"
    # sandbox hosts always point at the production CDN
    if parts[0].lower() == "sandbox":
        return "prod"
    # development environments have 'dev' or 'ondemand' as the second label
    if len(parts) > 1 and parts[1].lower() in {"dev", "ondemand"}:
        return "dev"
    # default to production
    return "prod"


def parse_bootstrap_config(page: str) -> Optional[Dict[str, str]]:

    m = re.search(
        r'<script[^>]+id=["\']cl-bootstrap["\'][^>]+src=["\']([^"#]+)#([^"\']+)["\']',
        page,
        re.IGNORECASE,
    )
    if not m:
        return None
    encoded_fragment = m.group(2)
    try:
        decoded = base64.b64decode(encoded_fragment).decode("utf-8")
        config = json.loads(decoded)
        return config
    except Exception:
        return None


def load_apps_config(cdn_host: str, namespace: str) -> List[Dict[str, str]]:

    base_folder = "apps" if namespace == "standard" else "internal-apps"
    url = f"{cdn_host}/web/{base_folder}/_config/apps.json"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def find_app(apps: List[Dict[str, str]], app_id: str) -> Optional[Dict[str, str]]:

    for app in apps:
        if app.get("id") == app_id:
            return app
    return None


def fetch_entry_assets(cdn_host: str, namespace: str, repo: str, version: str) -> Dict[str, List[str]]:

    base_folder = "apps" if namespace == "standard" else "internal-apps"
    path = f"/web/{base_folder}/{repo}/{version}/entry-assets.json"
    url = f"{cdn_host}{path}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <url>")
        sys.exit(1)
    input_url = sys.argv[1]
    # Ensure the URL has a scheme
    if not urllib.parse.urlparse(input_url).scheme:
        input_url = "https://" + input_url
    # Determine which CDN to use based on the host
    hostname = urllib.parse.urlparse(input_url).hostname or ""
    env_type = determine_env_type(hostname)
    cdn_host = "https://cloverstatic.com" if env_type == "prod" else "https://dev.cloverstatic.com"
    # Fetch the page to find the bootstrap configuration
    try:
        resp = requests.get(input_url, timeout=10)
        page = resp.text
    except Exception as exc:
        print(f"Error fetching {input_url}: {exc}", file=sys.stderr)
        sys.exit(1)
    config = parse_bootstrap_config(page)
    # Default values if no configuration is found
    namespace = "standard"
    app_id = "web-portal"
    if config:
        namespace = config.get("namespace", namespace)
        app_id = config.get("appId", app_id)
    # Load the list of applications
    try:
        apps = load_apps_config(cdn_host, namespace)
    except Exception as exc:
        print(f"Unable to load apps configuration: {exc}", file=sys.stderr)
        sys.exit(1)
    app = find_app(apps, app_id)
    if not app:
        print(f"Application ID '{app_id}' not found in apps configuration.", file=sys.stderr)
        sys.exit(1)
    repo = app["repo"]
    version = app["version"]
    # Retrieve entry assets
    try:
        entry_assets = fetch_entry_assets(cdn_host, namespace, repo, version)
    except Exception as exc:
        print(f"Unable to fetch entry assets: {exc}", file=sys.stderr)
        sys.exit(1)
    # Print JavaScript bundle paths
    js_files = entry_assets.get("js", [])
    if not js_files:
        print("No JS bundles found.")
    else:
        for path in js_files:
            print(path)


if __name__ == "__main__":
    main()