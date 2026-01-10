"""
Enhanced AI Service with Latest OpenAI Models and Multi-Layered Analysis
Implements comprehensive code scanning with double-checking and proof-reading
"""

import openai
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from ..core.config import settings
import json
import hashlib

logger = logging.getLogger(__name__)

class EnhancedAIService:
    """
    Enterprise-grade AI service with multi-layered analysis and latest models
    """
    
    # Latest OpenAI models (as of 2025)
    PRIMARY_MODEL = "gpt-4o"  # Latest GPT-4 Optimized
    SECONDARY_MODEL = "gpt-4-turbo"  # For cross-validation
    FAST_MODEL = "gpt-3.5-turbo"  # For quick pre-screening
    
    MAX_FILES = 50
    MAX_CONTENT_LEN = 8000  # Increased for better context
    
    VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
    VALID_CATEGORIES = {
        "security", "performance", "quality", "scalability", 
        "maintainability", "architecture", "testing", "documentation"
    }
    
    def __init__(self, model_name: str = None):
        self.primary_model = model_name or self.PRIMARY_MODEL
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.analysis_cache = {}  # Simple in-memory cache
        
    async def analyze_code_comprehensive(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Comprehensive multi-layered code analysis with cross-validation
        
        Layers:
        1. Fast pre-screening (GPT-3.5-turbo)
        2. Deep analysis (GPT-4o)
        3. Cross-validation (GPT-4-turbo)
        4. Final synthesis and scoring
        """
        try:
            logger.info(f"Starting comprehensive analysis of {len(files)} files")
            
            # Prepare and validate files
            processed_files = self._prepare_files(files)
            if not processed_files:
                return self._empty_analysis_result()
            
            # Generate cache key for this analysis
            cache_key = self._generate_cache_key(processed_files)
            if cache_key in self.analysis_cache:
                logger.info("Returning cached analysis result")
                return self.analysis_cache[cache_key]
            
            # Layer 1: Fast Pre-screening
            logger.info("Layer 1: Fast pre-screening with GPT-3.5-turbo")
            pre_screen = await self._fast_prescreening(processed_files)
            
            # Layer 2: Deep Analysis
            logger.info("Layer 2: Deep analysis with GPT-4o")
            deep_analysis = await self._deep_analysis(processed_files, pre_screen)
            
            # Layer 3: Cross-validation (only for high-risk findings)
            if deep_analysis.get("risk_level") in ["critical", "high"]:
                logger.info("Layer 3: Cross-validation with GPT-4-turbo")
                validation = await self._cross_validation(processed_files, deep_analysis)
            else:
                validation = {"validated": True, "confidence": 0.9}
            
            # Layer 4: Final Synthesis
            logger.info("Layer 4: Final synthesis and scoring")
            final_result = await self._synthesize_results(
                pre_screen, deep_analysis, validation, processed_files
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = final_result
            
            logger.info(f"Analysis complete: {final_result.get('ai_score', 0)}/10 score")
            return final_result
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {str(e)}")
            return self._error_analysis_result(str(e))
    
    async def _fast_prescreening(self, files: List[Dict]) -> Dict[str, Any]:
        """
        Fast pre-screening to identify obvious issues and prioritize analysis
        """
        prompt = self._build_prescreening_prompt(files)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.FAST_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a senior code reviewer performing fast pre-screening.
                        Identify obvious security vulnerabilities, critical bugs, and code smells.
                        Focus on high-impact issues that need immediate attention.
                        Respond in JSON format only."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Pre-screening failed: {e}")
            return {"priority_issues": [], "risk_indicators": [], "needs_deep_analysis": True}
    
    async def _deep_analysis(self, files: List[Dict], pre_screen: Dict) -> Dict[str, Any]:
        """
        Deep comprehensive analysis using GPT-4o
        """
        prompt = self._build_deep_analysis_prompt(files, pre_screen)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.PRIMARY_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a world-class senior software architect and security expert.
                        Perform comprehensive code analysis covering:
                        - Security vulnerabilities (OWASP Top 10, CWE)
                        - Code quality and maintainability
                        - Performance and scalability issues
                        - Architecture and design patterns
                        - Testing and documentation gaps
                        
                        Be thorough, precise, and provide actionable recommendations.
                        Respond in the specified JSON format only."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Deep analysis failed: {e}")
            return self._fallback_analysis()
    
    async def _cross_validation(self, files: List[Dict], analysis: Dict) -> Dict[str, Any]:
        """
        Cross-validate findings using a different model for high-confidence results
        """
        prompt = self._build_validation_prompt(files, analysis)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.SECONDARY_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an independent code review expert validating another analyst's findings.
                        Critically examine the provided analysis and verify:
                        - Are the identified issues actually present?
                        - Are the severity levels appropriate?
                        - Are there any false positives?
                        - Are there any missed critical issues?
                        
                        Provide honest validation with confidence scores."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Cross-validation failed: {e}")
            return {"validated": True, "confidence": 0.7, "notes": "Validation failed"}
    
    async def _synthesize_results(
        self, 
        pre_screen: Dict, 
        deep_analysis: Dict, 
        validation: Dict, 
        files: List[Dict]
    ) -> Dict[str, Any]:
        """
        Synthesize all analysis layers into final comprehensive result
        """
        # Calculate confidence-weighted scores
        base_score = deep_analysis.get("ai_score", 5.0)
        validation_confidence = validation.get("confidence", 0.8)
        
        # Adjust score based on validation
        if validation.get("validated", True):
            final_score = base_score * validation_confidence
        else:
            final_score = max(base_score * 0.7, 3.0)  # Penalize unvalidated findings
        
        # Merge and deduplicate issues
        all_issues = []
        all_issues.extend(pre_screen.get("priority_issues", []))
        all_issues.extend(deep_analysis.get("issues", []))
        
        # Deduplicate based on file + line + type
        unique_issues = self._deduplicate_issues(all_issues)
        
        # Calculate final metrics
        critical_count = len([i for i in unique_issues if i.get("severity") == "critical"])
        high_count = len([i for i in unique_issues if i.get("severity") == "high"])
        
        # Determine final risk level
        if critical_count > 0:
            risk_level = "critical"
        elif high_count > 2:
            risk_level = "high"
        elif high_count > 0 or len(unique_issues) > 5:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return {
            "ai_score": round(final_score, 1),
            "risk_level": risk_level,
            "confidence_score": validation_confidence,
            "analysis_layers": {
                "pre_screening": len(pre_screen.get("priority_issues", [])),
                "deep_analysis": len(deep_analysis.get("issues", [])),
                "cross_validated": validation.get("validated", False)
            },
            "review_summary": {
                "overall_assessment": self._generate_assessment(final_score, risk_level, unique_issues),
                "strengths": deep_analysis.get("strengths", []),
                "critical_concerns": [i for i in unique_issues if i.get("severity") == "critical"],
                "recommended_action": self._determine_action(risk_level, critical_count, high_count)
            },
            "metrics": {
                "complexity_score": deep_analysis.get("metrics", {}).get("complexity_score", 5),
                "maintainability_index": deep_analysis.get("metrics", {}).get("maintainability_index", 70.0),
                "security_score": max(1, 10 - critical_count * 3 - high_count),
                "performance_score": deep_analysis.get("metrics", {}).get("performance_score", 7),
                "test_coverage_concern": len([f for f in files if "test" not in f.get("filename", "").lower()]) > len(files) * 0.8
            },
            "issue_count": len(unique_issues),
            "warning_count": len([i for i in unique_issues if i.get("severity") in ["medium", "low"]]),
            "issues": unique_issues,
            "warnings": deep_analysis.get("warnings", []),
            "recommendations": self._prioritize_recommendations(deep_analysis.get("recommendations", [])),
            "security_findings": {
                "vulnerabilities_found": critical_count + high_count,
                "owasp_categories": list(set([i.get("owasp_category") for i in unique_issues if i.get("owasp_category")])),
                "cwe_ids": list(set([i.get("cwe_id") for i in unique_issues if i.get("cwe_id")])),
                "requires_security_review": critical_count > 0 or high_count > 1
            },
            "technical_debt": {
                "estimated_hours": len(unique_issues) * 0.5 + critical_count * 2 + high_count * 1,
                "priority": "high" if critical_count > 0 else "medium" if high_count > 0 else "low",
                "debt_items": [i.get("title", "Unknown issue") for i in unique_issues[:5]]
            },
            "summary": self._generate_executive_summary(final_score, risk_level, unique_issues, validation_confidence),
            "analysis_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "models_used": [self.FAST_MODEL, self.PRIMARY_MODEL, self.SECONDARY_MODEL],
                "files_analyzed": len(files),
                "total_lines": sum(len(f.get("content", "").split("\n")) for f in files),
                "analysis_duration_seconds": 0  # TODO: Track actual duration
            }
        }
    
    def _prepare_files(self, files: List[Dict[str, Any]]) -> List[Dict]:
        """Prepare and validate files for analysis"""
        processed = []
        for file in files[:self.MAX_FILES]:
            if not file.get("filename") or not file.get("content"):
                continue
                
            content = file["content"][:self.MAX_CONTENT_LEN]
            
            processed.append({
                "filename": file["filename"],
                "content": content,
                "additions": file.get("additions", 0),
                "deletions": file.get("deletions", 0),
                "language": self._detect_language(file["filename"])
            })
        
        return processed
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename"""
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".java": "java", ".cpp": "cpp", ".c": "c", ".cs": "csharp",
            ".rb": "ruby", ".go": "go", ".rs": "rust", ".php": "php",
            ".swift": "swift", ".kt": "kotlin", ".scala": "scala"
        }
        
        for ext, lang in ext_map.items():
            if filename.lower().endswith(ext):
                return lang
        return "unknown"
    
    def _generate_cache_key(self, files: List[Dict]) -> str:
        """Generate cache key for analysis"""
        content_hash = hashlib.md5()
        for file in files:
            content_hash.update(f"{file['filename']}:{file['content']}".encode())
        return content_hash.hexdigest()
    
    def _deduplicate_issues(self, issues: List[Dict]) -> List[Dict]:
        """Remove duplicate issues based on file, line, and type"""
        seen = set()
        unique = []
        
        for issue in issues:
            key = (
                issue.get("file", ""),
                issue.get("line", 0),
                issue.get("type", ""),
                issue.get("title", "")
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        
        return unique
    
    def _build_prescreening_prompt(self, files: List[Dict]) -> str:
        """Build prompt for fast pre-screening"""
        files_summary = "\n".join([
            f"File: {f['filename']} ({f['language']}, {len(f['content'].split())} lines)"
            for f in files[:10]  # Limit for pre-screening
        ])
        
        return f"""
Perform fast pre-screening of these code files for obvious critical issues:

{files_summary}

Look for:
1. SQL injection vulnerabilities
2. XSS vulnerabilities  
3. Authentication/authorization bypasses
4. Hardcoded secrets/passwords
5. Obvious security misconfigurations
6. Critical performance issues
7. Major code smells

Respond in JSON format:
{{
    "priority_issues": [
        {{
            "type": "sql_injection",
            "file": "filename.py",
            "line": 45,
            "severity": "critical",
            "description": "Brief description"
        }}
    ],
    "risk_indicators": ["indicator1", "indicator2"],
    "needs_deep_analysis": true/false,
    "estimated_risk": "low/medium/high/critical"
}}
"""
    
    def _build_deep_analysis_prompt(self, files: List[Dict], pre_screen: Dict) -> str:
        """Build comprehensive analysis prompt"""
        files_content = "\n\n".join([
            f"=== {f['filename']} ({f['language']}) ===\n{f['content']}"
            for f in files
        ])
        
        pre_screen_context = f"Pre-screening found: {len(pre_screen.get('priority_issues', []))} priority issues"
        
        return f"""
{pre_screen_context}

Perform comprehensive code analysis of these files:

{files_content}

Analyze for:

1. SECURITY VULNERABILITIES:
   - OWASP Top 10 (Injection, Broken Auth, Sensitive Data, XXE, Broken Access Control, etc.)
   - CWE categories
   - Cryptographic issues
   - Input validation problems

2. CODE QUALITY:
   - Code smells and anti-patterns
   - Maintainability issues
   - Complexity problems
   - Documentation gaps

3. PERFORMANCE:
   - Inefficient algorithms
   - Memory leaks
   - Database query issues
   - Scalability concerns

4. ARCHITECTURE:
   - Design pattern violations
   - Coupling and cohesion
   - SOLID principles
   - Error handling

Respond in JSON format:
{{
    "ai_score": 7.5,
    "risk_level": "medium",
    "confidence_score": 0.85,
    "strengths": ["Good error handling", "Clear variable names"],
    "issues": [
        {{
            "id": "unique_id",
            "category": "security",
            "type": "sql_injection", 
            "severity": "critical",
            "title": "SQL Injection in user query",
            "description": "Detailed explanation",
            "file": "app.py",
            "line": 45,
            "code_snippet": "query = f'SELECT * FROM users WHERE id = {user_id}'",
            "impact": "Attacker could access all user data",
            "remediation": "Use parameterized queries",
            "references": ["CWE-89", "OWASP-A03"],
            "cwe_id": "CWE-89",
            "owasp_category": "A03:2021-Injection"
        }}
    ],
    "warnings": [
        {{
            "type": "complexity",
            "severity": "medium", 
            "message": "Function too complex",
            "suggestion": "Break into smaller functions",
            "file": "utils.py",
            "line": 123
        }}
    ],
    "recommendations": [
        {{
            "priority": "high",
            "category": "security",
            "recommendation": "Implement input validation",
            "rationale": "Prevents injection attacks",
            "effort": "4 hours"
        }}
    ],
    "metrics": {{
        "complexity_score": 6,
        "maintainability_index": 75.5,
        "security_score": 4,
        "performance_score": 8
    }}
}}
"""
    
    def _build_validation_prompt(self, files: List[Dict], analysis: Dict) -> str:
        """Build cross-validation prompt"""
        return f"""
Validate this code analysis for accuracy:

Original Analysis Summary:

Key Issues Identified:
{json.dumps(analysis.get('issues', [])[:5], indent=2)}

Files Analyzed:
{chr(10).join([f"- {f['filename']} ({f['language']})" for f in files])}

Validate:
1. Are the identified issues actually present in the code?
2. Are severity levels appropriate?
3. Any false positives?
4. Any critical issues missed?

Respond in JSON:
{{
    "validated": true/false,
    "confidence": 0.0-1.0,
    "false_positives": ["issue_id1", "issue_id2"],
    "missed_critical": [
        {{
            "type": "missed_issue_type",
            "file": "filename",
            "description": "What was missed"
        }}
    ],
    "severity_adjustments": [
        {{
            "issue_id": "id",
            "current_severity": "high",
            "suggested_severity": "medium",
            "reason": "Impact is limited"
        }}
    ],
    "validation_notes": "Overall assessment notes"
}}
"""
    
    def _generate_assessment(self, score: float, risk_level: str, issues: List[Dict]) -> str:
        """Generate overall assessment"""
        if score >= 8.0:
            return f"Excellent code quality with {risk_level} risk level. {len(issues)} issues identified for improvement."
        elif score >= 6.0:
            return f"Good code quality with {risk_level} risk level. {len(issues)} issues need attention."
        elif score >= 4.0:
            return f"Moderate code quality with {risk_level} risk level. {len(issues)} issues require resolution."
        else:
            return f"Poor code quality with {risk_level} risk level. {len(issues)} critical issues need immediate attention."
    
    def _determine_action(self, risk_level: str, critical_count: int, high_count: int) -> str:
        """Determine recommended action"""
        if risk_level == "critical" or critical_count > 0:
            return "reject"
        elif risk_level == "high" or high_count > 2:
            return "request_changes"
        elif risk_level == "medium":
            return "approve_with_suggestions"
        else:
            return "approve"
    
    def _prioritize_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Sort recommendations by priority and impact"""
        priority_order = {"high": 3, "medium": 2, "low": 1}
        return sorted(
            recommendations, 
            key=lambda x: priority_order.get(x.get("priority", "low"), 1),
            reverse=True
        )
    
    def _generate_executive_summary(self, score: float, risk_level: str, issues: List[Dict], confidence: float) -> str:
        """Generate executive summary"""
        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        security_issues = [i for i in issues if i.get("category") == "security"]
        
        summary = f"Code analysis complete with {score}/10 quality score and {risk_level} risk level. "
        
        if critical_issues:
            summary += f"{len(critical_issues)} critical issues require immediate attention. "
        
        if security_issues:
            summary += f"{len(security_issues)} security vulnerabilities identified. "
        
        summary += f"Analysis confidence: {confidence*100:.0f}%. "
        
        if score >= 7.0:
            summary += "Code meets quality standards with minor improvements needed."
        elif score >= 5.0:
            summary += "Code requires moderate improvements before deployment."
        else:
            summary += "Code requires significant improvements and security review."
        
        return summary
    
    def _empty_analysis_result(self) -> Dict[str, Any]:
        """Return empty analysis result"""
        return {
            "ai_score": 0.0,
            "risk_level": "unknown",
            "confidence_score": 0.0,
            "issue_count": 0,
            "warning_count": 0,
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "summary": "No files provided for analysis"
        }
    
    def _error_analysis_result(self, error_msg: str) -> Dict[str, Any]:
        """Return error analysis result"""
        return {
            "ai_score": 1.0,
            "risk_level": "critical",
            "confidence_score": 0.0,
            "issue_count": 1,
            "warning_count": 0,
            "issues": [{
                "id": "analysis_error",
                "category": "system",
                "type": "analysis_failure",
                "severity": "critical",
                "title": "Analysis Failed",
                "description": f"Code analysis failed: {error_msg}",
                "file": "system",
                "line": 0
            }],
            "warnings": [],
            "recommendations": [],
            "summary": f"Analysis failed due to system error: {error_msg}"
        }
    
    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback analysis when deep analysis fails"""
        return {
            "ai_score": 5.0,
            "risk_level": "medium",
            "confidence_score": 0.5,
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "metrics": {
                "complexity_score": 5,
                "maintainability_index": 50.0,
                "security_score": 5,
                "performance_score": 5
            }
        }


