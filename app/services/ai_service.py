import openai
import logging
from typing import Dict, Any, List
from ..core.config import settings

class AIService:
    MAX_FILES = getattr(settings, "AI_MAX_FILES", 10)  # Increased for better analysis
    MAX_CONTENT_LEN = getattr(settings, "AI_MAX_CONTENT_LEN", 2000)  # Increased for better context
    VALID_SEVERITIES = {"low", "medium", "high", "critical"}
    VALID_CATEGORIES = {"security", "performance", "quality", "scalability", "maintainability", "architecture"}

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
        Enterprise-grade code analysis with comprehensive quality metrics.
        """
        # Enhanced file analysis with context
        max_files = min(len(files), self.MAX_FILES)
        file_summaries = []
        total_additions = 0
        total_deletions = 0
        file_types = {}
        
        for file in files[:max_files]:
            content_preview = (file.get("content") or "")[:self.MAX_CONTENT_LEN]
            additions = file.get('additions', 0)
            deletions = file.get('deletions', 0)
            total_additions += additions
            total_deletions += deletions
            
            # Track file types for context
            filename = file.get('filename', 'unknown')
            ext = filename.split('.')[-1] if '.' in filename else 'unknown'
            file_types[ext] = file_types.get(ext, 0) + 1
            
            file_summaries.append(
                f"File: {filename}\n"
                f"Changes: +{additions}/-{deletions}\n"
                f"Status: {file.get('status', 'modified')}\n"
                f"Language: {self.get_language_from_filename(filename)}\n"
                f"Code Preview:\n{content_preview}\n"
                f"{'='*60}\n"
            )

        # Build enterprise-grade prompt with context
        file_types_summary = ', '.join([f"{v} {k}" for k, v in file_types.items()])
        
        prompt = f"""You are an elite Senior Staff Engineer and Code Reviewer at a Fortune 500 company, with 15+ years of experience in software architecture, security, and code quality standards.

**Your Mission**: Perform a comprehensive, production-ready code review that meets enterprise standards (OWASP, CWE, SOLID principles, clean code, performance, scalability).

**Context**:
- Total Changes: +{total_additions}/-{total_deletions} lines
- Files Modified: {len(files[:max_files])} ({file_types_summary})
- Review Standard: Enterprise-grade (suitable for financial/healthcare/critical systems)

**Evaluation Criteria** (Weight each appropriately):

1. **Security (25%)**: SQL injection, XSS, CSRF, authentication/authorization flaws, secrets exposure, input validation, API security, dependency vulnerabilities
2. **Code Quality (20%)**: Readability, naming conventions, function length, complexity, DRY principle, SOLID principles, design patterns
3. **Performance (15%)**: Algorithmic complexity, N+1 queries, memory leaks, database optimization, caching strategies, resource management
4. **Scalability (10%)**: Horizontal/vertical scaling concerns, bottlenecks, concurrent processing, distributed systems considerations
5. **Maintainability (15%)**: Documentation, test coverage, error handling, logging, debugging ease, code organization
6. **Best Practices (10%)**: Language-specific idioms, framework conventions, API design, REST principles, error codes
7. **Architecture (5%)**: Separation of concerns, modularity, coupling, cohesion, technical debt

**Required Output** (strict JSON format):

