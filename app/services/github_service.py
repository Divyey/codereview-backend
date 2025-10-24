import httpx
import base64
import logging
from fastapi import HTTPException
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from ..core.config import settings

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self, token: Optional[str] = None):
        self.default_token = settings.GITHUB_TOKEN
        self.token = token or self.default_token
        self.base_url = "https://api.github.com"
        self.base_headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeReviewPro/1.0"
        }
        self.headers = self.base_headers.copy()
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.timeout = httpx.Timeout(30.0)  # Set a longer timeout for all requests

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
            except httpx.ConnectTimeout:
                raise HTTPException(status_code=504, detail="GitHub API timed out")
            if response.status_code == 401 and self.token != self.default_token:
                fallback_headers = self.base_headers.copy()
                fallback_headers["Authorization"] = f"token {self.default_token}"
                response = await client.get(url, headers=fallback_headers)
            if response.status_code == 401:
                response = await client.get(url, headers=self.base_headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="GitHub: PR not found or access denied")
            elif response.status_code == 403:
                msg = "GitHub: Forbidden (rate limit or insufficient token scope)"
                if "X-RateLimit-Remaining" in response.headers and response.headers["X-RateLimit-Remaining"] == "0":
                    msg = "GitHub: Rate limit exceeded"
                raise HTTPException(status_code=403, detail=msg)
            elif response.status_code == 401:
                raise HTTPException(status_code=401, detail="GitHub: Unauthorized (invalid or expired token)")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
            except httpx.ConnectTimeout:
                raise HTTPException(status_code=504, detail="GitHub API timed out")
            if response.status_code == 401 and self.token != self.default_token:
                fallback_headers = self.base_headers.copy()
                fallback_headers["Authorization"] = f"token {self.default_token}"
                response = await client.get(url, headers=fallback_headers)
            if response.status_code == 401:
                response = await client.get(url, headers=self.base_headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="GitHub: PR files not found or access denied")
            elif response.status_code == 403:
                raise HTTPException(status_code=403, detail="GitHub: Forbidden (rate limit or insufficient token scope)")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> Optional[str]:
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers, params={"ref": ref})
            except httpx.ConnectTimeout:
                raise HTTPException(status_code=504, detail="GitHub API timed out")
            if response.status_code == 401 and self.token != self.default_token:
                fallback_headers = self.base_headers.copy()
                fallback_headers["Authorization"] = f"token {self.default_token}"
                response = await client.get(url, headers=fallback_headers, params={"ref": ref})
            if response.status_code == 401:
                response = await client.get(url, headers=self.base_headers, params={"ref": ref})
            if response.status_code == 200:
                content_data = response.json()
                if content_data.get("encoding") == "base64":
                    raw = base64.b64decode(content_data["content"])
                    try:
                        # Try to decode as UTF-8 text
                        return raw.decode("utf-8")
                    except UnicodeDecodeError:
                        logger.warning(f"Binary file encountered: {path}. Skipping content decoding.")
                        # It's a binary file, return None or handle as needed
                        return None
                return content_data.get("content")
            elif response.status_code == 404:
                return None  # File may be deleted in PR
            else:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")


    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        url = f"{self.base_url}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
            except httpx.ConnectTimeout:
                raise HTTPException(status_code=504, detail="GitHub API timed out")
            if response.status_code == 401 and self.token != self.default_token:
                fallback_headers = self.base_headers.copy()
                fallback_headers["Authorization"] = f"token {self.default_token}"
                response = await client.get(url, headers=fallback_headers)
            if response.status_code == 401:
                response = await client.get(url, headers=self.base_headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="GitHub: Repository not found or access denied")
            elif response.status_code == 403:
                raise HTTPException(status_code=403, detail="GitHub: Forbidden (rate limit or insufficient token scope)")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")

    def parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        try:
            parsed = urlparse(url)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 4 and parts[-2] == "pull":
                return {
                    "owner": parts[0],
                    "repo": parts[1],
                    "pr_number": int(parts[3])
                }
            return None
        except Exception:
            return None

    async def get_pull_requests(self, owner: str, repo: str, state: str = "open") -> list:
        """
        Fetch all pull requests for a repo. State can be "open", "closed", or "all".
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": 100}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
            except httpx.ConnectTimeout:
                raise HTTPException(status_code=504, detail="GitHub API timed out")
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="GitHub: PRs not found or access denied")
            elif response.status_code == 403:
                raise HTTPException(status_code=403, detail="GitHub: Forbidden (rate limit or insufficient token scope)")
            else:
                raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.text}")
