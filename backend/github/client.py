"""
github/client.py
Dual-mode GitHub client:
  - GitHubClient: GraphQL API (used for PR intelligence and discussions)
  - GitHubRestClient: REST API (used for issues, branches, forks, workflows, projects)
Both clients support:
  - Optional token (works for public repos without token)
  - Rate limit handling with automatic wait/retry
  - Exponential backoff on server errors
  - Full pagination until exhausted
"""

import os
import time
import requests
from typing import Dict, List, Any, Tuple, Optional, Generator
from datetime import datetime, timedelta

class GitHubRateLimitException(Exception):
    """Exception raised when GitHub API rate limit is reached or near limit and sleep duration is too long."""
    def __init__(self, message="GitHub API rate limit exceeded.", sleep_secs=0):
        super().__init__(message)
        self.sleep_secs = sleep_secs

class MockResponse:
    def __init__(self, json_data, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._json_data

    @property
    def text(self):
        import json
        return json.dumps(self._json_data)

class GitHubClient:
    def __init__(self, token: str = None):
        self.token = token
        self.base_url = "https://api.github.com/graphql"

        self.headers = {"Content-Type": "application/json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        print(f"[AUTH AUDIT] GitHubClient init: token_present={bool(self.token)}")

    def query(self, query: str, variables: Dict = None) -> Dict:
        """Execute GraphQL query with rate limit handling and retries."""
        if (self.token and (self.token.startswith("mock") or self.token.startswith("github_pat_mock"))) or os.getenv("MOCK_GITHUB") == "true":
            mock_res = self._mock_query(query, variables)
            return mock_res.get("data", {})

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        max_retries = 3
        backoff_delay = 5.0

        for attempt in range(max_retries):
            try:
                response = requests.post(self.base_url, json=payload, headers=self.headers, timeout=30)

                if response.status_code in (403, 429):
                    reset_time_str = response.headers.get("X-RateLimit-Reset")
                    if reset_time_str:
                        try:
                            reset_time = float(reset_time_str)
                            sleep_dur = max(1.0, reset_time - time.time() + 2)
                            # If we have a token, use the full quota and wait until reset
                            if self.token:
                                print(f"[Rate Limit] Authenticated token present — sleeping {sleep_dur:.0f}s until reset...")
                                time.sleep(sleep_dur)
                                continue
                            # Unauthenticated: surface a rate limit exception so caller can persist state and resume later
                            raise GitHubRateLimitException(
                                f"GitHub GraphQL API rate limited. Need to sleep {sleep_dur:.0f}s.",
                                sleep_secs=sleep_dur
                            )
                        except GitHubRateLimitException:
                            raise
                        except Exception:
                            pass
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                    continue

                if response.status_code == 401:
                    raise Exception("Bad credentials: GitHub token is invalid or expired")

                if response.status_code != 200:
                    if response.status_code in (500, 502, 503, 504, 408):
                        if attempt == max_retries - 1:
                            raise Exception(f"GitHub API error {response.status_code}: {response.text[:200]}")
                        time.sleep(backoff_delay)
                        backoff_delay *= 2
                        continue
                    raise Exception(f"GitHub API returned HTTP {response.status_code}: {response.text[:200]}")

                data = response.json()

                # Capture rate limit info if present in headers or payload
                try:
                    rl_limit = response.headers.get("X-RateLimit-Limit")
                    rl_rem = response.headers.get("X-RateLimit-Remaining")
                    rl_reset = response.headers.get("X-RateLimit-Reset")
                    
                    # Fallback to GraphQL payload rateLimit if headers missing
                    gql_rl = data.get("rateLimit") or {}
                    if not rl_limit and "limit" in gql_rl:
                        rl_limit = gql_rl.get("limit")
                    if not rl_rem and "remaining" in gql_rl:
                        rl_rem = gql_rl.get("remaining")
                    if not rl_reset and "resetAt" in gql_rl:
                        rl_reset = gql_rl.get("resetAt")

                    if rl_limit or rl_rem or rl_reset:
                        self.last_rate_limit = {
                            "limit": int(rl_limit) if rl_limit else None,
                            "remaining": int(rl_rem) if rl_rem else None,
                            "reset": float(rl_reset) if isinstance(rl_reset, (int, float)) else None,
                        }
                    
                    limit_int = int(rl_limit) if rl_limit is not None else None
                    rem_int = int(rl_rem) if rl_rem is not None else None
                    print(
                        f"[AUTH AUDIT]\n"
                        f"token_present={bool(self.token)}\n"
                        f"authenticated={bool(self.token) and limit_int is not None and limit_int > 60}\n"
                        f"rate_limit={limit_int if limit_int is not None else 'unknown'}\n"
                        f"remaining={rem_int if rem_int is not None else 'unknown'}"
                    )
                except Exception as audit_err:
                    print(f"[AUTH AUDIT] Error extracting audit info: {audit_err}")

                if "errors" in data:
                    error_msg = str(data["errors"])
                    if "rate limit" in error_msg.lower() or "secondary" in error_msg.lower():
                        time.sleep(backoff_delay)
                        backoff_delay *= 2
                        continue
                    raise Exception(f"GraphQL Error: {error_msg}")

                return data.get("data", {})

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise Exception("GitHub API request timed out.")
                time.sleep(backoff_delay)
                backoff_delay *= 2
            except requests.exceptions.ConnectionError as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Connection error to GitHub API: {e}")
                time.sleep(backoff_delay)
                backoff_delay *= 2
            except Exception:
                raise

    def verify_repository_access(self, owner: str, repo: str) -> Dict[str, Any]:
        """Verify repository access and check if it is private."""
        query = """
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                isPrivate
                name
                owner { login }
                diskUsage
                stargazerCount
                watchers { totalCount }
                primaryLanguage { name }
                defaultBranchRef { name }
                description
                homepageUrl
                forkCount
            }
        }
        """
        variables = {"owner": owner, "repo": repo}
        data = self.query(query, variables)
        repo_data = data.get("repository")
        if not repo_data:
            raise Exception("Could not resolve to a Repository.")
        return {
            "ok": True,
            "is_private": repo_data.get("isPrivate", False),
            "owner": repo_data.get("owner", {}).get("login", owner),
            "repo": repo_data.get("name", repo),
            "stars": repo_data.get("stargazerCount", 0),
            "watchers": repo_data.get("watchers", {}).get("totalCount", 0),
            "language": (repo_data.get("primaryLanguage") or {}).get("name"),
            "default_branch": (repo_data.get("defaultBranchRef") or {}).get("name"),
            "description": repo_data.get("description"),
            "homepage": repo_data.get("homepageUrl"),
            "fork_count": repo_data.get("forkCount", 0),
            "disk_usage": repo_data.get("diskUsage", 0),
        }

    def fetch_pull_requests(
        self, owner: str, repo: str, first: int = 100, cursor: str = None
    ) -> Tuple[List[Dict], Dict, Dict]:
        """Fetch a page of PRs with reviews and commits, plus rate limit info."""
        query = """
        query($owner: String!, $repo: String!, $first: Int!, $cursor: String) {
            rateLimit { limit remaining resetAt }
            repository(owner: $owner, name: $repo) {
                pullRequests(first: $first, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                        number
                        title
                        body
                        state
                        isDraft
                        mergeable
                        labels(first: 100) { nodes { name } }
                        baseRefName
                        headRefName
                        createdAt
                        updatedAt
                        mergedAt
                        closedAt
                        commits(first: 1) { totalCount }
                        files(first: 100) {
                            totalCount
                            nodes { additions deletions }
                        }
                        reviews(first: 100) {
                            totalCount
                            nodes {
                                state
                                submittedAt
                                author { login }
                                comments(first: 1) { totalCount }
                            }
                        }
                        comments(first: 1) { totalCount }
                        author { login }
                    }
                }
            }
        }
        """
        variables = {"owner": owner, "repo": repo, "first": first, "cursor": cursor}
        data = self.query(query, variables)
        rate_limit = data.get("rateLimit", {})
        repo_data = data.get("repository")
        if not repo_data:
            raise Exception(
                "Could not resolve to a Repository. Check the URL is correct "
                "(https://github.com/owner/repo) and your token can access it."
            )
        conn = repo_data.get("pullRequests", {})
        prs = conn.get("nodes", [])
        page_info = conn.get("pageInfo", {"hasNextPage": False, "endCursor": None})
        return prs or [], page_info, rate_limit

    def fetch_repository_module_features(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Probe whether Discussions and Projects are available for a repository.
        Used before sync to avoid silent failures and to log accurate telemetry.
        """
        query = """
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                hasDiscussionsEnabled
                discussions { totalCount }
                projectsV2(first: 1) { totalCount }
            }
        }
        """
        try:
            data = self.query(query, {"owner": owner, "repo": repo})
            repo_data = data.get("repository")
            if not repo_data:
                return {
                    "accessible": False,
                    "discussions_enabled": False,
                    "discussions_total": 0,
                    "projects_total": 0,
                    "status": "not_found",
                    "message": "Repository not found or token cannot access it.",
                }
            discussions_conn = repo_data.get("discussions") or {}
            projects_conn = repo_data.get("projectsV2") or {}
            discussions_total = discussions_conn.get("totalCount", 0) or 0
            projects_total = projects_conn.get("totalCount", 0) or 0
            discussions_enabled = bool(repo_data.get("hasDiscussionsEnabled"))
            return {
                "accessible": True,
                "discussions_enabled": discussions_enabled,
                "discussions_total": discussions_total,
                "projects_total": projects_total,
                "status": "ok",
                "message": None,
            }
        except Exception as e:
            status = self._classify_module_error(str(e), "repository")
            print(f"[Telemetry][Features] {owner}/{repo} feature probe failed ({status}): {e}")
            return {
                "accessible": status != "auth",
                "discussions_enabled": False,
                "discussions_total": 0,
                "projects_total": 0,
                "status": status,
                "message": str(e)[:300],
            }

    @staticmethod
    def _classify_module_error(error_msg: str, module: str) -> str:
        """Classify GraphQL/HTTP errors for discussions/projects modules."""
        msg = error_msg.lower()
        if "bad credentials" in msg or "401" in msg:
            return "auth"
        if "forbidden" in msg or "resource not accessible" in msg or "must have push access" in msg:
            return "forbidden"
        if module == "discussions" and ("discussions" in msg and ("disabled" in msg or "not enabled" in msg)):
            return "disabled"
        if module == "projects" and ("projects" in msg and ("disabled" in msg or "not supported" in msg)):
            return "disabled"
        if "could not resolve to a repository" in msg or "not_found" in msg:
            return "not_found"
        if "rate limit" in msg:
            return "rate_limit"
        return "error"

    def fetch_discussions(self, owner: str, repo: str, first: int = 100, cursor: str = None) -> Tuple[List[Dict], Dict]:
        """Fetch discussions via GraphQL (repository must have discussions enabled)."""
        query = """
        query($owner: String!, $repo: String!, $first: Int!, $cursor: String) {
            repository(owner: $owner, name: $repo) {
                discussions(first: $first, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                        id
                        number
                        title
                        body
                        category { name }
                        author { login }
                        closed
                        answer { id }
                        comments(first: 100) {
                            totalCount
                            nodes {
                                id
                                author { login }
                                body
                                reactions { totalCount }
                                createdAt
                                replies(first: 100) {
                                    totalCount
                                    nodes {
                                        id
                                        author { login }
                                        body
                                        reactions { totalCount }
                                        createdAt
                                    }
                                }
                            }
                        }
                        reactions { totalCount }
                        participants(first: 1) { totalCount }
                        createdAt
                        updatedAt
                    }
                }
            }
        }
        """
        variables = {"owner": owner, "repo": repo, "first": first, "cursor": cursor}
        try:
            data = self.query(query, variables)
            repo_data = data.get("repository")
            if not repo_data:
                print(f"[Telemetry][Discussions] API response: repository=null (check token/repo visibility)")
                return [], {"hasNextPage": False, "endCursor": None}
            conn = repo_data.get("discussions") or {}
            nodes = [n for n in (conn.get("nodes") or []) if n]
            page_info = conn.get("pageInfo", {"hasNextPage": False, "endCursor": None})
            print(f"[Telemetry][Discussions] API response count: {len(nodes)} discussions fetched (page)")
            return nodes, page_info
        except Exception as e:
            status = self._classify_module_error(str(e), "discussions")
            print(f"[Telemetry][Discussions] Fetch failed ({status}): {e}")
            if status == "auth":
                print("[Telemetry][Discussions] Token invalid or expired — check user PAT.")
            elif status == "forbidden":
                print("[Telemetry][Discussions] Token lacks access to this repository (private repo needs repo scope).")
            return [], {"hasNextPage": False, "endCursor": None}

    def fetch_projects_v2(self, owner: str, repo: str, first: int = 100, cursor: str = None) -> Tuple[List[Dict], Dict]:
        """Fetch GitHub Projects v2 linked to a repository via GraphQL."""
        query = """
        query($owner: String!, $repo: String!, $first: Int!, $cursor: String) {
            repository(owner: $owner, name: $repo) {
                projectsV2(first: $first, after: $cursor) {
                    pageInfo { hasNextPage endCursor }
                    totalCount
                    nodes {
                        id
                        number
                        title
                        shortDescription
                        closed
                        creator { login }
                        createdAt
                        updatedAt
                        items(first: 100) {
                            nodes {
                                id
                                type
                                fieldValues(first: 100) {
                                    nodes {
                                        ... on ProjectV2ItemFieldSingleSelectValue {
                                            name
                                            field {
                                                ... on ProjectV2FieldCommon {
                                                    name
                                                }
                                            }
                                        }
                                    }
                                }
                                content {
                                    ... on DraftIssue {
                                        title
                                        body
                                        createdAt
                                        updatedAt
                                        assignees(first: 10) {
                                            nodes { login }
                                        }
                                    }
                                    ... on Issue {
                                        title
                                        state
                                        createdAt
                                        updatedAt
                                        assignees(first: 10) {
                                            nodes { login }
                                        }
                                    }
                                    ... on PullRequest {
                                        title
                                        state
                                        createdAt
                                        updatedAt
                                        assignees(first: 10) {
                                            nodes { login }
                                        }
                                    }
                                }
                            }
                            totalCount
                        }
                    }
                }
            }
        }
        """
        variables = {"owner": owner, "repo": repo, "first": first, "cursor": cursor}
        try:
            data = self.query(query, variables)
            repo_data = data.get("repository")
            if not repo_data:
                print(f"[Telemetry][Projects] API response: repository=null (check token/repo visibility)")
                return [], {"hasNextPage": False, "endCursor": None}
            conn = repo_data.get("projectsV2") or {}
            raw_nodes = conn.get("nodes") or []
            nodes = [n for n in raw_nodes if n]
            null_count = len(raw_nodes) - len(nodes)
            if null_count:
                print(
                    f"[Telemetry][Projects] API returned {null_count} null project node(s) "
                    f"(likely missing read:project scope on token). "
                    f"totalCount={conn.get('totalCount', '?')}"
                )
            page_info = conn.get("pageInfo", {"hasNextPage": False, "endCursor": None})
            print(f"[Telemetry][Projects] API response count: {len(nodes)} projects fetched (page)")
            return nodes, page_info
        except Exception as e:
            status = self._classify_module_error(str(e), "projects")
            print(f"[Telemetry][Projects] Fetch failed ({status}): {e}")
            if status == "forbidden":
                print("[Telemetry][Projects] Token may need read:project scope for Projects v2.")
            return [], {"hasNextPage": False, "endCursor": None}

    def parse_pr_data(self, pr: Dict) -> Dict:
        """Parse raw PR data into structured format."""
        try:
            if not pr:
                raise ValueError("PR data is None")

            created_at_str = pr.get("createdAt")
            if not created_at_str:
                raise ValueError("PR missing createdAt")

            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

            updated_at_str = pr.get("updatedAt")
            updated_at = None
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))

            merged_at = pr.get("mergedAt")
            if merged_at:
                merged_at = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))

            closed_at = pr.get("closedAt")
            if closed_at:
                closed_at = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))

            cycle_time_days = None
            if merged_at:
                cycle_time_days = (merged_at - created_at).total_seconds() / 86400

            reviews_data = pr.get("reviews")
            reviews = []
            if reviews_data and isinstance(reviews_data, dict):
                reviews = reviews_data.get("nodes", []) or []

            first_review_time = None
            last_review_time = None
            approval_count = 0
            change_request_count = 0

            for review in reviews:
                if review and review.get("submittedAt"):
                    review_time = datetime.fromisoformat(review["submittedAt"].replace("Z", "+00:00"))
                    if not first_review_time or review_time < first_review_time:
                        first_review_time = review_time
                    if not last_review_time or review_time > last_review_time:
                        last_review_time = review_time
                    if review.get("state") == "APPROVED":
                        approval_count += 1
                    elif review.get("state") == "CHANGES_REQUESTED":
                        change_request_count += 1

            wait_for_review_hours = None
            if first_review_time:
                wait_for_review_hours = (first_review_time - created_at).total_seconds() / 3600

            review_duration_hours = None
            if first_review_time and last_review_time:
                review_duration_hours = (last_review_time - first_review_time).total_seconds() / 3600

            files_data = pr.get("files")
            files = []
            if files_data and isinstance(files_data, dict):
                files = files_data.get("nodes", []) or []

            lines_added = sum(f.get("additions", 0) for f in files if f)
            lines_deleted = sum(f.get("deletions", 0) for f in files if f)

            author_data = pr.get("author")
            author = "unknown"
            if author_data and isinstance(author_data, dict):
                author = author_data.get("login", "unknown")

            commits_data = pr.get("commits")
            commit_count = 0
            if commits_data and isinstance(commits_data, dict):
                commit_count = commits_data.get("totalCount", 0) or 0

            files_count = 0
            if files_data and isinstance(files_data, dict):
                files_count = files_data.get("totalCount", 0) or 0

            reviews_count = 0
            if reviews_data and isinstance(reviews_data, dict):
                reviews_count = reviews_data.get("totalCount", 0) or 0

            comments_data = pr.get("comments")
            comment_count = 0
            if comments_data and isinstance(comments_data, dict):
                comment_count = comments_data.get("totalCount", 0) or 0

            # Labels
            labels_data = pr.get("labels", {})
            label_names = []
            if labels_data and isinstance(labels_data, dict):
                label_names = [n.get("name", "") for n in (labels_data.get("nodes") or []) if n]

            return {
                "number": pr.get("number", 0),
                "title": pr.get("title", ""),
                "body": pr.get("body", ""),
                "state": pr.get("state", "UNKNOWN"),
                "draft": pr.get("isDraft", False),
                "merge_state": pr.get("mergeable"),
                "labels": ",".join(label_names),
                "base_branch": pr.get("baseRefName"),
                "head_branch": pr.get("headRefName"),
                "created_at": created_at,
                "updated_at": updated_at,
                "merged_at": merged_at,
                "closed_at": closed_at,
                "commit_count": commit_count,
                "files_changed": files_count,
                "lines_added": lines_added,
                "lines_deleted": lines_deleted,
                "review_count": reviews_count,
                "comment_count": comment_count,
                "author": author,
                "cycle_time_days": cycle_time_days,
                "wait_for_review_hours": wait_for_review_hours,
                "review_duration_hours": review_duration_hours,
                "approval_count": approval_count,
                "change_request_count": change_request_count,
                "reviewer_count": len(set(
                    r.get("author", {}).get("login") for r in reviews
                    if r and r.get("author")
                )),
                "reviews": reviews,  # raw review nodes for storage
            }
        except Exception as e:
            print(f"Error parsing PR data: {str(e)}")
            raise

    def _mock_query(self, query: str, variables: Dict = None) -> Dict:
        if not variables:
            variables = {}
        owner = variables.get("owner", "mock-owner")
        repo = variables.get("repo", "mock-repo")
        cursor = variables.get("cursor")

        if "pullRequests" in query:
            if not cursor:
                nodes = []
                now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                nodes.append({
                    "number": 150,
                    "title": "Fresh Pull Request #150",
                    "body": "This is a fresh PR to verify incremental sync.",
                    "state": "OPEN",
                    "isDraft": False,
                    "mergeable": "MERGEABLE",
                    "labels": {"nodes": [{"name": "bug"}, {"name": "frontend"}]},
                    "baseRefName": "main",
                    "headRefName": "feature-150",
                    "createdAt": now_str,
                    "updatedAt": now_str,
                    "mergedAt": None,
                    "closedAt": None,
                    "commits": {"totalCount": 3},
                    "files": {
                        "totalCount": 2,
                        "nodes": [{"additions": 10, "deletions": 5}]
                    },
                    "reviews": {
                        "totalCount": 1,
                        "nodes": [{
                            "state": "APPROVED",
                            "submittedAt": now_str,
                            "author": {"login": "reviewer1"},
                            "comments": {"totalCount": 1}
                        }]
                    },
                    "comments": {"totalCount": 2},
                    "author": {"login": "coder150"}
                })
                # PRs 149 down to 101 are old
                for num in range(149, 100, -1):
                    nodes.append({
                        "number": num,
                        "title": f"Old Pull Request #{num}",
                        "body": "This is an old PR.",
                        "state": "MERGED" if num % 2 == 0 else "CLOSED",
                        "isDraft": False,
                        "mergeable": "MERGEABLE",
                        "labels": {"nodes": [{"name": "enhancement"}]},
                        "baseRefName": "main",
                        "headRefName": f"feature-{num}",
                        "createdAt": "2020-01-01T00:00:00Z",
                        "updatedAt": "2020-01-01T00:00:00Z",
                        "mergedAt": "2020-01-02T00:00:00Z" if num % 2 == 0 else None,
                        "closedAt": "2020-01-02T00:00:00Z",
                        "commits": {"totalCount": 1},
                        "files": {
                            "totalCount": 1,
                            "nodes": [{"additions": 2, "deletions": 1}]
                        },
                        "reviews": {"totalCount": 0, "nodes": []},
                        "comments": {"totalCount": 0},
                        "author": {"login": f"user{num}"}
                    })
                return {
                    "data": {
                        "rateLimit": {"limit": 5000, "remaining": 4999, "resetAt": "2026-05-22T20:00:00Z"},
                        "repository": {
                            "pullRequests": {
                                "nodes": nodes,
                                "pageInfo": {"hasNextPage": True, "endCursor": "page1"}
                            }
                        }
                    }
                }
            elif cursor == "page1":
                # Page 2: PRs 100 down to 51
                nodes = []
                for num in range(100, 50, -1):
                    nodes.append({
                        "number": num,
                        "title": f"Old Pull Request #{num}",
                        "body": "This is an old PR.",
                        "state": "MERGED" if num % 2 == 0 else "CLOSED",
                        "isDraft": False,
                        "mergeable": "MERGEABLE",
                        "labels": {"nodes": []},
                        "baseRefName": "main",
                        "headRefName": f"feature-{num}",
                        "createdAt": "2020-01-01T00:00:00Z",
                        "updatedAt": "2020-01-01T00:00:00Z",
                        "mergedAt": "2020-01-02T00:00:00Z" if num % 2 == 0 else None,
                        "closedAt": "2020-01-02T00:00:00Z",
                        "commits": {"totalCount": 1},
                        "files": {
                            "totalCount": 1,
                            "nodes": [{"additions": 2, "deletions": 1}]
                        },
                        "reviews": {"totalCount": 0, "nodes": []},
                        "comments": {"totalCount": 0},
                        "author": {"login": f"user{num}"}
                    })
                return {
                    "data": {
                        "rateLimit": {"limit": 5000, "remaining": 4998, "resetAt": "2026-05-22T20:00:00Z"},
                        "repository": {
                            "pullRequests": {
                                "nodes": nodes,
                                "pageInfo": {"hasNextPage": True, "endCursor": "page2"}
                            }
                        }
                    }
                }
            elif cursor == "page2":
                # Page 3: PRs 50 down to 1
                nodes = []
                for num in range(50, 0, -1):
                    nodes.append({
                        "number": num,
                        "title": f"Old Pull Request #{num}",
                        "body": "This is an old PR.",
                        "state": "MERGED" if num % 2 == 0 else "CLOSED",
                        "isDraft": False,
                        "mergeable": "MERGEABLE",
                        "labels": {"nodes": []},
                        "baseRefName": "main",
                        "headRefName": f"feature-{num}",
                        "createdAt": "2020-01-01T00:00:00Z",
                        "updatedAt": "2020-01-01T00:00:00Z",
                        "mergedAt": "2020-01-02T00:00:00Z" if num % 2 == 0 else None,
                        "closedAt": "2020-01-02T00:00:00Z",
                        "commits": {"totalCount": 1},
                        "files": {
                            "totalCount": 1,
                            "nodes": [{"additions": 2, "deletions": 1}]
                        },
                        "reviews": {"totalCount": 0, "nodes": []},
                        "comments": {"totalCount": 0},
                        "author": {"login": f"user{num}"}
                    })
                return {
                    "data": {
                        "rateLimit": {"limit": 5000, "remaining": 4997, "resetAt": "2026-05-22T20:00:00Z"},
                        "repository": {
                            "pullRequests": {
                                "nodes": nodes,
                                "pageInfo": {"hasNextPage": False, "endCursor": None}
                            }
                        }
                    }
                }

        elif "hasDiscussionsEnabled" in query:
            return {
                "data": {
                    "repository": {
                        "hasDiscussionsEnabled": True,
                        "discussions": {"totalCount": 5},
                        "projectsV2": {"totalCount": 3},
                    }
                }
            }

        elif "discussions(first" in query or "discussions(first:" in query.replace(" ", ""):
            nodes = []
            for num in range(1, 6):
                nodes.append({
                    "id": f"discussion_node_{num}",
                    "number": num,
                    "title": f"Mock Discussion #{num}",
                    "body": f"Body of mock discussion {num}",
                    "category": {"name": "Q&A" if num % 2 == 0 else "General"},
                    "author": {"login": f"discuss_user_{num}"},
                    "closed": False,
                    "answer": {"id": "ans_1"} if num % 2 == 0 else None,
                    "comments": {
                        "totalCount": 2,
                        "nodes": [
                            {
                                "id": f"comment_node_{num}_1",
                                "author": {"login": f"commenter_{num}_1"},
                                "body": f"This is comment 1 on discussion {num}",
                                "reactions": {"totalCount": 1},
                                "createdAt": "2026-01-02T12:00:00Z",
                                "replies": {
                                    "totalCount": 1,
                                    "nodes": [
                                        {
                                            "id": f"reply_node_{num}_1_1",
                                            "author": {"login": f"replier_{num}_1_1"},
                                            "body": f"This is reply 1 to comment 1 on discussion {num}",
                                            "reactions": {"totalCount": 0},
                                            "createdAt": "2026-01-02T13:00:00Z"
                                        }
                                    ]
                                }
                            },
                            {
                                "id": f"comment_node_{num}_2",
                                "author": {"login": f"commenter_{num}_2"},
                                "body": f"This is comment 2 on discussion {num}",
                                "reactions": {"totalCount": 0},
                                "createdAt": "2026-01-02T12:30:00Z",
                                "replies": {
                                    "totalCount": 0,
                                    "nodes": []
                                }
                            }
                        ]
                    },
                    "reactions": {"totalCount": num},
                    "participants": {"totalCount": num + 1},
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-02T00:00:00Z"
                })
            return {
                "data": {
                    "repository": {
                        "discussions": {
                            "nodes": nodes,
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }

        elif "projectsV2" in query:
            nodes = []
            for num in range(1, 4):
                items_nodes = []
                for item_idx in range(1, 4):
                    item_type = "ISSUE" if item_idx == 1 else ("PULL_REQUEST" if item_idx == 2 else "DRAFT_ISSUE")
                    item_state = "CLOSED" if (num + item_idx) % 2 == 0 else "OPEN"
                    status_name = "Done" if item_state == "CLOSED" else ("In Progress" if item_idx == 2 else "Todo")
                    
                    items_nodes.append({
                        "id": f"item_node_{num}_{item_idx}",
                        "type": item_type,
                        "fieldValues": {
                            "nodes": [
                                {
                                    "name": status_name,
                                    "field": {
                                        "name": "Status"
                                    }
                                }
                            ]
                        },
                        "content": {
                            "title": f"Mock {item_type.replace('_', ' ').title()} {item_idx} in project {num}",
                            "body": f"Description of item {item_idx}",
                            "state": item_state,
                            "createdAt": "2026-01-01T10:00:00Z",
                            "updatedAt": "2026-01-02T11:00:00Z",
                            "assignees": {
                                "nodes": [{"login": "coder_bob"}]
                            }
                        }
                    })

                nodes.append({
                    "id": f"project_node_{num}",
                    "number": num,
                    "title": f"Mock Project v2 #{num}",
                    "shortDescription": f"Description of project {num}",
                    "closed": False,
                    "creator": {"login": "project_boss"},
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-02T00:00:00Z",
                    "items": {
                        "nodes": items_nodes,
                        "totalCount": len(items_nodes)
                    }
                })
            return {
                "data": {
                    "repository": {
                        "projectsV2": {
                            "nodes": nodes,
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }

        elif "repository" in query:
            is_private = "private" in repo.lower()
            if is_private and not self.token:
                return {"data": {"repository": None}}
            repo_payload = {
                "isPrivate": is_private,
                "name": repo,
                "owner": {"login": owner},
                "diskUsage": 12345,
                "stargazerCount": 42,
                "watchers": {"totalCount": 10},
                "primaryLanguage": {"name": "Python"},
                "defaultBranchRef": {"name": "main"},
                "description": "Mocked Repo Description",
                "homepageUrl": "https://mock.homepage.url",
                "forkCount": 15,
            }
            if "hasDiscussionsEnabled" in query:
                repo_payload["hasDiscussionsEnabled"] = True
                repo_payload["discussions"] = {"totalCount": 5}
                repo_payload["projectsV2"] = {"totalCount": 3}
            return {"data": {"repository": repo_payload}}

        return {"data": {}}


# ---------------------------------------------------------------------------
# REST API Client (new — powers all non-GraphQL modules)
# ---------------------------------------------------------------------------

class GitHubRestClient:
    """
    Full REST API client for GitHub public APIs.
    Supports:
    - Full pagination via Link header
    - Rate limit detection and automatic wait
    - Exponential backoff for transient errors
    - Optional token (works without token for public repos, higher limits with token)
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = None):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PRISM-GitHub-Intelligence/2.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.request_count = 0  # Track API requests for budget enforcement
        print(f"[AUTH AUDIT] GitHubRestClient init: token_present={bool(self.token)}")

    def get_token_scopes(self) -> Dict[str, Any]:
        """Return OAuth scopes granted to the current token (from response headers)."""
        if not self.token:
            return {"has_token": False, "scopes": [], "suggested": ["public_repo", "read:project"]}
        try:
            resp = self._get(f"{self.BASE_URL}/rate_limit")
            raw = resp.headers.get("X-OAuth-Scopes") or resp.headers.get("x-oauth-scopes") or ""
            scopes = [s.strip() for s in raw.split(",") if s.strip()]
            print(f"[Telemetry][Auth] Token scopes: {scopes or '(none reported — fine-grained PAT)'}")
            return {
                "has_token": True,
                "scopes": scopes,
                "has_project_scope": "project" in raw or "read:project" in scopes,
                "suggested": ["repo", "read:project"] if not scopes else [],
            }
        except Exception as e:
            print(f"[Telemetry][Auth] Could not read token scopes: {e}")
            return {"has_token": True, "scopes": [], "error": str(e)[:200]}

    def _handle_rate_limit(self, response: requests.Response):
        """Check rate limit headers and sleep if needed."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_at = response.headers.get("X-RateLimit-Reset")
        if remaining is not None and int(remaining) < 5:
            if reset_at:
                sleep_secs = max(1.0, float(reset_at) - time.time() + 2)
                # If token present, use full quota and wait until reset
                if self.token:
                    print(f"[REST Rate Limit] Authenticated token present — sleeping {sleep_secs:.0f}s until reset...")
                    time.sleep(sleep_secs)
                    return
                # Unauthenticated callers should receive an exception so higher-level engine can persist state and resume
                if sleep_secs > 10:
                    raise GitHubRateLimitException(
                        f"GitHub REST API rate limit near limit (remaining: {remaining}). Need to sleep {sleep_secs:.0f}s.",
                        sleep_secs=sleep_secs
                    )
                print(f"[REST Rate Limit] Near limit. Sleeping {sleep_secs:.0f}s ...")
                time.sleep(sleep_secs)

    def _get(self, url: str, params: Dict = None, max_retries: int = 3) -> requests.Response:
        """Make a GET request with retries and rate limit handling."""
        if (self.token and (self.token.startswith("mock") or self.token.startswith("github_pat_mock"))) or os.getenv("MOCK_GITHUB") == "true":
            return self._mock_get(url, params)

        backoff = 5.0
        for attempt in range(max_retries):
            try:
                self.request_count += 1
                resp = self.session.get(url, params=params, timeout=30)

                if resp.status_code in (403, 429):
                    body_text = resp.text.lower()
                    is_rate_limit = (
                        resp.status_code == 429
                        or "rate limit" in body_text
                        or "secondary" in body_text
                        or "abuse limit" in body_text
                        or "spammer" in body_text
                        or resp.headers.get("X-RateLimit-Reset") is not None
                    )
                    if is_rate_limit:
                        reset_at = resp.headers.get("X-RateLimit-Reset")
                        if reset_at:
                            sleep_secs = max(1.0, float(reset_at) - time.time() + 2)
                            if self.token:
                                print(f"[REST] Authenticated token present — sleeping {sleep_secs:.0f}s until reset...")
                                time.sleep(sleep_secs)
                                continue
                            if sleep_secs > 10:
                                raise GitHubRateLimitException(
                                    f"GitHub REST API rate limited. Need to sleep {sleep_secs:.0f}s.",
                                    sleep_secs=sleep_secs
                                )
                            print(f"[REST] Rate limited. Sleeping {sleep_secs:.0f}s ...")
                            time.sleep(sleep_secs)
                        else:
                            time.sleep(backoff)
                            backoff *= 2
                        continue
                    else:
                        raise Exception(f"403 Forbidden: Permission denied or invalid scope. Response: {resp.text[:200]}")

                if resp.status_code == 401:
                    raise Exception("Bad credentials: GitHub token invalid or expired")

                if resp.status_code == 404:
                    return resp  # Caller handles 404

                if resp.status_code in (500, 502, 503, 504):
                    if attempt == max_retries - 1:
                        raise Exception(f"GitHub REST API server error {resp.status_code}")
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                self._handle_rate_limit(resp)
                # store last rate limit info for telemetry
                try:
                    rl_limit = resp.headers.get("X-RateLimit-Limit")
                    rl_rem = resp.headers.get("X-RateLimit-Remaining")
                    rl_reset = resp.headers.get("X-RateLimit-Reset")
                    self.last_rate_limit = {
                        "limit": int(rl_limit) if rl_limit else None,
                        "remaining": int(rl_rem) if rl_rem else None,
                        "reset": float(rl_reset) if rl_reset else None,
                    }
                    
                    limit_int = int(rl_limit) if rl_limit is not None else None
                    rem_int = int(rl_rem) if rl_rem is not None else None
                    print(
                        f"[AUTH AUDIT]\n"
                        f"token_present={bool(self.token)}\n"
                        f"authenticated={bool(self.token) and limit_int is not None and limit_int > 60}\n"
                        f"rate_limit={limit_int if limit_int is not None else 'unknown'}\n"
                        f"remaining={rem_int if rem_int is not None else 'unknown'}"
                    )
                except Exception as audit_err:
                    print(f"[AUTH AUDIT] Error extracting audit info: {audit_err}")
                return resp

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise Exception("GitHub REST API timed out")
                time.sleep(backoff)
                backoff *= 2
            except requests.exceptions.ConnectionError as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Connection error to GitHub REST API: {e}")
                time.sleep(backoff)
                backoff *= 2

        raise Exception("Max retries exceeded for GitHub REST API")

    def _paginate(self, url: str, params: Dict = None) -> Generator[List[Dict], None, None]:
        """
        Full recursive paginator using Link header.
        Yields lists of items page by page.
        Continues until no 'next' link is found.
        """
        if params is None:
            params = {}
        params.setdefault("per_page", 100)

        current_url = url
        # expose next URL for callers to persist resume state
        self.last_next_url = None
        page_num = 0

        while current_url:
            page_num += 1
            resp = self._get(current_url, params if page_num == 1 else None)

            if resp.status_code == 404:
                print(f"[REST] 404 Not Found: {current_url}")
                break

            if resp.status_code != 200:
                print(f"[REST] Unexpected status {resp.status_code} for {current_url}")
                break

            items = resp.json()
            if not items:
                break

            yield items

            # Parse Link header for next page and expose it
            link_header = resp.headers.get("Link", "")
            next_url = self._parse_next_link(link_header)
            self.last_next_url = next_url
            current_url = next_url

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        """Parse the 'next' URL from a GitHub Link header."""
        if not link_header:
            return None
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                if url_part.startswith("<") and url_part.endswith(">"):
                    return url_part[1:-1]
        return None

    @staticmethod
    def _parse_last_page_from_link(link_header: str) -> Optional[int]:
        """Parse the last page number from a GitHub Link header."""
        if not link_header:
            return None
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="last"' in part:
                url_part = part.split(";")[0].strip()
                if url_part.startswith("<") and url_part.endswith(">"):
                    url = url_part[1:-1]
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(url)
                    query = parse_qs(parsed.query)
                    if "page" in query:
                        try:
                            return int(query["page"][0])
                        except Exception:
                            pass
        return None

    def get_pull_requests(self, owner: str, repo: str, state: str = "all") -> Generator[List[Dict], None, None]:
        """Paginate through pull requests using REST API."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": 100, "sort": "updated", "direction": "desc"}
        for page in self._paginate(url, params):
            yield page

    def parse_rest_pr_data(self, pr: Dict) -> Dict:
        """Parse raw REST PR data into structured format matching GraphQL format."""
        try:
            created_at_str = pr.get("created_at")
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

            updated_at_str = pr.get("updated_at")
            updated_at = None
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))

            merged_at_str = pr.get("merged_at")
            merged_at = None
            if merged_at_str:
                merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))

            closed_at_str = pr.get("closed_at")
            closed_at = None
            if closed_at_str:
                closed_at = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))

            cycle_time_days = None
            if merged_at:
                cycle_time_days = (merged_at - created_at).total_seconds() / 86400

            author = pr.get("user", {}).get("login", "unknown") if pr.get("user") else "unknown"

            state = pr.get("state", "open").upper()
            if merged_at:
                state = "MERGED"

            labels_list = pr.get("labels", [])
            label_names = [l.get("name", "") for l in labels_list if l]

            return {
                "number": pr.get("number", 0),
                "github_node_id": pr.get("node_id"),
                "title": pr.get("title", ""),
                "body": pr.get("body", ""),
                "state": state,
                "draft": pr.get("draft", False),
                "merge_state": pr.get("mergeable"),
                "labels": ",".join(label_names),
                "base_branch": pr.get("base", {}).get("ref"),
                "head_branch": pr.get("head", {}).get("ref"),
                "created_at": created_at,
                "updated_at": updated_at,
                "merged_at": merged_at,
                "closed_at": closed_at,
                "commit_count": 0,
                "files_changed": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "review_count": 0,
                "comment_count": pr.get("comments", 0),
                "author": author,
                "cycle_time_days": cycle_time_days,
                "wait_for_review_hours": None,
                "review_duration_hours": None,
                "approval_count": 0,
                "change_request_count": 0,
                "reviewer_count": 0,
                "reviews": [],
            }
        except Exception as e:
            print(f"Error parsing REST PR data: {str(e)}")
            raise

    def get_repository_estimates(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch counts of PRs, issues, forks, contributors, workflows to estimate API usage."""
        meta = self.get_repository_metadata(owner, repo)
        if not meta:
            raise Exception("Repository not found or is private (GitHub PAT required).")

        forks_count = meta.get("forks_count", 0)
        is_private = meta.get("private", False)
        stars = meta.get("stargazers_count", 0)
        description = meta.get("description")
        language = meta.get("language")

        # 2. PR count
        pr_count = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
            resp = self._get(url, params={"state": "all", "per_page": 1})
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                if link:
                    last_page = self._parse_last_page_from_link(link)
                    pr_count = last_page if last_page else len(resp.json())
                else:
                    pr_count = len(resp.json())
        except Exception as e:
            print(f"[Estimate] Error fetching PR count: {e}")

        # 3. Issues count
        total_issues_and_prs = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
            resp = self._get(url, params={"state": "all", "per_page": 1})
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                if link:
                    last_page = self._parse_last_page_from_link(link)
                    total_issues_and_prs = last_page if last_page else len(resp.json())
                else:
                    total_issues_and_prs = len(resp.json())
        except Exception as e:
            print(f"[Estimate] Error fetching issues count: {e}")

        issues_count = max(0, total_issues_and_prs - pr_count)

        # 4. Contributors count
        contributors_count = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/contributors"
            resp = self._get(url, params={"per_page": 1})
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                if link:
                    last_page = self._parse_last_page_from_link(link)
                    contributors_count = last_page if last_page else len(resp.json())
                else:
                    contributors_count = len(resp.json())
        except Exception as e:
            print(f"[Estimate] Error fetching contributors count: {e}")

        # 5. Workflows count (active definitions only)
        workflows_count = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
            resp = self._get(url, params={"per_page": 100})
            if resp.status_code == 200:
                data = resp.json()
                workflows = data.get("workflows", []) or []
                active_wfs = [w for w in workflows if isinstance(w, dict) and w.get("state") == "active"]
                workflows_count = len(active_wfs)
        except Exception as e:
            print(f"[Estimate] Error fetching workflows count: {e}")

        # 5b. Commits count
        commits_count = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"
            resp = self._get(url, params={"per_page": 1})
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                if link:
                    last_page = self._parse_last_page_from_link(link)
                    commits_count = last_page if last_page else len(resp.json())
                else:
                    commits_count = len(resp.json())
        except Exception as e:
            print(f"[Estimate] Error fetching commits count: {e}")

        # 5c. Branches count
        branches_count = 0
        try:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches"
            resp = self._get(url, params={"per_page": 1})
            if resp.status_code == 200:
                link = resp.headers.get("Link", "")
                if link:
                    last_page = self._parse_last_page_from_link(link)
                    branches_count = last_page if last_page else len(resp.json())
                else:
                    branches_count = len(resp.json())
        except Exception as e:
            print(f"[Estimate] Error fetching branches count: {e}")

        # 5d. Workflow runs count
        workflow_runs_count = 0
        if workflows_count > 0:
            try:
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"
                resp = self._get(url, params={"per_page": 1})
                if resp.status_code == 200:
                    link = resp.headers.get("Link", "")
                    if link:
                        last_page = self._parse_last_page_from_link(link)
                        workflow_runs_count = last_page if last_page else len(resp.json())
                    else:
                        workflow_runs_count = len(resp.json())
            except Exception as e:
                print(f"[Estimate] Error fetching workflow runs count: {e}")
        else:
            workflow_runs_count = 0

        # 6. Discussions count
        discussions_count = 0
        if self.token:
            try:
                gql_client = GitHubClient(token=self.token)
                features = gql_client.fetch_repository_module_features(owner, repo)
                discussions_count = features.get("discussions_total", 0)
            except Exception as e:
                print(f"[Estimate] Error fetching discussions count: {e}")

        import math
        est_prs_rest = math.ceil(pr_count / 100) + pr_count * 3
        est_issues_rest = math.ceil(issues_count / 100)
        est_forks_rest = math.ceil(forks_count / 100)
        est_workflows_rest = math.ceil((pr_count * 2) / 100)
        estimated_requests_rest = 5 + est_prs_rest + est_issues_rest + est_forks_rest + est_workflows_rest

        est_prs_pat = math.ceil(pr_count / 50) + pr_count * 2
        est_discussions_pat = math.ceil(discussions_count / 50)
        estimated_requests_pat = 6 + est_prs_pat + est_issues_rest + est_forks_rest + est_workflows_rest + est_discussions_pat
        return {
            "owner": owner,
            "repo": repo,
            "is_private": is_private,
            "stars": stars,
            "description": description,
            "language": language,
            "pr_count": pr_count,
            "issues_count": issues_count,
            "commits_count": commits_count,
            "forks_count": forks_count,
            "branches_count": branches_count,
            "contributors_count": contributors_count,
            "workflows_count": workflows_count,
            "workflow_runs_count": workflow_runs_count,
            "discussions_count": discussions_count,
            "estimated_requests_rest": estimated_requests_rest,
            "estimated_requests_pat": estimated_requests_pat,
        }

    def get_all_pages(self, url: str, params: Dict = None) -> List[Dict]:
        """Convenience method: collect all pages into a single list."""
        results = []
        for page in self._paginate(url, params):
            results.extend(page)
        return results

    # ----------------------------------------------------------------
    # Contributors
    # ----------------------------------------------------------------

    def get_contributors(self, owner: str, repo: str) -> Generator[List[Dict], None, None]:
        """Paginate through contributors using REST API."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contributors"
        params = {"per_page": 100, "anon": "true"}
        for page in self._paginate(url, params):
            yield page

    # ----------------------------------------------------------------
    # Repository Metadata
    # ----------------------------------------------------------------

    def get_repository_metadata(self, owner: str, repo: str) -> Optional[Dict]:
        """Fetch repository metadata from REST API."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        resp = self._get(url)
        if resp.status_code == 200:
            return resp.json()
        return None

    # ----------------------------------------------------------------
    # Issues (filters out PRs automatically using pull_request key)
    # ----------------------------------------------------------------

    def get_issues(self, owner: str, repo: str, since: Optional[str] = None) -> Generator[List[Dict], None, None]:
        """
        Paginate through issues.
        GitHub issues endpoint returns both issues and PRs.
        The caller is responsible for filtering: records with 'pull_request' key are PRs, not issues.
        We filter them here for convenience.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
        params = {"state": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since

        for page_items in self._paginate(url, params):
            yield page_items

    def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict]:
        """Fetch all comments for a specific issue."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        return self.get_all_pages(url)

    # ----------------------------------------------------------------
    # Branches
    # ----------------------------------------------------------------

    def get_branches(self, owner: str, repo: str) -> Generator[List[Dict], None, None]:
        """Paginate through branches."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches"
        params = {"per_page": 100}
        for page in self._paginate(url, params):
            yield page

    def get_branch_detail(self, owner: str, repo: str, branch: str) -> Optional[Dict]:
        """Get branch detail including last commit."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches/{requests.utils.quote(branch, safe='')}"
        resp = self._get(url)
        if resp.status_code == 200:
            return resp.json()
        return None

    # ----------------------------------------------------------------
    # Forks
    # ----------------------------------------------------------------

    def get_forks(self, owner: str, repo: str) -> Generator[List[Dict], None, None]:
        """Paginate through forks."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/forks"
        params = {"per_page": 100, "sort": "newest"}
        for page in self._paginate(url, params):
            yield page

    # ----------------------------------------------------------------
    # Actions / Workflows
    # ----------------------------------------------------------------

    def get_workflows(self, owner: str, repo: str) -> List[Dict]:
        """Get all workflows for a repository."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
        results = []
        for page in self._paginate(url, {"per_page": 100}):
            # Workflow list endpoint wraps in {"total_count": N, "workflows": [...]}
            if isinstance(page, dict):
                if "workflows" in page:
                    results.extend(page["workflows"])
                elif "id" in page:
                    results.append(page)
            elif isinstance(page, list):
                for item in page:
                    if isinstance(item, dict) and "workflows" in item:
                        results.extend(item["workflows"])
                    elif isinstance(item, dict) and "id" in item:
                        results.append(item)
        return results

    def _get_workflows_raw(self, owner: str, repo: str) -> List[Dict]:
        """Get workflows handling the wrapped response format."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows"
        resp = self._get(url, {"per_page": 100})
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("workflows", [])

    def get_workflow_runs(self, owner: str, repo: str, workflow_id: int = None,
                          since: Optional[str] = None) -> Generator[List[Dict], None, None]:
        """Paginate through workflow runs, optionally filtered by workflow_id."""
        if workflow_id:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"

        params = {"per_page": 100}
        if since:
            params["created"] = f">={since}"

        for page in self._paginate(url, params):
            runs = []
            if isinstance(page, dict):
                if "workflow_runs" in page:
                    runs.extend(page["workflow_runs"])
                elif "id" in page:
                    runs.append(page)
            elif isinstance(page, list):
                for item in page:
                    if isinstance(item, dict) and "workflow_runs" in item:
                        runs.extend(item["workflow_runs"])
                    elif isinstance(item, dict) and "id" in item:
                        runs.append(item)
            if runs:
                yield runs

    def get_all_workflow_runs_raw(self, owner: str, repo: str, since: Optional[str] = None) -> Generator[List[Dict], None, None]:
        """Get workflow runs handling the wrapped response format."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": 100}
        if since:
            params["created"] = f">={since}"

        current_url = url
        page_num = 0
        while current_url:
            page_num += 1
            resp = self._get(current_url, params if page_num == 1 else None)
            if resp.status_code != 200:
                break
            data = resp.json()
            runs = data.get("workflow_runs", [])
            if not runs:
                break
            yield runs
            # Parse next link
            link_header = resp.headers.get("Link", "")
            current_url = self._parse_next_link(link_header)

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict]:
        """Get all jobs for a workflow run."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        results = []
        current_url = url
        page_num = 0
        while current_url:
            page_num += 1
            resp = self._get(current_url, {"per_page": 100} if page_num == 1 else None)
            if resp.status_code != 200:
                break
            data = resp.json()
            jobs = data.get("jobs", [])
            if not jobs:
                break
            results.extend(jobs)
            link_header = resp.headers.get("Link", "")
            current_url = self._parse_next_link(link_header)
        return results

    # ----------------------------------------------------------------
    # Projects v1 (REST)
    # ----------------------------------------------------------------

    def get_projects_v1(self, owner: str, repo: str) -> List[Dict]:
        """Get classic GitHub Projects (v1) via REST API."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/projects"
        resp = self._get(url, {"per_page": 100, "state": "all"})
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 410:
            # Projects v1 gone/disabled for this repo
            return []
        return []

    def get_project_columns(self, project_id: int) -> List[Dict]:
        """Get columns for a Projects v1 project."""
        url = f"{self.BASE_URL}/projects/{project_id}/columns"
        resp = self._get(url, {"per_page": 100})
        if resp.status_code == 200:
            return resp.json()
        return []

    def get_project_cards(self, column_id: int) -> List[Dict]:
        """Get cards in a Projects v1 column."""
        url = f"{self.BASE_URL}/projects/columns/{column_id}/cards"
        return self.get_all_pages(url, {"per_page": 100})

    # ----------------------------------------------------------------
    # PR detail via REST (reviews, files, commits)
    # ----------------------------------------------------------------

    def get_pr_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get all reviews for a PR via REST."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        return self.get_all_pages(url, {"per_page": 100})

    def fetch_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """
        Fetch all changed files for a PR via REST with full pagination.
        GET /repos/{owner}/{repo}/pulls/{pr_number}/files
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        return self._fetch_pr_rest_paginated(url, owner, repo, pr_number, "files")

    def fetch_pull_request_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """
        Fetch all commits for a PR via REST with full pagination.
        GET /repos/{owner}/{repo}/pulls/{pr_number}/commits
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        return self._fetch_pr_rest_paginated(url, owner, repo, pr_number, "commits")

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Alias for fetch_pull_request_files."""
        return self.fetch_pull_request_files(owner, repo, pr_number)

    def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Alias for fetch_pull_request_commits."""
        return self.fetch_pull_request_commits(owner, repo, pr_number)

    def _fetch_pr_rest_paginated(
        self,
        url: str,
        owner: str,
        repo: str,
        pr_number: int,
        resource: str,
    ) -> List[Dict]:
        """
        Paginate a PR sub-resource (commits/files) until exhausted.
        Logs telemetry for pages processed, items fetched, and API failures.
        """
        results: List[Dict] = []
        pages_processed = 0
        params = {"per_page": 100}

        try:
            for page_items in self._paginate(url, params):
                pages_processed += 1
                if not page_items:
                    print(
                        f"[Telemetry][PR {resource}] {owner}/{repo}#{pr_number}: "
                        f"empty page {pages_processed}, stopping pagination"
                    )
                    break
                if isinstance(page_items, list):
                    results.extend(page_items)
                elif isinstance(page_items, dict):
                    results.append(page_items)
                print(
                    f"[Telemetry][PR {resource}] {owner}/{repo}#{pr_number}: "
                    f"page {pages_processed} — {len(page_items) if isinstance(page_items, list) else 1} item(s)"
                )

            print(
                f"[Telemetry][PR {resource}] {owner}/{repo}#{pr_number}: "
                f"fetched={len(results)}, pages_processed={pages_processed}"
            )
            return results

        except Exception as e:
            print(
                f"[Telemetry][PR {resource}] API failure for {owner}/{repo}#{pr_number} "
                f"after {pages_processed} page(s), fetched_so_far={len(results)}: {e}"
            )
            raise

    def _mock_get(self, url: str, params: Dict = None) -> Any:
        from urllib.parse import urlparse, parse_qs
        import re
        parsed_url = urlparse(url)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Merge params dictionary into query_params
        if params:
            for k, v in params.items():
                if v is not None:
                    query_params[k] = [str(v)]

        # If a private repository and no token, simulate 404 Not Found
        if "private" in path.lower() and not self.token:
            return MockResponse({"message": "Not Found", "documentation_url": "https://docs.github.com/rest/repos/repos#get-a-repository"}, status_code=404)

        # Extract page number
        page = 1
        if "page" in query_params:
            try:
                page = int(query_params["page"][0])
            except Exception:
                pass

        # 1. Repository metadata
        meta_match = re.match(r"^/repos/([^/]+)/([^/]+)$", path)
        if meta_match:
            owner = meta_match.group(1)
            repo = meta_match.group(2)
            if "does-not-exist" in repo.lower() or "not-exist" in repo.lower() or "not-found" in repo.lower():
                return MockResponse({"message": "Not Found"}, status_code=404)
            is_private = "private" in repo.lower()
            data = {
                "id": 987654,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "owner": {"login": owner},
                "description": "Mocked Repo via REST Description",
                "homepage": "https://mock.rest.homepage",
                "language": "Python",
                "default_branch": "main",
                "size": 54321,
                "stargazers_count": 42,
                "watchers_count": 42,
                "forks_count": 15,
                "private": is_private,
                "visibility": "private" if is_private else "public"
            }
            return MockResponse(data)

        # 2. Issues
        if path.endswith("/issues"):
            if os.getenv("MOCK_GITHUB_PRUNED") == "true":
                page = int(query_params.get("page", 1))
                if page == 1:
                    issues = []
                    for num in range(1, 11):
                        issues.append({
                            "id": 1000 + num,
                            "number": num,
                            "title": f"Mock Issue #{num}",
                            "body": f"Description for mock issue {num}",
                            "state": "open",
                            "labels": [],
                            "assignees": [],
                            "user": {"login": "reporter1"},
                            "comments": 0,
                            "created_at": "2026-05-10T12:00:00Z",
                            "updated_at": "2026-05-11T12:00:00Z",
                            "closed_at": None
                        })
                    return MockResponse(issues)
                else:
                    return MockResponse([])

            if page == 1:
                # Page 1: return 100 issues (e.g. issues 1 to 100)
                # Issue #50 is actually a PR (has 'pull_request' key)
                issues = []
                for num in range(1, 101):
                    issue = {
                        "id": 1000 + num,
                        "number": num,
                        "title": f"Mock Issue #{num}",
                        "body": f"Description for mock issue {num}",
                        "state": "closed" if num % 2 == 0 else "open",
                        "state_reason": "completed" if num % 2 == 0 else None,
                        "labels": [{"name": "bug"} if num % 5 == 0 else {"name": "enhancement"}],
                        "assignees": [{"login": "assignee1"}],
                        "user": {"login": "reporter1"},
                        "comments": num % 3,
                        "created_at": "2026-05-10T12:00:00Z",
                        "updated_at": "2026-05-11T12:00:00Z",
                        "closed_at": "2026-05-12T12:00:00Z" if num % 2 == 0 else None
                    }
                    if num == 50:
                        # Dummy issue representing a PR
                        issue["pull_request"] = {"url": "https://api.github.com/repos/mock-owner/mock-repo/pulls/50"}
                    issues.append(issue)

                next_url = f"https://api.github.com{path}?page=2"
                headers = {"Link": f'<{next_url}>; rel="next"'}
                return MockResponse(issues, headers=headers)
            elif page == 2:
                # Page 2: return 20 issues (101 to 120)
                issues = []
                for num in range(101, 121):
                    issues.append({
                        "id": 1000 + num,
                        "number": num,
                        "title": f"Mock Issue #{num}",
                        "body": f"Description for mock issue {num}",
                        "state": "open",
                        "labels": [],
                        "assignees": [],
                        "user": {"login": "reporter2"},
                        "comments": 0,
                        "created_at": "2026-05-12T12:00:00Z",
                        "updated_at": "2026-05-12T12:00:00Z",
                        "closed_at": None
                    })
                return MockResponse(issues)
            else:
                return MockResponse([])

        # 3. Branches
        if path.endswith("/branches"):
            headers = {}
            if "per_page" in query_params:
                headers = {"Link": '<https://api.github.com/repositories/123/branches?per_page=1&page=3>; rel="last"'}
            branches = [
                {
                    "name": "main",
                    "protected": True,
                    "commit": {
                        "sha": "sha_main_branch",
                        "commit": {
                            "author": {"name": "Main Dev", "date": "2026-05-20T12:00:00Z"},
                            "message": "Production commit on main"
                        }
                    }
                },
                {
                    "name": "develop",
                    "protected": False,
                    "commit": {
                        "sha": "sha_develop_branch",
                        "commit": {
                            "author": {"name": "Develop Dev", "date": "2026-05-18T12:00:00Z"},
                            "message": "Dev commit on develop"
                        }
                    }
                },
                {
                    "name": "stale-branch",
                    "protected": False,
                    "commit": {
                        "sha": "sha_stale_branch",
                        "commit": {
                            "author": {"name": "Stale Dev", "date": "2020-01-01T12:00:00Z"},
                            "message": "Old commit on stale branch"
                        }
                    }
                }
            ]
            if os.getenv("MOCK_GITHUB_PRUNED") == "true":
                branches = [b for b in branches if b["name"] != "stale-branch"]
            return MockResponse(branches, headers=headers)

        # 3b. Branch Detail
        branch_detail_match = re.match(r"^/repos/([^/]+)/([^/]+)/branches/([^/]+)$", path)
        if branch_detail_match:
            branch_name = branch_detail_match.group(3)
            commit_shas = {
                "main": "sha_main_branch",
                "develop": "sha_develop_branch",
                "stale-branch": "sha_stale_branch"
            }
            commit_authors = {
                "main": "Main Dev",
                "develop": "Develop Dev",
                "stale-branch": "Stale Dev"
            }
            dates = {
                "main": "2026-05-20T12:00:00Z",
                "develop": "2026-05-18T12:00:00Z",
                "stale-branch": "2020-01-01T12:00:00Z"
            }
            messages = {
                "main": "Production commit on main",
                "develop": "Dev commit on develop",
                "stale-branch": "Old commit on stale branch"
            }
            if branch_name in commit_shas:
                return MockResponse({
                    "name": branch_name,
                    "protected": branch_name == "main",
                    "commit": {
                        "sha": commit_shas[branch_name],
                        "commit": {
                            "author": {"name": commit_authors[branch_name], "date": dates[branch_name]},
                            "message": messages[branch_name]
                        }
                    }
                })
            return MockResponse({}, status_code=404)

        # 4. Forks
        if path.endswith("/forks"):
            forks = [
                {
                    "id": 88801,
                    "full_name": "forker1/mock-repo",
                    "owner": {"login": "forker1"},
                    "name": "mock-repo",
                    "stargazers_count": 5,
                    "forks_count": 0,
                    "open_issues_count": 1,
                    "description": "Fork number 1",
                    "language": "Python",
                    "created_at": "2026-05-15T12:00:00Z",
                    "updated_at": "2026-05-16T12:00:00Z",
                    "pushed_at": "2026-05-17T12:00:00Z"
                },
                {
                    "id": 88802,
                    "full_name": "forker2/mock-repo",
                    "owner": {"login": "forker2"},
                    "name": "mock-repo",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "description": "Fork number 2",
                    "language": "Python",
                    "created_at": "2026-05-16T12:00:00Z",
                    "updated_at": "2026-05-16T12:00:00Z",
                    "pushed_at": "2020-01-01T12:00:00Z"
                }
            ]
            if os.getenv("MOCK_GITHUB_PRUNED") == "true":
                forks = [f for f in forks if f["id"] != 88802]
            return MockResponse(forks)

        # 5. Workflows
        if path.endswith("/actions/workflows"):
            workflows = {
                "total_count": 1,
                "workflows": [
                    {
                        "id": 12345,
                        "name": "CI Workflow",
                        "path": ".github/workflows/ci.yml",
                        "state": "active",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z"
                    }
                ]
            }
            return MockResponse(workflows)

        # 6. Workflow Runs
        if "/actions/runs" in path or "/actions/workflows/" in path:
            headers = {}
            if "per_page" in query_params:
                headers = {"Link": '<https://api.github.com/repositories/123/actions/runs?per_page=1&page=2>; rel="last"'}
            is_incremental = "created" in query_params or os.getenv("MOCK_GITHUB_INCREMENTAL") == "true"
            runs = [
                {
                    "id": 99991,
                    "workflow_id": 12345,
                    "name": "CI Workflow Run 1",
                    "head_branch": "main",
                    "head_sha": "sha_main",
                    "event": "push",
                    "status": "completed",
                    "conclusion": "success",
                    "run_number": 1,
                    "run_attempt": 1,
                    "actor": {"login": "workflow_actor"},
                    "created_at": "2026-05-20T12:00:00Z",
                    "updated_at": "2026-05-20T12:10:00Z",
                    "run_started_at": "2026-05-20T12:00:00Z"
                }
            ]
            if not is_incremental:
                runs.append({
                    "id": 99992,
                    "workflow_id": 12345,
                    "name": "CI Workflow Run 2",
                    "head_branch": "develop",
                    "head_sha": "sha_develop",
                    "event": "push",
                    "status": "completed",
                    "conclusion": "failure",
                    "run_number": 2,
                    "run_attempt": 1,
                    "actor": {"login": "workflow_actor"},
                    "created_at": "2026-05-18T12:00:00Z",
                    "updated_at": "2026-05-18T12:15:00Z",
                    "run_started_at": "2026-05-18T12:00:00Z"
                })
            data = {
                "total_count": len(runs),
                "workflow_runs": runs
            }
            return MockResponse(data, headers=headers)

        # 7. Workflow Jobs
        if path.endswith("/jobs") and "/actions/runs/" in path:
            jobs = {
                "total_count": 1,
                "jobs": [
                    {
                        "id": 77771,
                        "name": "build-and-test",
                        "status": "completed",
                        "conclusion": "success",
                        "runner_name": "GitHub-Hosted Runner",
                        "started_at": "2026-05-20T12:01:00Z",
                        "completed_at": "2026-05-20T12:09:00Z"
                    }
                ]
            }
            return MockResponse(jobs)

        # 8. Projects v1
        if path.endswith("/projects"):
            return MockResponse([])

        # 9. PR commits
        commits_match = re.match(
            r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)/commits$", path
        )
        if commits_match:
            pr_num = int(commits_match.group(3))
            mock_commits = [
                {
                    "sha": f"mock_commit_{pr_num}_1",
                    "commit": {
                        "message": f"Mock commit 1 for PR #{pr_num}",
                        "author": {"name": "mock_author", "date": "2026-05-20T12:00:00Z"},
                    },
                },
                {
                    "sha": f"mock_commit_{pr_num}_2",
                    "commit": {
                        "message": f"Mock commit 2 for PR #{pr_num}",
                        "author": {"name": "mock_author", "date": "2026-05-20T13:00:00Z"},
                    },
                },
            ]
            return MockResponse(mock_commits)

        # 10. PR files
        files_match = re.match(
            r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)/files$", path
        )
        if files_match:
            pr_num = int(files_match.group(3))
            mock_files = [
                {
                    "filename": f"src/module_{pr_num}.py",
                    "status": "modified",
                    "additions": 42,
                    "deletions": 7,
                    "changes": 49,
                    "patch": "@@ mock diff @@",
                },
                {
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 3,
                    "deletions": 1,
                    "changes": 4,
                },
            ]
            return MockResponse(mock_files)

        if path.endswith("/pulls"):
            headers = {}
            if "large" in path.lower():
                headers = {"Link": '<https://api.github.com/repositories/123/pulls?per_page=1&page=500>; rel="last"'}
            mock_prs = [
                {
                    "number": 1,
                    "node_id": "mock_node_1",
                    "title": "Mock Pull Request #1",
                    "body": "Body of mock PR 1",
                    "state": "open",
                    "draft": False,
                    "labels": [{"name": "bug"}],
                    "base": {"ref": "main"},
                    "head": {"ref": "feature-1"},
                    "created_at": "2026-05-20T12:00:00Z",
                    "updated_at": "2026-05-20T12:00:00Z",
                    "merged_at": None,
                    "closed_at": None,
                    "user": {"login": "coder1"},
                    "comments": 2
                },
                {
                    "number": 2,
                    "node_id": "mock_node_2",
                    "title": "Mock Pull Request #2",
                    "body": "Body of mock PR 2",
                    "state": "closed",
                    "draft": False,
                    "labels": [],
                    "base": {"ref": "main"},
                    "head": {"ref": "feature-2"},
                    "created_at": "2026-05-18T12:00:00Z",
                    "updated_at": "2026-05-19T12:00:00Z",
                    "merged_at": "2026-05-19T12:00:00Z",
                    "closed_at": "2026-05-19T12:00:00Z",
                    "user": {"login": "coder2"},
                    "comments": 1
                }
            ]
            return MockResponse(mock_prs, headers=headers)

        # Mock repository commits
        repo_commits_match = re.match(
            r"^/repos/([^/]+)/([^/]+)/commits$", path
        )
        if repo_commits_match:
            headers = {}
            if "per_page" in query_params:
                headers = {"Link": '<https://api.github.com/repositories/123/commits?per_page=1&page=150>; rel="last"'}
            mock_commits = [{"sha": "mock_sha_1", "commit": {"message": "Initial commit"}}]
            return MockResponse(mock_commits, headers=headers)

        # Mock repository contributors
        contributors_match = re.match(
            r"^/repos/([^/]+)/([^/]+)/contributors$", path
        )
        if contributors_match:
            owner = contributors_match.group(1)
            repo = contributors_match.group(2)
            headers = {}
            if "large" in repo.lower():
                # 120 contributors split across 2 pages
                if page == 1:
                    mock_contributors = []
                    for num in range(1, 101):
                        mock_contributors.append({
                            "login": f"contrib_large_{num}",
                            "id": 9200 + num,
                            "contributions": 150 - num,
                            "type": "User"
                        })
                    next_url = f"https://api.github.com{path}?page=2"
                    headers = {"Link": f'<{next_url}>; rel="next"'}
                    return MockResponse(mock_contributors, headers=headers)
                elif page == 2:
                    mock_contributors = []
                    for num in range(101, 121):
                        mock_contributors.append({
                            "login": f"contrib_large_{num}",
                            "id": 9200 + num,
                            "contributions": 150 - num,
                            "type": "User"
                        })
                    return MockResponse(mock_contributors, headers=headers)
                else:
                    return MockResponse([])
            elif "small" in repo.lower():
                # 2 contributors
                mock_contributors = [
                    {"login": "contrib_small_1", "id": 9001, "contributions": 12, "type": "User"},
                    {"login": "contrib_small_2", "id": 9002, "contributions": 5, "type": "User"}
                ]
                return MockResponse(mock_contributors)
            else:
                # Medium/default repository (5 contributors, including bots, deleted users, and anonymous)
                mock_contributors = [
                    {"login": "contrib_med_1", "id": 9101, "contributions": 25, "type": "User"},
                    {"login": "dependabot[bot]", "id": 49699333, "contributions": 8, "type": "Bot"},
                    {"login": "ghost", "id": 10137, "contributions": 2, "type": "User"},
                    {"login": "contrib_med_2", "id": 9102, "contributions": 1, "type": "User"},
                ]
                if query_params.get("anon") == ["true"] or query_params.get("anon") == ["1"]:
                    mock_contributors.append({
                        "name": "Anon Contrib",
                        "email": "anon@contrib.com",
                        "contributions": 4,
                        "type": "Anonymous"
                    })
                return MockResponse(mock_contributors)

        if "/pulls/" in path:
            return MockResponse([])

        return MockResponse({}, status_code=404)