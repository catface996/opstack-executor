"""
Built-in tools for the hierarchical multi-agent system.

This module provides commonly used tools that agents can use:
- Search tools (web search, document search)
- Document processing tools (text processing, file operations)
- Data processing tools (JSON, CSV handling)
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from .tools import BaseTool, ToolInput, ToolOutput, ToolMetadata


class TavilySearchTool(BaseTool):
    """Web search tool using Tavily API (mock implementation for testing)."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="tavily_search",
            description="Search the web for information using Tavily API",
            version="1.0.0",
            author="Hierarchical Agents Team",
            tags=["search", "web", "information"],
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5, "description": "Maximum number of results"},
                    "include_domains": {"type": "array", "items": {"type": "string"}, "description": "Domains to include"},
                    "exclude_domains": {"type": "array", "items": {"type": "string"}, "description": "Domains to exclude"}
                },
                "required": ["query"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array", "description": "Search results"},
                    "query": {"type": "string", "description": "Original query"},
                    "total_results": {"type": "integer", "description": "Total number of results"}
                }
            },
            requires_auth=True
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate search input."""
        return hasattr(input_data, 'query') and bool(getattr(input_data, 'query', '').strip())
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute web search (mock implementation)."""
        try:
            query = getattr(input_data, 'query', '')
            max_results = getattr(input_data, 'max_results', 5)
            
            # Mock search results for testing
            mock_results = [
                {
                    "title": f"AI Medical Applications - Result {i+1}",
                    "url": f"https://example{i+1}.com/ai-medical-research",
                    "snippet": f"This is a mock search result {i+1} for query: {query}. "
                             f"It contains relevant information about AI applications in healthcare.",
                    "published_date": "2024-01-15",
                    "score": 0.9 - (i * 0.1)
                }
                for i in range(min(max_results, 5))
            ]
            
            # Simulate API delay
            time.sleep(0.1)
            
            return ToolOutput(
                success=True,
                result={
                    "results": mock_results,
                    "query": query,
                    "total_results": len(mock_results)
                },
                metadata={
                    "provider": "tavily",
                    "api_version": "v1",
                    "cached": False
                }
            )
            
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Search failed: {str(e)}"
            )