{{
  "ai_score": <float 1.0-10.0>,
  "risk_level": "<low|medium|high|critical>",
  "confidence_score": <float 0.0-1.0>,
  "review_summary": {{
    "overall_assessment": "<2-3 sentence executive summary>",
    "strengths": ["<list 2-3 positive aspects>"],
    "critical_concerns": ["<list any blocking issues>"],
    "recommended_action": "<approve|approve_with_suggestions|request_changes|reject>"
  }},
  "metrics": {{
    "complexity_score": <int 1-10>,
    "maintainability_index": <float 0.0-100.0>,
    "security_score": <int 1-10>,
    "performance_score": <int 1-10>,
    "test_coverage_concern": <bool>
  }},
  "issue_count": <int>,
  "warning_count": <int>,
  "issues": [
    {{
      "id": "<unique_id>",
      "category": "<security|performance|quality|scalability|maintainability|architecture>",
      "type": "<specific_type>",
      "severity": "<critical|high|medium|low>",
      "title": "<concise_title>",
      "description": "<detailed_explanation>",
      "file": "<filename>",
      "line": <int> or {{"start": <int>, "end": <int>}} or null,
      "code_snippet": "<optional>",
      "impact": "<business_impact>",
      "remediation": "<specific_fix_steps>",
      "references": ["<CWE-ID or OWASP link or documentation>"]
    }}
  ],
  "warnings": [
    {{
      "type": "<type>",
      "severity": "<low|medium>",
      "message": "<description>",
      "suggestion": "<actionable_fix>",
      "file": "<filename>",
      "line": <int> or {{"start": <int>, "end": <int>}} or null
    }}
  ],
  "recommendations": [
    {{
      "priority": "<high|medium|low>",
      "category": "<category>",
      "recommendation": "<specific_action>",
      "rationale": "<why_this_matters>",
      "effort": "<hours_estimate>"
    }}
  ],
  "security_findings": {{
    "vulnerabilities_found": <int>,
    "owasp_categories": ["<list_applicable>"],
    "cwe_ids": ["<list_if_applicable>"],
    "requires_security_review": <bool>
  }},
  "technical_debt": {{
    "estimated_hours": <float>,
    "priority": "<high|medium|low>",
    "debt_items": ["<list>"]
  }},
  "summary": "<Professional 3-4 sentence summary suitable for sharing with team leads and product managers. Include key risks, recommendations, and approval status.>"
}}

**Critical Rules**:
1. **ONLY** use severity values: "critical", "high", "medium", "low"
2. Be **specific** and **actionable** - avoid generic advice
3. If security/validation is implemented correctly (even in helper functions), **DO NOT** flag as missing
4. Consider the **entire context** - don't nitpick on minor style if core logic is sound
5. **Balance** being thorough with being practical - focus on what truly matters
6. Provide **concrete code examples** in remediation when possible
7. Reference **industry standards** (OWASP, CWE, PEP, etc.) where applicable
8. Score fairly: 8+ for good code, 6-7 for acceptable, <6 for needs work
9. **Line numbers**: For issues spanning multiple lines, use {{"start": X, "end": Y}} format. For single-line issues, use integer. If line number is unknown or not applicable, use null.

**Code Changes to Review:**

""" + "\n".join(file_summaries)

        try:
            if self.async_mode:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are an expert code review AI."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,  # Increased for comprehensive analysis
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
                    max_tokens=2000,  # Increased for comprehensive analysis
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
            ai_message = response.choices[0].message.content
            import json
            analysis = json.loads(ai_message)

            # Enhanced validation and normalization
            for issue in analysis.get("issues", []):
                issue["severity"] = str(issue.get("severity", "")).lower()
                if issue["severity"] not in self.VALID_SEVERITIES:
                    issue["severity"] = "medium"
                # Validate category
                category = str(issue.get("category", "")).lower()
                if category not in self.VALID_CATEGORIES:
                    issue["category"] = "quality"
                    
            for warning in analysis.get("warnings", []):
                warning["severity"] = str(warning.get("severity", "")).lower()
                if warning["severity"] not in self.VALID_SEVERITIES:
                    warning["severity"] = "medium"

            # Ensure risk_level is valid
            risk_level = str(analysis.get("risk_level", "")).lower()
            if risk_level not in self.VALID_SEVERITIES:
                risk_level = "medium"

            return {
                "ai_score": analysis.get("ai_score", 7.5),
                "risk_level": risk_level,
                "confidence_score": analysis.get("confidence_score", 0.8),
                "review_summary": analysis.get("review_summary", {}),
                "metrics": analysis.get("metrics", {}),
                "issue_count": analysis.get("issue_count", 0),
                "warning_count": analysis.get("warning_count", 0),
                "issues": analysis.get("issues", []),
                "warnings": analysis.get("warnings", []),
                "recommendations": analysis.get("recommendations", []),
                "security_findings": analysis.get("security_findings", {}),
                "technical_debt": analysis.get("technical_debt", {}),
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
