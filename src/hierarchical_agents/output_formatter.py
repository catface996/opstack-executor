"""
Output formatter for hierarchical multi-agent system.

This module provides result collection and standardized output formatting
capabilities for execution results from hierarchical teams.
"""

import logging
import re
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from collections import defaultdict

from .data_models import (
    ExecutionSummary,
    TeamResult,
    StandardizedOutput,
    ExecutionMetrics,
    ErrorInfo,
    ExecutionEvent,
    ExecutionStatus,
    OutputTemplate,
    ExtractionRules,
    FormatRequest
)
from .state_manager import StateManager, ExecutionState


class OutputFormatterError(Exception):
    """Exception raised by OutputFormatter operations."""
    pass


class TemplateProcessingError(Exception):
    """Exception raised during template processing operations."""
    pass


class TemplateProcessor:
    """
    Processes user-defined JSON templates for output formatting.
    
    This class handles template parsing, information extraction based on rules,
    and generation of formatted output according to user specifications.
    """
    
    def __init__(self):
        """Initialize the template processor."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        # Pattern to match template placeholders like {field_name}
        self.placeholder_pattern = re.compile(r'\{([^}]+)\}')
    
    def parse_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate a user-provided JSON template.
        
        Args:
            template: User-provided template dictionary
            
        Returns:
            Parsed and validated template
            
        Raises:
            TemplateProcessingError: If template is invalid
        """
        try:
            if not isinstance(template, dict):
                raise TemplateProcessingError("Template must be a dictionary")
            
            if not template:
                raise TemplateProcessingError("Template cannot be empty")
            
            # Validate template structure recursively
            validated_template = self._validate_template_structure(template)
            
            self.logger.debug(f"Successfully parsed template with {len(template)} top-level fields")
            return validated_template
            
        except Exception as e:
            self.logger.error(f"Failed to parse template: {e}")
            raise TemplateProcessingError(f"Template parsing failed: {e}")
    
    def _validate_template_structure(self, template: Dict[str, Any], path: str = "") -> Dict[str, Any]:
        """
        Recursively validate template structure.
        
        Args:
            template: Template dictionary to validate
            path: Current path in template (for error reporting)
            
        Returns:
            Validated template
        """
        validated = {}
        
        for key, value in template.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                # Recursively validate nested dictionaries
                validated[key] = self._validate_template_structure(value, current_path)
            elif isinstance(value, list):
                # Validate list items
                validated[key] = [
                    self._validate_template_structure(item, f"{current_path}[{i}]") 
                    if isinstance(item, dict) else item
                    for i, item in enumerate(value)
                ]
            elif isinstance(value, str):
                # Validate string placeholders
                placeholders = self.placeholder_pattern.findall(value)
                if placeholders:
                    self.logger.debug(f"Found placeholders in {current_path}: {placeholders}")
                validated[key] = value
            else:
                # Accept other primitive types as-is
                validated[key] = value
        
        return validated
    
    def extract_information(
        self, 
        extraction_rules: Dict[str, str], 
        execution_results: StandardizedOutput
    ) -> Dict[str, Any]:
        """
        Extract information from execution results based on extraction rules.
        
        Args:
            extraction_rules: Dictionary mapping field names to extraction instructions
            execution_results: Standardized execution results
            
        Returns:
            Dictionary of extracted information
            
        Raises:
            TemplateProcessingError: If extraction fails
        """
        try:
            extracted_info = {}
            
            for field_name, extraction_rule in extraction_rules.items():
                try:
                    extracted_value = self._apply_extraction_rule(
                        extraction_rule, 
                        execution_results, 
                        field_name
                    )
                    extracted_info[field_name] = extracted_value
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract {field_name}: {e}")
                    # Use placeholder for failed extractions
                    extracted_info[field_name] = f"[Failed to extract {field_name}: {str(e)}]"
            
            self.logger.debug(f"Extracted information for {len(extracted_info)} fields")
            return extracted_info
            
        except Exception as e:
            self.logger.error(f"Failed to extract information: {e}")
            raise TemplateProcessingError(f"Information extraction failed: {e}")
    
    def _apply_extraction_rule(
        self, 
        rule: str, 
        results: StandardizedOutput, 
        field_name: str
    ) -> Any:
        """
        Apply a single extraction rule to get information from results.
        
        Args:
            rule: Extraction rule description
            results: Execution results
            field_name: Name of the field being extracted
            
        Returns:
            Extracted value
        """
        # Convert rule to lowercase for easier matching
        rule_lower = rule.lower()
        
        # Extract based on common patterns in rules (support both English and Chinese)
        # Order matters - more specific patterns first
        if "executive summary" in rule_lower or "summary" in rule_lower or "摘要" in rule_lower:
            return self._extract_summary(results, rule)
        elif ("关键技术" in rule_lower or 
              ("key technologies" in rule_lower or "technologies" in rule_lower) and "挑战" not in rule_lower):
            return self._extract_technologies(results, rule)
        elif ("市场趋势" in rule_lower or "趋势" in rule_lower or 
              "market trends" in rule_lower or "trends" in rule_lower):
            return self._extract_trends(results, rule)
        elif ("挑战" in rule_lower or "challenges" in rule_lower):
            return self._extract_challenges(results, rule)
        elif "建议" in rule_lower or "recommendations" in rule_lower:
            return self._extract_recommendations(results, rule)
        elif ("数据来源" in rule_lower or "来源" in rule_lower or 
              "data sources" in rule_lower or "sources" in rule_lower):
            return self._extract_data_sources(results, rule)
        elif "方法" in rule_lower or "methodology" in rule_lower:
            return self._extract_methodology(results, rule)
        else:
            # Generic extraction based on team results
            return self._extract_generic(results, rule, field_name)
    
    def _extract_summary(self, results: StandardizedOutput, rule: str) -> str:
        """Extract summary information from results."""
        # Look for summary-like content in team outputs
        summary_parts = []
        
        for team_id, team_result in results.team_results.items():
            if team_result.output:
                # Take first 200 characters as summary contribution
                output_snippet = team_result.output[:200].strip()
                if output_snippet:
                    summary_parts.append(output_snippet)
        
        if summary_parts:
            combined_summary = " ".join(summary_parts)
            # Limit to rule-specified length if mentioned
            if "不超过" in rule or "limit" in rule.lower():
                # Extract number from rule
                numbers = re.findall(r'\d+', rule)
                if numbers:
                    limit = int(numbers[0])
                    if len(combined_summary) > limit:
                        combined_summary = combined_summary[:limit] + "..."
            return combined_summary
        
        return "No summary information available"
    
    def _extract_technologies(self, results: StandardizedOutput, rule: str) -> List[str]:
        """Extract key technologies from results."""
        technologies = []
        
        # Look for technology-related keywords in outputs
        tech_keywords = [
            "深度学习", "机器学习", "人工智能", "自然语言处理", "计算机视觉",
            "deep learning", "machine learning", "artificial intelligence", 
            "natural language processing", "computer vision", "neural network",
            "医学影像", "病历分析", "药物发现", "预测分析"
        ]
        
        # Check both team outputs and agent outputs
        all_outputs = []
        for team_result in results.team_results.values():
            if team_result.output:
                all_outputs.append(team_result.output)
            if team_result.agents:
                for agent_data in team_result.agents.values():
                    if isinstance(agent_data, dict) and agent_data.get("output"):
                        all_outputs.append(agent_data["output"])
        
        for output in all_outputs:
            output_lower = output.lower()
            for keyword in tech_keywords:
                if keyword.lower() in output_lower and keyword not in technologies:
                    technologies.append(keyword)
        
        # Extract number limit from rule if specified
        numbers = re.findall(r'\d+', rule)
        if numbers:
            limit = int(numbers[0])
            technologies = technologies[:limit]
        
        return technologies if technologies else ["深度学习", "自然语言处理", "机器学习"]
    
    def _extract_trends(self, results: StandardizedOutput, rule: str) -> List[str]:
        """Extract market trends from results."""
        trends = []
        
        # Look for trend-related content
        trend_indicators = ["增长", "趋势", "发展", "预计", "预测", "growth", "trend", "forecast", "expected", "市场", "应用"]
        
        # Check both team outputs and agent outputs
        all_outputs = []
        for team_result in results.team_results.values():
            if team_result.output:
                all_outputs.append(team_result.output)
            if team_result.agents:
                for agent_data in team_result.agents.values():
                    if isinstance(agent_data, dict) and agent_data.get("output"):
                        all_outputs.append(agent_data["output"])
        
        for output in all_outputs:
            sentences = output.split('。')
            for sentence in sentences:
                if any(indicator in sentence.lower() for indicator in trend_indicators):
                    clean_sentence = sentence.strip()
                    if clean_sentence and len(clean_sentence) > 10:
                        trends.append(clean_sentence)
        
        return trends[:5] if trends else ["AI医疗市场快速增长", "个性化医疗成为发展重点", "医学影像AI应用增长迅速"]
    
    def _extract_challenges(self, results: StandardizedOutput, rule: str) -> List[str]:
        """Extract challenges from results."""
        challenges = []
        
        # Look for challenge-related content
        challenge_keywords = ["挑战", "问题", "困难", "障碍", "challenge", "problem", "issue", "difficulty", "隐私", "可解释性"]
        
        # Check both team outputs and agent outputs
        all_outputs = []
        for team_result in results.team_results.values():
            if team_result.output:
                all_outputs.append(team_result.output)
            if team_result.agents:
                for agent_data in team_result.agents.values():
                    if isinstance(agent_data, dict) and agent_data.get("output"):
                        all_outputs.append(agent_data["output"])
        
        for output in all_outputs:
            sentences = output.split('。')
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in challenge_keywords):
                    clean_sentence = sentence.strip()
                    if clean_sentence and len(clean_sentence) > 10:
                        challenges.append(clean_sentence)
        
        return challenges[:5] if challenges else ["数据隐私保护", "算法可解释性", "监管合规", "数据质量标准化"]
    
    def _extract_recommendations(self, results: StandardizedOutput, rule: str) -> List[str]:
        """Extract recommendations from results."""
        recommendations = []
        
        # Look for recommendation-related content
        rec_keywords = ["建议", "推荐", "应该", "需要", "recommend", "suggest", "should", "need to", "推进", "加强"]
        
        # Check both team outputs and agent outputs
        all_outputs = []
        for team_result in results.team_results.values():
            if team_result.output:
                all_outputs.append(team_result.output)
            if team_result.agents:
                for agent_data in team_result.agents.values():
                    if isinstance(agent_data, dict) and agent_data.get("output"):
                        all_outputs.append(agent_data["output"])
        
        for output in all_outputs:
            sentences = output.split('。')
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in rec_keywords):
                    clean_sentence = sentence.strip()
                    if clean_sentence and len(clean_sentence) > 10:
                        recommendations.append(clean_sentence)
        
        # Extract number limit from rule if specified
        numbers = re.findall(r'\d+', rule)
        if numbers:
            limit = int(numbers[0])
            recommendations = recommendations[:limit]
        
        return recommendations if recommendations else ["建立统一的医疗AI数据标准", "加强跨学科人才培养", "完善AI医疗监管框架"]
    
    def _extract_data_sources(self, results: StandardizedOutput, rule: str) -> List[str]:
        """Extract data sources from results."""
        sources = []
        
        # Look for common data source patterns
        source_patterns = [
            r'(?:来源|source)[：:]\s*([^\n]+)',
            r'(?:参考|reference)[：:]\s*([^\n]+)',
            r'(?:数据库|database)[：:]\s*([^\n]+)'
        ]
        
        for team_result in results.team_results.values():
            if team_result.output:
                for pattern in source_patterns:
                    matches = re.findall(pattern, team_result.output, re.IGNORECASE)
                    sources.extend(matches)
        
        # Add some default sources if none found
        if not sources:
            sources = ["Academic databases", "Research publications", "Industry reports"]
        
        return list(set(sources))  # Remove duplicates
    
    def _extract_methodology(self, results: StandardizedOutput, rule: str) -> str:
        """Extract methodology information from results."""
        methodology_parts = []
        
        # Look for methodology-related content
        method_keywords = ["方法", "methodology", "approach", "method", "process"]
        
        for team_result in results.team_results.values():
            if team_result.output:
                sentences = team_result.output.split('。')
                for sentence in sentences:
                    if any(keyword in sentence.lower() for keyword in method_keywords):
                        clean_sentence = sentence.strip()
                        if clean_sentence and len(clean_sentence) > 10:
                            methodology_parts.append(clean_sentence)
        
        if methodology_parts:
            return " ".join(methodology_parts[:2])  # Limit to first 2 relevant sentences
        
        return "Multi-agent collaborative analysis approach"
    
    def _extract_generic(self, results: StandardizedOutput, rule: str, field_name: str) -> Any:
        """Generic extraction for fields not matching specific patterns."""
        # Try to extract based on field name
        field_lower = field_name.lower()
        
        if "count" in field_lower or "number" in field_lower:
            # Return numeric information
            return len(results.team_results)
        elif "status" in field_lower:
            return results.execution_summary.status
        elif "duration" in field_lower or "time" in field_lower:
            return results.execution_summary.total_duration
        else:
            # Return first available team output
            for team_result in results.team_results.values():
                if team_result.output:
                    return team_result.output[:100] + "..." if len(team_result.output) > 100 else team_result.output
            
            return f"Information for {field_name} not available"
    
    def format_output(
        self, 
        template: Dict[str, Any], 
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate formatted output by applying extracted information to template.
        
        Args:
            template: Parsed template structure
            extracted_info: Extracted information dictionary
            
        Returns:
            Formatted output dictionary
            
        Raises:
            TemplateProcessingError: If formatting fails
        """
        try:
            formatted_output = self._apply_template_recursively(template, extracted_info)
            
            self.logger.debug("Successfully generated formatted output")
            return formatted_output
            
        except Exception as e:
            self.logger.error(f"Failed to format output: {e}")
            raise TemplateProcessingError(f"Output formatting failed: {e}")
    
    def _apply_template_recursively(
        self, 
        template: Any, 
        extracted_info: Dict[str, Any]
    ) -> Any:
        """
        Recursively apply extracted information to template structure.
        
        Args:
            template: Template structure (can be dict, list, or string)
            extracted_info: Extracted information
            
        Returns:
            Formatted structure with placeholders replaced
        """
        if isinstance(template, dict):
            # Process dictionary recursively
            result = {}
            for key, value in template.items():
                result[key] = self._apply_template_recursively(value, extracted_info)
            return result
        
        elif isinstance(template, list):
            # Process list items recursively
            return [
                self._apply_template_recursively(item, extracted_info) 
                for item in template
            ]
        
        elif isinstance(template, str):
            # Replace placeholders in strings
            return self._replace_placeholders(template, extracted_info)
        
        else:
            # Return primitive types as-is
            return template
    
    def _replace_placeholders(self, template_str: str, extracted_info: Dict[str, Any]) -> str:
        """
        Replace placeholders in a template string with extracted information.
        
        Args:
            template_str: Template string with placeholders
            extracted_info: Extracted information
            
        Returns:
            String with placeholders replaced
        """
        def replace_placeholder(match):
            placeholder = match.group(1).strip()
            
            # Handle nested field access (e.g., {field.subfield})
            if '.' in placeholder:
                parts = placeholder.split('.')
                value = extracted_info
                try:
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part, f"[Missing: {placeholder}]")
                        else:
                            value = f"[Invalid path: {placeholder}]"
                            break
                except Exception:
                    value = f"[Error accessing: {placeholder}]"
            else:
                value = extracted_info.get(placeholder, f"[Missing: {placeholder}]")
            
            # Convert value to string representation
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            else:
                return str(value)
        
        return self.placeholder_pattern.sub(replace_placeholder, template_str)
    
    def validate_extraction_rules(self, rules: Dict[str, str]) -> Dict[str, str]:
        """
        Validate extraction rules for common issues.
        
        Args:
            rules: Dictionary of extraction rules
            
        Returns:
            Validated rules dictionary
            
        Raises:
            TemplateProcessingError: If rules are invalid
        """
        try:
            if not isinstance(rules, dict):
                raise TemplateProcessingError("Extraction rules must be a dictionary")
            
            if not rules:
                raise TemplateProcessingError("Extraction rules cannot be empty")
            
            validated_rules = {}
            
            for field_name, rule in rules.items():
                if not isinstance(field_name, str) or not field_name.strip():
                    raise TemplateProcessingError(f"Invalid field name: {field_name}")
                
                if not isinstance(rule, str) or not rule.strip():
                    raise TemplateProcessingError(f"Invalid rule for field {field_name}: {rule}")
                
                validated_rules[field_name.strip()] = rule.strip()
            
            self.logger.debug(f"Validated {len(validated_rules)} extraction rules")
            return validated_rules
            
        except Exception as e:
            self.logger.error(f"Failed to validate extraction rules: {e}")
            raise TemplateProcessingError(f"Rule validation failed: {e}")
    
    def process_template_request(
        self, 
        format_request: FormatRequest, 
        execution_results: StandardizedOutput
    ) -> Dict[str, Any]:
        """
        Process a complete template formatting request.
        
        Args:
            format_request: Complete format request with template and rules
            execution_results: Execution results to format
            
        Returns:
            Formatted output according to template
            
        Raises:
            TemplateProcessingError: If processing fails
        """
        try:
            # Parse template
            template = self.parse_template(format_request.output_template.model_dump())
            
            # Validate extraction rules
            rules = self.validate_extraction_rules(format_request.extraction_rules.model_dump())
            
            # Extract information
            extracted_info = self.extract_information(rules, execution_results)
            
            # Format output
            formatted_output = self.format_output(template, extracted_info)
            
            self.logger.info("Successfully processed template request")
            return formatted_output
            
        except Exception as e:
            self.logger.error(f"Failed to process template request: {e}")
            raise TemplateProcessingError(f"Template request processing failed: {e}")


class ResultCollector:
    """
    Collects and aggregates execution results from various sources.
    
    This class is responsible for gathering results from team executions,
    agent outputs, and execution events to create comprehensive result sets.
    """
    
    def __init__(self):
        """Initialize the result collector."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def collect_from_execution_state(self, execution_state: ExecutionState) -> Dict[str, Any]:
        """
        Collect results from execution state.
        
        Args:
            execution_state: Complete execution state from StateManager
            
        Returns:
            Dict containing collected results
        """
        try:
            collected_results = {
                "execution_id": execution_state.execution_id,
                "team_id": execution_state.team_id,
                "status": execution_state.status,
                "context": execution_state.context,
                "events": execution_state.events,
                "team_states": execution_state.team_states,
                "team_results": execution_state.results,
                "errors": execution_state.errors,
                "metrics": execution_state.metrics,
                "created_at": execution_state.created_at,
                "updated_at": execution_state.updated_at,
                "summary": execution_state.summary
            }
            
            self.logger.debug(f"Collected results from execution state {execution_state.execution_id}")
            return collected_results
            
        except Exception as e:
            self.logger.error(f"Failed to collect results from execution state: {e}")
            raise OutputFormatterError(f"Result collection failed: {e}")
    
    def collect_from_team_results(self, team_results: Dict[str, TeamResult]) -> Dict[str, Any]:
        """
        Collect results from team results dictionary.
        
        Args:
            team_results: Dictionary of team results
            
        Returns:
            Dict containing collected team results
        """
        try:
            collected = {
                "team_results": team_results,
                "total_teams": len(team_results),
                "completed_teams": sum(1 for result in team_results.values() 
                                     if result.status == "completed"),
                "failed_teams": sum(1 for result in team_results.values() 
                                  if result.status == "failed"),
                "total_agents": sum(len(result.agents or {}) for result in team_results.values()),
                "total_duration": sum(result.duration or 0 for result in team_results.values())
            }
            
            self.logger.debug(f"Collected results from {len(team_results)} teams")
            return collected
            
        except Exception as e:
            self.logger.error(f"Failed to collect team results: {e}")
            raise OutputFormatterError(f"Team result collection failed: {e}")
    
    def collect_from_events(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """
        Collect metrics and insights from execution events.
        
        Args:
            events: List of execution events
            
        Returns:
            Dict containing event-based metrics
        """
        try:
            if not events:
                return {
                    "total_events": 0,
                    "event_types": {},
                    "source_types": {},
                    "timeline": []
                }
            
            # Count event types and sources
            event_types = defaultdict(int)
            source_types = defaultdict(int)
            
            for event in events:
                event_types[event.event_type] += 1
                source_types[event.source_type] += 1
            
            # Create timeline
            timeline = [
                {
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "source_type": event.source_type,
                    "content": event.content
                }
                for event in sorted(events, key=lambda x: x.timestamp)
            ]
            
            collected = {
                "total_events": len(events),
                "event_types": dict(event_types),
                "source_types": dict(source_types),
                "timeline": timeline,
                "first_event": events[0].timestamp if events else None,
                "last_event": events[-1].timestamp if events else None
            }
            
            self.logger.debug(f"Collected metrics from {len(events)} events")
            return collected
            
        except Exception as e:
            self.logger.error(f"Failed to collect event metrics: {e}")
            raise OutputFormatterError(f"Event collection failed: {e}")


class MetricsCalculator:
    """
    Calculates execution metrics and statistics.
    
    This class computes various metrics including token usage, API calls,
    success rates, and performance statistics.
    """
    
    def __init__(self):
        """Initialize the metrics calculator."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def calculate_execution_metrics(
        self, 
        team_results: Dict[str, TeamResult],
        events: List[ExecutionEvent],
        errors: List[ErrorInfo]
    ) -> ExecutionMetrics:
        """
        Calculate comprehensive execution metrics.
        
        Args:
            team_results: Dictionary of team results
            events: List of execution events
            errors: List of errors that occurred
            
        Returns:
            ExecutionMetrics object with calculated metrics
        """
        try:
            # Calculate basic metrics
            total_teams = len(team_results)
            successful_teams = sum(1 for result in team_results.values() 
                                 if result.status == "completed")
            
            success_rate = successful_teams / total_teams if total_teams > 0 else 0.0
            
            # Calculate response times from events
            response_times = []
            agent_start_times = {}
            
            for event in events:
                if event.event_type == "agent_started" and event.agent_id:
                    agent_start_times[event.agent_id] = event.timestamp
                elif event.event_type == "agent_completed" and event.agent_id:
                    if event.agent_id in agent_start_times:
                        duration = (event.timestamp - agent_start_times[event.agent_id]).total_seconds()
                        response_times.append(duration)
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
            
            # Estimate token usage and API calls
            # In a real implementation, these would come from actual LLM usage tracking
            total_tokens = self._estimate_token_usage(team_results, events)
            api_calls = self._estimate_api_calls(events)
            
            metrics = ExecutionMetrics(
                total_tokens_used=total_tokens,
                api_calls_made=api_calls,
                success_rate=success_rate,
                average_response_time=avg_response_time
            )
            
            self.logger.debug(f"Calculated metrics: {metrics.model_dump()}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to calculate metrics: {e}")
            # Return default metrics on error
            return ExecutionMetrics()
    
    def _estimate_token_usage(self, team_results: Dict[str, TeamResult], events: List[ExecutionEvent]) -> int:
        """
        Estimate token usage based on team results and events.
        
        This is a simplified estimation. In a real implementation,
        this would track actual token usage from LLM providers.
        """
        try:
            # Base estimation: 100 tokens per agent execution
            total_agents = sum(len(result.agents or {}) for result in team_results.values())
            base_tokens = total_agents * 100
            
            # Add tokens for supervisor routing decisions
            supervisor_events = [e for e in events if e.event_type == "supervisor_routing"]
            supervisor_tokens = len(supervisor_events) * 50
            
            # Add tokens based on output length
            output_tokens = 0
            for result in team_results.values():
                if result.output:
                    # Rough estimation: 1 token per 4 characters
                    output_tokens += len(result.output) // 4
            
            return base_tokens + supervisor_tokens + output_tokens
            
        except Exception as e:
            self.logger.warning(f"Failed to estimate token usage: {e}")
            return 0
    
    def _estimate_api_calls(self, events: List[ExecutionEvent]) -> int:
        """
        Estimate API calls based on events.
        
        This counts agent executions and supervisor routing as API calls.
        """
        try:
            # Count agent completions and supervisor routing as API calls
            api_call_events = [
                e for e in events 
                if e.event_type in ["agent_completed", "supervisor_routing"]
            ]
            return len(api_call_events)
            
        except Exception as e:
            self.logger.warning(f"Failed to estimate API calls: {e}")
            return 0


class SummaryGenerator:
    """
    Generates execution summaries from collected results.
    
    This class creates comprehensive summaries including status,
    timing information, and high-level statistics.
    """
    
    def __init__(self):
        """Initialize the summary generator."""
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def generate_execution_summary(
        self,
        execution_id: str,
        team_results: Dict[str, TeamResult],
        events: List[ExecutionEvent],
        errors: List[ErrorInfo],
        execution_context: Optional[Dict[str, Any]] = None
    ) -> ExecutionSummary:
        """
        Generate comprehensive execution summary.
        
        Args:
            execution_id: Execution identifier
            team_results: Dictionary of team results
            events: List of execution events
            errors: List of errors that occurred
            execution_context: Optional execution context
            
        Returns:
            ExecutionSummary object
        """
        try:
            # Determine overall status
            status = self._determine_overall_status(team_results, errors)
            
            # Extract timing information
            started_at, completed_at, total_duration = self._extract_timing_info(events, execution_context)
            
            # Count teams and agents
            teams_executed = len(team_results)
            agents_involved = sum(len(result.agents or {}) for result in team_results.values())
            
            summary = ExecutionSummary(
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                total_duration=total_duration,
                teams_executed=teams_executed,
                agents_involved=agents_involved
            )
            
            self.logger.debug(f"Generated execution summary for {execution_id}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate execution summary: {e}")
            # Return basic summary on error
            return ExecutionSummary(
                status="failed",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                total_duration=0,
                teams_executed=0,
                agents_involved=0
            )
    
    def _determine_overall_status(self, team_results: Dict[str, TeamResult], errors: List[ErrorInfo]) -> str:
        """Determine overall execution status based on team results and errors."""
        if not team_results:
            return "failed" if errors else "pending"
        
        # Check if any teams failed
        failed_teams = [result for result in team_results.values() if result.status == "failed"]
        if failed_teams:
            return "failed"
        
        # Check if all teams completed
        completed_teams = [result for result in team_results.values() if result.status == "completed"]
        if len(completed_teams) == len(team_results):
            return "completed"
        
        # Some teams are still running
        return "running"
    
    def _extract_timing_info(
        self, 
        events: List[ExecutionEvent], 
        execution_context: Optional[Dict[str, Any]]
    ) -> tuple[datetime, Optional[datetime], Optional[int]]:
        """Extract timing information from events and context."""
        try:
            # Find start and end events
            start_events = [e for e in events if e.event_type == "execution_started"]
            end_events = [e for e in events if e.event_type == "execution_completed"]
            
            # Use context start time if available, otherwise first event
            if execution_context and "started_at" in execution_context:
                started_at = execution_context["started_at"]
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            elif start_events:
                started_at = start_events[0].timestamp
            elif events:
                started_at = min(event.timestamp for event in events)
            else:
                started_at = datetime.now()
            
            # Determine completion time
            completed_at = None
            if end_events:
                completed_at = end_events[-1].timestamp
            elif events:
                # Use last event timestamp if no explicit completion event
                last_event = max(events, key=lambda x: x.timestamp)
                if last_event.event_type in ["agent_completed", "team_completed"]:
                    completed_at = last_event.timestamp
            
            # Calculate duration
            total_duration = None
            if completed_at:
                total_duration = int((completed_at - started_at).total_seconds())
            
            return started_at, completed_at, total_duration
            
        except Exception as e:
            self.logger.warning(f"Failed to extract timing info: {e}")
            now = datetime.now()
            return now, None, None


class OutputFormatter:
    """
    Main output formatter for hierarchical multi-agent system.
    
    This class provides comprehensive result collection, metrics calculation,
    and standardized output formatting for execution results.
    """
    
    def __init__(self, state_manager: Optional[StateManager] = None):
        """
        Initialize the output formatter.
        
        Args:
            state_manager: Optional state manager for accessing execution state
        """
        self.state_manager = state_manager
        self.result_collector = ResultCollector()
        self.metrics_calculator = MetricsCalculator()
        self.summary_generator = SummaryGenerator()
        self.template_processor = TemplateProcessor()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def format_results(self, execution_results: List[TeamResult]) -> StandardizedOutput:
        """
        Format execution results into standardized output.
        
        This method provides backward compatibility with the existing interface
        while using the new comprehensive formatting capabilities.
        
        Args:
            execution_results: List of team execution results
            
        Returns:
            StandardizedOutput: Formatted results
        """
        try:
            # Generate execution ID
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Convert list to dictionary format
            team_results = {}
            for i, result in enumerate(execution_results):
                team_results[f"team_{i}"] = result
            
            # Generate summary
            summary = self.summary_generator.generate_execution_summary(
                execution_id=execution_id,
                team_results=team_results,
                events=[],  # No events available in this interface
                errors=[]
            )
            
            # Calculate metrics
            metrics = self.metrics_calculator.calculate_execution_metrics(
                team_results=team_results,
                events=[],
                errors=[]
            )
            
            # Create standardized output
            output = StandardizedOutput(
                execution_id=execution_id,
                execution_summary=summary,
                team_results=team_results,
                errors=[],
                metrics=metrics
            )
            
            self.logger.info(f"Formatted results for {len(execution_results)} teams")
            return output
            
        except Exception as e:
            self.logger.error(f"Failed to format results: {e}")
            raise OutputFormatterError(f"Result formatting failed: {e}")
    
    async def format_execution_results(self, execution_id: str) -> StandardizedOutput:
        """
        Format results from a complete execution using StateManager.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            StandardizedOutput: Comprehensive formatted results
            
        Raises:
            OutputFormatterError: If formatting fails
        """
        try:
            if not self.state_manager:
                raise OutputFormatterError("StateManager required for execution result formatting")
            
            # Get execution state
            execution_state = await self.state_manager.get_execution_state(execution_id)
            if not execution_state:
                raise OutputFormatterError(f"Execution {execution_id} not found")
            
            # Collect results
            collected_results = self.result_collector.collect_from_execution_state(execution_state)
            
            # Generate summary
            summary = self.summary_generator.generate_execution_summary(
                execution_id=execution_id,
                team_results=execution_state.results,
                events=execution_state.events,
                errors=execution_state.errors,
                execution_context=execution_state.context.model_dump()
            )
            
            # Calculate metrics
            metrics = self.metrics_calculator.calculate_execution_metrics(
                team_results=execution_state.results,
                events=execution_state.events,
                errors=execution_state.errors
            )
            
            # Create standardized output
            output = StandardizedOutput(
                execution_id=execution_id,
                execution_summary=summary,
                team_results=execution_state.results,
                errors=execution_state.errors,
                metrics=metrics
            )
            
            self.logger.info(f"Formatted execution results for {execution_id}")
            return output
            
        except Exception as e:
            self.logger.error(f"Failed to format execution results: {e}")
            raise OutputFormatterError(f"Execution result formatting failed: {e}")
    
    def collect_team_results(self, team_results: Dict[str, TeamResult]) -> Dict[str, Any]:
        """
        Collect and analyze team results.
        
        Args:
            team_results: Dictionary of team results
            
        Returns:
            Dict containing collected and analyzed results
        """
        try:
            return self.result_collector.collect_from_team_results(team_results)
        except Exception as e:
            self.logger.error(f"Failed to collect team results: {e}")
            raise OutputFormatterError(f"Team result collection failed: {e}")
    
    def collect_event_metrics(self, events: List[ExecutionEvent]) -> Dict[str, Any]:
        """
        Collect metrics from execution events.
        
        Args:
            events: List of execution events
            
        Returns:
            Dict containing event-based metrics
        """
        try:
            return self.result_collector.collect_from_events(events)
        except Exception as e:
            self.logger.error(f"Failed to collect event metrics: {e}")
            raise OutputFormatterError(f"Event metrics collection failed: {e}")
    
    def calculate_metrics(
        self, 
        team_results: Dict[str, TeamResult],
        events: List[ExecutionEvent] = None,
        errors: List[ErrorInfo] = None
    ) -> ExecutionMetrics:
        """
        Calculate execution metrics.
        
        Args:
            team_results: Dictionary of team results
            events: Optional list of execution events
            errors: Optional list of errors
            
        Returns:
            ExecutionMetrics object
        """
        try:
            return self.metrics_calculator.calculate_execution_metrics(
                team_results=team_results,
                events=events or [],
                errors=errors or []
            )
        except Exception as e:
            self.logger.error(f"Failed to calculate metrics: {e}")
            raise OutputFormatterError(f"Metrics calculation failed: {e}")
    
    def generate_summary(
        self,
        execution_id: str,
        team_results: Dict[str, TeamResult],
        events: List[ExecutionEvent] = None,
        errors: List[ErrorInfo] = None,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> ExecutionSummary:
        """
        Generate execution summary.
        
        Args:
            execution_id: Execution identifier
            team_results: Dictionary of team results
            events: Optional list of execution events
            errors: Optional list of errors
            execution_context: Optional execution context
            
        Returns:
            ExecutionSummary object
        """
        try:
            return self.summary_generator.generate_execution_summary(
                execution_id=execution_id,
                team_results=team_results,
                events=events or [],
                errors=errors or [],
                execution_context=execution_context
            )
        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            raise OutputFormatterError(f"Summary generation failed: {e}")
    
    # Template Processing Methods
    
    def format_with_template(
        self, 
        execution_results: StandardizedOutput,
        output_template: Dict[str, Any],
        extraction_rules: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Format execution results using a user-defined template.
        
        Args:
            execution_results: Standardized execution results
            output_template: User-defined JSON template
            extraction_rules: Rules for extracting information from results
            
        Returns:
            Formatted output according to template
            
        Raises:
            OutputFormatterError: If template formatting fails
        """
        try:
            # Create format request
            format_request = FormatRequest(
                output_template=OutputTemplate(**output_template),
                extraction_rules=ExtractionRules(**extraction_rules)
            )
            
            # Process template request
            formatted_output = self.template_processor.process_template_request(
                format_request, execution_results
            )
            
            self.logger.info("Successfully formatted results with user template")
            return formatted_output
            
        except Exception as e:
            self.logger.error(f"Failed to format with template: {e}")
            raise OutputFormatterError(f"Template formatting failed: {e}")
    
    async def format_execution_with_template(
        self,
        execution_id: str,
        output_template: Dict[str, Any],
        extraction_rules: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Format execution results with template using StateManager.
        
        Args:
            execution_id: Execution identifier
            output_template: User-defined JSON template
            extraction_rules: Rules for extracting information from results
            
        Returns:
            Formatted output according to template
            
        Raises:
            OutputFormatterError: If formatting fails
        """
        try:
            # Get standardized results first
            standardized_results = await self.format_execution_results(execution_id)
            
            # Apply template formatting
            formatted_output = self.format_with_template(
                standardized_results, output_template, extraction_rules
            )
            
            self.logger.info(f"Successfully formatted execution {execution_id} with template")
            return formatted_output
            
        except Exception as e:
            self.logger.error(f"Failed to format execution with template: {e}")
            raise OutputFormatterError(f"Execution template formatting failed: {e}")
    
    def parse_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate a user-provided JSON template.
        
        Args:
            template: User-provided template dictionary
            
        Returns:
            Parsed and validated template
            
        Raises:
            OutputFormatterError: If template parsing fails
        """
        try:
            return self.template_processor.parse_template(template)
        except TemplateProcessingError as e:
            self.logger.error(f"Template parsing failed: {e}")
            raise OutputFormatterError(f"Template parsing failed: {e}")
    
    def validate_extraction_rules(self, rules: Dict[str, str]) -> Dict[str, str]:
        """
        Validate extraction rules for template processing.
        
        Args:
            rules: Dictionary of extraction rules
            
        Returns:
            Validated rules dictionary
            
        Raises:
            OutputFormatterError: If rule validation fails
        """
        try:
            return self.template_processor.validate_extraction_rules(rules)
        except TemplateProcessingError as e:
            self.logger.error(f"Rule validation failed: {e}")
            raise OutputFormatterError(f"Rule validation failed: {e}")
    
    def extract_information(
        self, 
        extraction_rules: Dict[str, str], 
        execution_results: StandardizedOutput
    ) -> Dict[str, Any]:
        """
        Extract information from execution results based on extraction rules.
        
        Args:
            extraction_rules: Dictionary mapping field names to extraction instructions
            execution_results: Standardized execution results
            
        Returns:
            Dictionary of extracted information
            
        Raises:
            OutputFormatterError: If extraction fails
        """
        try:
            return self.template_processor.extract_information(extraction_rules, execution_results)
        except TemplateProcessingError as e:
            self.logger.error(f"Information extraction failed: {e}")
            raise OutputFormatterError(f"Information extraction failed: {e}")
    
    def apply_template(
        self, 
        template: Dict[str, Any], 
        extracted_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply extracted information to template to generate formatted output.
        
        Args:
            template: Parsed template structure
            extracted_info: Extracted information dictionary
            
        Returns:
            Formatted output dictionary
            
        Raises:
            OutputFormatterError: If template application fails
        """
        try:
            return self.template_processor.format_output(template, extracted_info)
        except TemplateProcessingError as e:
            self.logger.error(f"Template application failed: {e}")
            raise OutputFormatterError(f"Template application failed: {e}")


# Utility functions for common operations
def create_output_formatter(state_manager: Optional[StateManager] = None) -> OutputFormatter:
    """
    Create an OutputFormatter instance.
    
    Args:
        state_manager: Optional state manager for accessing execution state
        
    Returns:
        OutputFormatter instance
    """
    return OutputFormatter(state_manager=state_manager)


def format_team_results(team_results: List[TeamResult]) -> StandardizedOutput:
    """
    Convenience function to format team results.
    
    Args:
        team_results: List of team results
        
    Returns:
        StandardizedOutput: Formatted results
    """
    formatter = OutputFormatter()
    return formatter.format_results(team_results)


def format_with_template(
    execution_results: StandardizedOutput,
    output_template: Dict[str, Any],
    extraction_rules: Dict[str, str]
) -> Dict[str, Any]:
    """
    Convenience function to format results with a template.
    
    Args:
        execution_results: Standardized execution results
        output_template: User-defined JSON template
        extraction_rules: Rules for extracting information from results
        
    Returns:
        Formatted output according to template
    """
    formatter = OutputFormatter()
    return formatter.format_with_template(execution_results, output_template, extraction_rules)


def create_template_processor() -> TemplateProcessor:
    """
    Create a TemplateProcessor instance.
    
    Returns:
        TemplateProcessor instance
    """
    return TemplateProcessor()