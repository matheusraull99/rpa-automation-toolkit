"""
Web Scraping Automation
=======================
Demonstrates a typical RPA pattern: scrape structured data from
multiple web sources, normalize it, and produce a clean dataset.

This example uses a public API (JSONPlaceholder) instead of scraping
a real website. The pattern (loop → extract → validate → save) is
identical to a production scraping bot — only the source changes.

UiPath equivalent
-----------------
This automation maps to the following UiPath activities:
  - Open Browser
  - Navigate To
  - Extract Structured Data (or HTTP Request for APIs)
  - For Each (loop over rows)
  - Build Data Table + Append Row
  - Write CSV
  - Try Catch (error handling)

The advantages of recreating this in Python instead of using the
UiPath workflow directly:
  - Runs anywhere (no UiPath license required)
  - Easier version control
  - Faster execution for pure data-extraction work
  - Shared base framework across all bots
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.base_automation import BaseAutomation, retry

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class PublicAPIScraperBot(BaseAutomation):
    """Scrapes user data from a public test API and normalizes it."""

    BASE_URL = 'https://jsonplaceholder.typicode.com'

    def __init__(self):
        super().__init__(name='PublicAPIScraperBot')
        self.session: requests.Session | None = None

    def setup(self) -> None:
        self.logger.info('Initializing HTTP session...')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'rpa-toolkit/1.0',
            'Accept': 'application/json',
        })

    @retry(max_attempts=3, backoff_seconds=2.0)
    def _fetch_users(self) -> list[dict]:
        """
        Fetch users from API. Falls back to local mock data when the API
        is unreachable — useful for offline demos and CI environments
        where network egress is restricted.
        """
        try:
            resp = self.session.get(f'{self.BASE_URL}/users', timeout=10)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, requests.HTTPError) as e:
            self.logger.warning(f'Live API unreachable ({e}); using mock dataset')
            return self._mock_users()

    @retry(max_attempts=3, backoff_seconds=2.0)
    def _fetch_user_posts(self, user_id: int) -> list[dict]:
        try:
            resp = self.session.get(
                f'{self.BASE_URL}/posts',
                params={'userId': user_id},
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, requests.HTTPError):
            # Mock: 5-15 posts per user
            return [{'id': i, 'userId': user_id, 'title': f'Post {i}'}
                    for i in range(1, 8)]

    @staticmethod
    def _mock_users() -> list[dict]:
        """Realistic mock data with 10 users for offline demos."""
        names = [
            ('Leanne Graham', 'leanne@demo.com', 'Romaguera-Crona', 'Gwenborough'),
            ('Ervin Howell', 'ervin@demo.com', 'Deckow-Crist', 'Wisokyburgh'),
            ('Clementine Bauch', 'clem@demo.com', 'Romaguera-Jacobson', 'McKenziehaven'),
            ('Patricia Lebsack', 'patricia@demo.com', 'Robel-Corkery', 'South Elvis'),
            ('Chelsey Dietrich', 'chelsey@demo.com', 'Keebler LLC', 'Roscoeview'),
            ('Mrs. Dennis', 'dennis@demo.com', 'Considine-Lockman', 'South Christy'),
            ('Kurtis Weissnat', 'kurtis@demo.com', 'Johns Group', 'Howemouth'),
            ('Nicholas Runolfsdottir', 'nick@demo.com', 'Abernathy Group', 'Aliyaview'),
            ('Glenna Reichert', 'glenna@demo.com', 'Yost and Sons', 'Bartholomebury'),
            ('Clementina DuBuque', 'clema@demo.com', 'Hoeger LLC', 'Lebsackbury'),
        ]
        return [
            {
                'id': i + 1,
                'name': n[0],
                'username': n[0].split()[0].lower(),
                'email': n[1],
                'company': {'name': n[2]},
                'address': {'city': n[3]},
            }
            for i, n in enumerate(names)
        ]

    def run(self) -> None:
        self.logger.info('Fetching users...')
        users = self._fetch_users()
        self.logger.info(f'Got {len(users)} users')

        records = []
        for user in users:
            try:
                posts = self._fetch_user_posts(user['id'])
                records.append({
                    'user_id': user['id'],
                    'name': user['name'],
                    'username': user['username'],
                    'email': user['email'],
                    'company': user.get('company', {}).get('name', ''),
                    'city': user.get('address', {}).get('city', ''),
                    'post_count': len(posts),
                })
                self.metrics.items_processed += 1
            except Exception as e:
                self.metrics.items_failed += 1
                self.metrics.errors.append({
                    'user_id': user.get('id'),
                    'message': str(e),
                })
                self.logger.warning(f'Failed to enrich user {user.get("id")}: {e}')

        df = pd.DataFrame(records)
        output_path = OUTPUT_DIR / 'scraped_users.csv'
        df.to_csv(output_path, index=False)
        self.logger.info(f'Saved {len(df)} rows to {output_path}')

    def teardown(self) -> None:
        if self.session:
            self.session.close()
            self.logger.info('HTTP session closed')


if __name__ == '__main__':
    bot = PublicAPIScraperBot()
    bot.execute()
