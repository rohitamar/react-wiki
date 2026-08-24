from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_URL = "https://en.wikipedia.org/w/api.php"
DEFAULT_USER_AGENT = "react-wiki-bfs/0.1 (https://github.com/rohitamar/react-wiki)"

def title_key(title: str) -> str:
    return " ".join(title.replace("_", " ").split()).casefold()

def shortest_path(
    start: str,
    target: str,
    get_links: Callable[[str], Iterable[str]],
    max_workers: int = 3,
    max_depth: int | None = None,
    max_nodes: int = 100_000,
) -> list[str] | None:
    if not start.strip() or not target.strip():
        raise ValueError("start and target must not be empty")
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    if max_nodes < 1:
        raise ValueError("max_nodes must be at least 1")

    start = start.strip().replace("_", " ")
    target = target.strip().replace("_", " ")
    start_key = title_key(start)
    target_key = title_key(target)
    visited = {start_key: start}
    parent: dict[str, str | None] = {start_key: None}
    frontier = [start]

    if start_key == target_key:
        return [start]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        depth = 0
        while frontier and (max_depth is None or depth < max_depth):
            next_frontier: list[str] = []
            for page, links in zip(frontier, executor.map(get_links, frontier)):
                for link in links:
                    normalized = link.strip().replace("_", " ")
                    key = title_key(normalized)
                    if not normalized or key in visited:
                        continue
                    if len(visited) >= max_nodes:
                        return None
                    visited[key] = normalized
                    parent[key] = title_key(page)
                    next_frontier.append(normalized)
                    if key == target_key:
                        path_keys = [key]
                        while parent[path_keys[-1]] is not None:
                            path_keys.append(parent[path_keys[-1]])
                        path_keys.reverse()
                        return [visited[item] for item in path_keys]
            frontier = next_frontier
            depth += 1

    return None

class WikipediaClient:
    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.api_url = api_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries

    def _request(self, params: dict[str, str]) -> dict:
        url = f"{self.api_url}?{urlencode(params)}"
        for attempt in range(self.retries + 1):
            request = Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read())
            except HTTPError as error:
                if error.code not in {429, 502, 503, 504} or attempt == self.retries:
                    raise
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
            except URLError:
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("Wikipedia request failed")

    def resolve_title(self, title: str) -> str:
        data = self._request(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
                "prop": "info",
                "titles": title,
            }
        )
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            raise ValueError(f"Wikipedia article not found: {title}")
        return pages[0]["title"]

    def get_links(self, title: str) -> list[str]:
        links: list[str] = []
        continuation: dict[str, str] = {}
        while True:
            params = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
                "prop": "links",
                "titles": title,
                "plnamespace": "0",
                "pllimit": "max",
                **continuation,
            }
            data = self._request(params)
            for page in data.get("query", {}).get("pages", []):
                links.extend(link["title"] for link in page.get("links", []))
            continuation = data.get("continue", {})
            if not continuation:
                return links

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find a shortest path between Wikipedia articles.")
    parser.add_argument("start", help="starting Wikipedia article title")
    parser.add_argument("target", help="target Wikipedia article title")
    parser.add_argument("--workers", type=int, default=3, help="maximum concurrent Wikipedia requests")
    parser.add_argument("--max-depth", type=int, default=None, help="maximum number of edges to traverse")
    parser.add_argument("--max-nodes", type=int, default=100_000, help="maximum number of discovered articles")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Wikipedia API endpoint")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent for Wikipedia requests")
    return parser

def main() -> None:
    args = build_parser().parse_args()
    client = WikipediaClient(api_url=args.api_url, user_agent=args.user_agent)
    start = client.resolve_title(args.start)
    target = client.resolve_title(args.target)
    path = shortest_path(
        start,
        target,
        client.get_links,
        max_workers=args.workers,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
    )
    print(json.dumps({"start": start, "target": target, "path": path}, indent=2))

if __name__ == "__main__":
    main()