class WebScraperTool(BaseTool):
    """Web scraping tool for extracting content from URLs."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_scraper",
            description="Extract and process content from web pages",
            version="1.0.0",
            author="Hierarchical Agents Team",
            tags=["scraping", "web", "content", "extraction"],
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "extract_text": {"type": "boolean", "default": True, "description": "Extract text content"},
                    "extract_links": {"type": "boolean", "default": False, "description": "Extract links"},
                    "max_length": {"type": "integer", "default": 10000, "description": "Maximum content length"}
                },
                "required": ["url"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Extracted content"},
                    "title": {"type": "string", "description": "Page title"},
                    "links": {"type": "array", "description": "Extracted links"},
                    "metadata": {"type": "object", "description": "Page metadata"}
                }
            }
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate scraper input."""
        url = getattr(input_data, 'url', '')
        return bool(url and (url.startswith('http://') or url.startswith('https://')))
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute web scraping (mock implementation)."""
        try:
            url = getattr(input_data, 'url', '')
            extract_text = getattr(input_data, 'extract_text', True)
            extract_links = getattr(input_data, 'extract_links', False)
            max_length = getattr(input_data, 'max_length', 10000)
            
            # Mock scraped content
            mock_content = f"""
            This is mock content scraped from {url}.
            
            The page contains detailed information about AI applications in medical research.
            Key topics include:
            - Deep learning for medical imaging
            - Natural language processing for clinical notes
            - Predictive analytics for patient outcomes
            - Challenges in data privacy and algorithm interpretability
            
            This content would normally be extracted from the actual webpage.
            """[:max_length]
            
            result = {
                "content": mock_content.strip(),
                "title": "AI Medical Research - Mock Page",
                "metadata": {
                    "url": url,
                    "scraped_at": datetime.now().isoformat(),
                    "content_length": len(mock_content)
                }
            }
            
            if extract_links:
                result["links"] = [
                    "https://example.com/related-article-1",
                    "https://example.com/related-article-2",
                    "https://example.com/research-paper-1"
                ]
            
            # Simulate scraping delay
            time.sleep(0.2)
            
            return ToolOutput(
                success=True,
                result=result,
                metadata={
                    "scraper_version": "1.0.0",
                    "user_agent": "HierarchicalAgents/1.0"
                }
            )
            
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Web scraping failed: {str(e)}"
            )


class DocumentWriterTool(BaseTool):
    """Tool for creating and formatting documents."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="document_writer",
            description="Create and format documents in various formats",
            version="1.0.0",
            author="Hierarchical Agents Team",
            tags=["document", "writing", "formatting", "text"],
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Document content"},
                    "title": {"type": "string", "description": "Document title"},
                    "format": {"type": "string", "enum": ["markdown", "html", "text"], "default": "markdown"},
                    "sections": {"type": "array", "description": "Document sections"},
                    "metadata": {"type": "object", "description": "Document metadata"}
                },
                "required": ["content"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "document": {"type": "string", "description": "Formatted document"},
                    "word_count": {"type": "integer", "description": "Word count"},
                    "format": {"type": "string", "description": "Document format"}
                }
            }
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate document writer input."""
        return hasattr(input_data, 'content') and bool(getattr(input_data, 'content', '').strip())
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute document writing."""
        try:
            content = getattr(input_data, 'content', '')
            title = getattr(input_data, 'title', 'Untitled Document')
            format_type = getattr(input_data, 'format', 'markdown')
            sections = getattr(input_data, 'sections', [])
            metadata = getattr(input_data, 'metadata', {})
            
            # Format document based on type
            if format_type == 'markdown':
                document = self._format_markdown(title, content, sections, metadata)
            elif format_type == 'html':
                document = self._format_html(title, content, sections, metadata)
            else:  # text
                document = self._format_text(title, content, sections, metadata)
            
            word_count = len(document.split())
            
            return ToolOutput(
                success=True,
                result={
                    "document": document,
                    "word_count": word_count,
                    "format": format_type
                },
                metadata={
                    "created_at": datetime.now().isoformat(),
                    "title": title,
                    "format": format_type
                }
            )
            
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Document writing failed: {str(e)}"
            )
    
    def _format_markdown(self, title: str, content: str, sections: List[Dict], metadata: Dict) -> str:
        """Format document as Markdown."""
        doc_parts = [f"# {title}", ""]
        
        if metadata:
            doc_parts.extend(["## Metadata", ""])
            for key, value in metadata.items():
                doc_parts.append(f"- **{key}**: {value}")
            doc_parts.append("")
        
        if sections:
            for section in sections:
                section_title = section.get('title', 'Section')
                section_content = section.get('content', '')
                doc_parts.extend([f"## {section_title}", "", section_content, ""])
        else:
            doc_parts.extend(["## Content", "", content])
        
        return "\n".join(doc_parts)
    
    def _format_html(self, title: str, content: str, sections: List[Dict], metadata: Dict) -> str:
        """Format document as HTML."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{title}</title>",
            "</head>",
            "<body>",
            f"<h1>{title}</h1>"
        ]
        
        if metadata:
            html_parts.extend(["<h2>Metadata</h2>", "<ul>"])
            for key, value in metadata.items():
                html_parts.append(f"<li><strong>{key}</strong>: {value}</li>")
            html_parts.append("</ul>")
        
        if sections:
            for section in sections:
                section_title = section.get('title', 'Section')
                section_content = section.get('content', '')
                html_parts.extend([
                    f"<h2>{section_title}</h2>",
                    f"<p>{section_content}</p>"
                ])
        else:
            html_parts.extend(["<h2>Content</h2>", f"<p>{content}</p>"])
        
        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts)
    
    def _format_text(self, title: str, content: str, sections: List[Dict], metadata: Dict) -> str:
        """Format document as plain text."""
        doc_parts = [title, "=" * len(title), ""]
        
        if metadata:
            doc_parts.extend(["METADATA", "-" * 8, ""])
            for key, value in metadata.items():
                doc_parts.append(f"{key}: {value}")
            doc_parts.append("")
        
        if sections:
            for section in sections:
                section_title = section.get('title', 'Section')
                section_content = section.get('content', '')
                doc_parts.extend([
                    section_title,
                    "-" * len(section_title),
                    "",
                    section_content,
                    ""
                ])
        else:
            doc_parts.extend(["CONTENT", "-" * 7, "", content])
        
        return "\n".join(doc_parts)


class DataProcessorTool(BaseTool):
    """Tool for processing and analyzing data."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="data_processor",
            description="Process and analyze structured data (JSON, CSV, etc.)",
            version="1.0.0",
            author="Hierarchical Agents Team",
            tags=["data", "processing", "analysis", "json", "csv"],
            input_schema={
                "type": "object",
                "properties": {
                    "data": {"description": "Data to process (string, dict, or list)"},
                    "operation": {"type": "string", "enum": ["analyze", "transform", "filter", "aggregate"], "default": "analyze"},
                    "format": {"type": "string", "enum": ["json", "csv", "text"], "default": "json"},
                    "parameters": {"type": "object", "description": "Operation parameters"}
                },
                "required": ["data"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"description": "Processed data result"},
                    "statistics": {"type": "object", "description": "Data statistics"},
                    "operation": {"type": "string", "description": "Operation performed"}
                }
            }
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate data processor input."""
        return hasattr(input_data, 'data') and getattr(input_data, 'data') is not None
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute data processing."""
        try:
            data = getattr(input_data, 'data')
            operation = getattr(input_data, 'operation', 'analyze')
            data_format = getattr(input_data, 'format', 'json')
            parameters = getattr(input_data, 'parameters', {})
            
            # Parse data if it's a string
            if isinstance(data, str):
                if data_format == 'json':
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        # Try to extract JSON-like patterns
                        data = self._extract_json_patterns(data)
                elif data_format == 'csv':
                    data = self._parse_csv_string(data)
            
            # Perform operation
            if operation == 'analyze':
                result = self._analyze_data(data)
            elif operation == 'transform':
                result = self._transform_data(data, parameters)
            elif operation == 'filter':
                result = self._filter_data(data, parameters)
            elif operation == 'aggregate':
                result = self._aggregate_data(data, parameters)
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            return ToolOutput(
                success=True,
                result=result,
                metadata={
                    "operation": operation,
                    "data_format": data_format,
                    "processed_at": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Data processing failed: {str(e)}"
            )
    
    def _extract_json_patterns(self, text: str) -> Dict[str, Any]:
        """Extract structured information from text."""
        # Simple pattern extraction for demo
        patterns = {
            "numbers": re.findall(r'\d+(?:\.\d+)?', text),
            "dates": re.findall(r'\d{4}-\d{2}-\d{2}', text),
            "urls": re.findall(r'https?://[^\s]+', text),
            "emails": re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        }
        return {k: v for k, v in patterns.items() if v}
    
    def _parse_csv_string(self, csv_string: str) -> List[Dict[str, str]]:
        """Parse CSV string into list of dictionaries."""
        lines = csv_string.strip().split('\n')
        if not lines:
            return []
        
        headers = [h.strip() for h in lines[0].split(',')]
        data = []
        
        for line in lines[1:]:
            values = [v.strip() for v in line.split(',')]
            if len(values) == len(headers):
                data.append(dict(zip(headers, values)))
        
        return data
    
    def _analyze_data(self, data: Any) -> Dict[str, Any]:
        """Analyze data and return statistics."""
        analysis = {
            "data_type": type(data).__name__,
            "size": len(data) if hasattr(data, '__len__') else 1
        }
        
        if isinstance(data, list):
            analysis.update({
                "item_types": list(set(type(item).__name__ for item in data)),
                "sample_items": data[:3] if data else []
            })
        elif isinstance(data, dict):
            analysis.update({
                "keys": list(data.keys()),
                "key_count": len(data),
                "value_types": list(set(type(v).__name__ for v in data.values()))
            })
        elif isinstance(data, str):
            analysis.update({
                "length": len(data),
                "word_count": len(data.split()),
                "line_count": len(data.split('\n'))
            })
        
        return {
            "result": analysis,
            "statistics": analysis,
            "operation": "analyze"
        }
    
    def _transform_data(self, data: Any, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data based on parameters."""
        # Simple transformation example
        if isinstance(data, list) and parameters.get('operation') == 'uppercase':
            result = [str(item).upper() if isinstance(item, str) else item for item in data]
        elif isinstance(data, dict) and parameters.get('operation') == 'keys_only':
            result = list(data.keys())
        else:
            result = data
        
        return {
            "result": result,
            "statistics": {"transformed_items": len(result) if hasattr(result, '__len__') else 1},
            "operation": "transform"
        }
    
    def _filter_data(self, data: Any, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Filter data based on parameters."""
        if isinstance(data, list):
            filter_func = parameters.get('filter_function', lambda x: True)
            if isinstance(filter_func, str):
                # Simple string filtering
                result = [item for item in data if filter_func.lower() in str(item).lower()]
            else:
                result = data  # No filtering applied
        else:
            result = data
        
        return {
            "result": result,
            "statistics": {"filtered_items": len(result) if hasattr(result, '__len__') else 1},
            "operation": "filter"
        }
    
    def _aggregate_data(self, data: Any, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate data based on parameters."""
        if isinstance(data, list):
            result = {
                "count": len(data),
                "unique_count": len(set(str(item) for item in data)),
                "sample": data[:5] if data else []
            }
        elif isinstance(data, dict):
            result = {
                "key_count": len(data),
                "value_count": len(data.values()),
                "keys": list(data.keys())
            }
        else:
            result = {"value": data, "type": type(data).__name__}
        
        return {
            "result": result,
            "statistics": result,
            "operation": "aggregate"
        }


class TextEditorTool(BaseTool):
    """Tool for editing and processing text content."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="editor",
            description="Edit and process text content with various operations",
            version="1.0.0",
            author="Hierarchical Agents Team",
            tags=["text", "editing", "processing", "formatting"],
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to edit"},
                    "operation": {"type": "string", "enum": ["format", "clean", "summarize", "extract"], "default": "format"},
                    "parameters": {"type": "object", "description": "Operation parameters"}
                },
                "required": ["text"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "edited_text": {"type": "string", "description": "Edited text"},
                    "changes": {"type": "array", "description": "List of changes made"},
                    "statistics": {"type": "object", "description": "Text statistics"}
                }
            }
        )
    
    def validate_input(self, input_data: ToolInput) -> bool:
        """Validate text editor input."""
        return hasattr(input_data, 'text') and isinstance(getattr(input_data, 'text'), str)
    
    def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute text editing."""
        try:
            text = getattr(input_data, 'text', '')
            operation = getattr(input_data, 'operation', 'format')
            parameters = getattr(input_data, 'parameters', {})
            
            changes = []
            
            if operation == 'format':
                edited_text, format_changes = self._format_text(text, parameters)
                changes.extend(format_changes)
            elif operation == 'clean':
                edited_text, clean_changes = self._clean_text(text, parameters)
                changes.extend(clean_changes)
            elif operation == 'summarize':
                edited_text, summary_changes = self._summarize_text(text, parameters)
                changes.extend(summary_changes)
            elif operation == 'extract':
                edited_text, extract_changes = self._extract_from_text(text, parameters)
                changes.extend(extract_changes)
            else:
                edited_text = text
                changes.append(f"Unknown operation: {operation}")
            
            statistics = {
                "original_length": len(text),
                "edited_length": len(edited_text),
                "original_words": len(text.split()),
                "edited_words": len(edited_text.split()),
                "changes_count": len(changes)
            }
            
            return ToolOutput(
                success=True,
                result={
                    "edited_text": edited_text,
                    "changes": changes,
                    "statistics": statistics
                },
                metadata={
                    "operation": operation,
                    "edited_at": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Text editing failed: {str(e)}"
            )
    
    def _format_text(self, text: str, parameters: Dict[str, Any]) -> tuple[str, List[str]]:
        """Format text according to parameters."""
        changes = []
        formatted_text = text
        
        # Remove extra whitespace
        if parameters.get('remove_extra_whitespace', True):
            original_length = len(formatted_text)
            formatted_text = re.sub(r'\s+', ' ', formatted_text).strip()
            if len(formatted_text) != original_length:
                changes.append("Removed extra whitespace")
        
        # Fix line breaks
        if parameters.get('fix_line_breaks', True):
            original_lines = len(formatted_text.split('\n'))
            formatted_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', formatted_text)
            new_lines = len(formatted_text.split('\n'))
            if new_lines != original_lines:
                changes.append("Fixed line breaks")
        
        # Capitalize sentences
        if parameters.get('capitalize_sentences', False):
            sentences = re.split(r'([.!?]+)', formatted_text)
            for i in range(0, len(sentences), 2):
                if sentences[i].strip():
                    sentences[i] = sentences[i].strip().capitalize()
            new_text = ''.join(sentences)
            if new_text != formatted_text:
                formatted_text = new_text
                changes.append("Capitalized sentences")
        
        return formatted_text, changes
    
    def _clean_text(self, text: str, parameters: Dict[str, Any]) -> tuple[str, List[str]]:
        """Clean text by removing unwanted elements."""
        changes = []
        cleaned_text = text
        
        # Remove HTML tags
        if parameters.get('remove_html', True):
            original_length = len(cleaned_text)
            cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
            if len(cleaned_text) != original_length:
                changes.append("Removed HTML tags")
        
        # Remove URLs
        if parameters.get('remove_urls', False):
            original_length = len(cleaned_text)
            cleaned_text = re.sub(r'https?://[^\s]+', '', cleaned_text)
            if len(cleaned_text) != original_length:
                changes.append("Removed URLs")
        
        # Remove special characters
        if parameters.get('remove_special_chars', False):
            original_length = len(cleaned_text)
            cleaned_text = re.sub(r'[^\w\s.,!?-]', '', cleaned_text)
            if len(cleaned_text) != original_length:
                changes.append("Removed special characters")
        
        return cleaned_text, changes
    
    def _summarize_text(self, text: str, parameters: Dict[str, Any]) -> tuple[str, List[str]]:
        """Create a simple summary of the text."""
        changes = []
        max_sentences = parameters.get('max_sentences', 3)
        
        # Simple extractive summarization
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= max_sentences:
            summary = text
            changes.append("Text already short enough")
        else:
            # Take first, middle, and last sentences as a simple summary
            if max_sentences == 1:
                summary = sentences[0] + "."
            elif max_sentences == 2:
                summary = sentences[0] + ". " + sentences[-1] + "."
            else:
                indices = [0, len(sentences) // 2, -1]
                selected_sentences = [sentences[i] for i in indices[:max_sentences]]
                summary = ". ".join(selected_sentences) + "."
            
            changes.append(f"Summarized from {len(sentences)} to {max_sentences} sentences")
        
        return summary, changes
    
    def _extract_from_text(self, text: str, parameters: Dict[str, Any]) -> tuple[str, List[str]]:
        """Extract specific information from text."""
        changes = []
        extract_type = parameters.get('extract_type', 'keywords')
        
        if extract_type == 'keywords':
            # Simple keyword extraction
            words = re.findall(r'\b\w{4,}\b', text.lower())
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top keywords
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            extracted = ", ".join([word for word, freq in top_keywords])
            changes.append(f"Extracted {len(top_keywords)} keywords")
            
        elif extract_type == 'sentences':
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            extracted = "\n".join(f"- {s}" for s in sentences[:5])
            changes.append(f"Extracted {min(5, len(sentences))} sentences")
            
        else:
            extracted = text
            changes.append(f"Unknown extraction type: {extract_type}")
        
        return extracted, changes


# Register all built-in tools
def register_builtin_tools():
    """Register all built-in tools in the default registry."""
    from .tools import register_tool
    
    register_tool(TavilySearchTool)
    register_tool(WebScraperTool)
    register_tool(DocumentWriterTool)
    register_tool(DataProcessorTool)
    register_tool(TextEditorTool)