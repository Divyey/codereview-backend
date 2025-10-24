import openai
import logging
from typing import Dict, Any, List
from ..core.config import settings

class AIService:
    MAX_FILES = getattr(settings, "AI_MAX_FILES", 5)
    MAX_CONTENT_LEN = getattr(settings, "AI_MAX_CONTENT_LEN", 1000)
    VALID_SEVERITIES = {"low", "medium", "high", "critical"}

    def __init__(self, model_name: str = None):
        self.model_name = model_name or getattr(settings, "OPENAI_MODEL_NAME", "gpt-4o")
        try:
            self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.async_mode = True
        except AttributeError:
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            self.async_mode = False

    async def analyze_code(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze code files and return a structured AI review for your DB and UI.
        """
        file_summaries = []
        for file in files[:self.MAX_FILES]:
            content_preview = (file.get("content") or "")[:self.MAX_CONTENT_LEN]
            file_summaries.append(
                f"Filename: {file.get('filename', 'unknown')}\n"
                f"Additions: {file.get('additions', 0)}, Deletions: {file.get('deletions', 0)}\n"
                f"Content Preview:\n{content_preview}\n"
            )

        prompt = (
            "You are an expert code review AI, trusted to help organizations maintain high code quality, security, and documentation standards. "
            "Analyze the following code changes and reply in strict JSON with these fields:\n"
            "- ai_score: float (1.0-10.0, reflecting overall code quality and adherence to best practices)\n"
            "- risk_level: string (low, medium, high, critical; only use these values)\n"
            "- issue_count: int (number of critical issues found)\n"
            "- warning_count: int (number of non-critical warnings)\n"
            "- issues: list of {type, severity, message, file, line} (severity: low, medium, high, critical; only use these)\n"
            "- warnings: list of {type, severity, message, suggestion} (severity: low, medium, high, critical; only use these)\n"
            "- recommendations: list of actionable suggestions to improve code quality, security, or documentation\n"
            "- summary: a concise, professional summary (2-4 sentences) that highlights key findings, risks, and next steps. "
            "Make the summary actionable, standards-driven, and suitable for sharing with a dev team.\n"
            "Example output:\n"
            "{\n"
            '  "ai_score": 8.5,\n'
            '  "risk_level": "medium",\n'
            '  "issue_count": 1,\n'
            '  "warning_count": 2,\n'
            '  "issues": [\n'
            '    {"type": "security", "severity": "high", "message": "Potential SQL injection", "file": "api.py", "line": 42}\n'
            '  ],\n'
            '  "warnings": [\n'
            '    {"type": "style", "severity": "low", "message": "Line too long", "suggestion": "Break into multiple lines"}\n'
            '  ],\n'
            '  "recommendations": ["Add input validation", "Improve function naming"],\n'
            '  "summary": "The code is generally well-structured, but contains a high-severity security risk. Address the recommendations before merging."\n'
            "}\n"
            "Valid severities: low, medium, high, critical. Only use these. "
            "If a security/validation/authentication check is implemented in a helper function and called/enforced in the endpoint, do not flag it as missing."
            "\nCode changes:\n" + "\n".join(file_summaries)
        )

        try:
            if self.async_mode:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert code review AI."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1200,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert code review AI."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1200,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
            ai_message = response.choices[0].message.content
            import json
            analysis = json.loads(ai_message)

            # Normalize and validate output
            for issue in analysis.get("issues", []):
                issue["severity"] = str(issue.get("severity", "")).lower()
                if issue["severity"] not in self.VALID_SEVERITIES:
                    issue["severity"] = "medium"
            for warning in analysis.get("warnings", []):
                warning["severity"] = str(warning.get("severity", "")).lower()
                if warning["severity"] not in self.VALID_SEVERITIES:
                    warning["severity"] = "medium"

            return {
                "ai_score": analysis.get("ai_score"),
                "risk_level": analysis.get("risk_level"),
                "issue_count": analysis.get("issue_count"),
                "warning_count": analysis.get("warning_count"),
                "issues": analysis.get("issues", []),
                "warnings": analysis.get("warnings", []),
                "recommendations": analysis.get("recommendations", []),
                "summary": analysis.get("summary", "")
            }
        except Exception as e:
            logging.error(f"OpenAI analysis failed: {e}")
            return {
                "ai_score": 7.5,
                "risk_level": "medium",
                "issue_count": 0,
                "warning_count": 1,
                "issues": [],
                "warnings": [{
                    "type": "complexity",
                    "severity": "medium",
                    "message": "Large number of files changed - consider breaking into smaller PRs",
                    "suggestion": "Split this PR into smaller, focused changes"
                }],
                "recommendations": [
                    "Add unit tests for new functionality",
                    "Consider adding documentation for complex logic",
                    "Review error handling in critical paths"
                ],
                "summary": f"Code quality analysis failed (mocked). Error: {str(e)}"
            }

    def get_language_from_filename(self, filename: str) -> str:
        extension_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".jsx": "javascript", ".java": "java",
            ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".php": "php",
            ".rb": "ruby", ".go": "go", ".rs": "rust", ".swift": "swift",
            ".kt": "kotlin", ".scala": "scala", ".html": "html", ".css": "css",
            ".scss": "scss", ".json": "json", ".xml": "xml", ".yaml": "yaml",
            ".yml": "yaml", ".md": "markdown", ".sql": "sql"
        }
        for ext, lang in extension_map.items():
            if filename.lower().endswith(ext):
                return lang
        return "text"
