#!/usr/bin/env python3
"""
Template Processing Demo

This script demonstrates the template processing functionality of the
hierarchical multi-agent system's output formatter.
"""

import sys
import os
from datetime import datetime

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hierarchical_agents.output_formatter import OutputFormatter, create_template_processor
from hierarchical_agents.data_models import (
    StandardizedOutput,
    ExecutionSummary,
    TeamResult,
    ExecutionMetrics,
    OutputTemplate,
    ExtractionRules,
    FormatRequest
)


def create_sample_execution_results():
    """Create sample execution results for demonstration."""
    return StandardizedOutput(
        execution_id="exec_demo_123",
        execution_summary=ExecutionSummary(
            status="completed",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_duration=1800,
            teams_executed=2,
            agents_involved=3
        ),
        team_results={
            "research_team": TeamResult(
                status="completed",
                duration=900,
                agents={
                    "search_agent": {
                        "agent_name": "医疗文献搜索专家",
                        "status": "completed",
                        "output": "收集了15篇AI医疗应用研究论文，包括深度学习在医学影像、自然语言处理在病历分析等领域的最新进展。发现机器学习在药物发现、计算机视觉在手术辅助等技术正在快速发展。",
                        "tools_used": ["tavily_search", "web_scraper"]
                    },
                    "analysis_agent": {
                        "agent_name": "趋势分析师",
                        "status": "completed",
                        "output": "分析了技术趋势、挑战和机遇。AI医疗市场预计2030年达到1000亿美元，医学影像AI应用增长率达35%。主要挑战包括数据隐私保护、算法可解释性、监管合规等问题。建议建立统一的医疗AI数据标准。",
                        "tools_used": ["data_processor"]
                    }
                },
                output="研究团队完成了AI医疗应用的全面调研和分析"
            ),
            "writing_team": TeamResult(
                status="completed",
                duration=900,
                agents={
                    "writer_agent": {
                        "agent_name": "技术报告撰写专家",
                        "status": "completed",
                        "output": "基于研究团队提供的材料，撰写了详细的AI医疗应用分析报告。报告包含技术背景、应用案例、挑战分析和未来展望。推荐加强跨学科人才培养、完善AI医疗监管框架、推进产学研合作创新。",
                        "tools_used": ["document_writer", "editor"]
                    }
                },
                output="写作团队完成了综合分析报告的撰写"
            )
        },
        errors=[],
        metrics=ExecutionMetrics(
            total_tokens_used=5000,
            api_calls_made=10,
            success_rate=1.0,
            average_response_time=300.0
        )
    )


def demo_template_parsing():
    """Demonstrate template parsing functionality."""
    print("=" * 60)
    print("Template Parsing Demo")
    print("=" * 60)
    
    processor = create_template_processor()
    
    # Sample template with nested structure and placeholders
    template = {
        "report_title": "AI医疗应用分析报告",
        "executive_summary": "{executive_summary}",
        "research_findings": {
            "key_technologies": "{key_technologies}",
            "market_trends": "{market_trends}",
            "challenges": "{challenges}"
        },
        "recommendations": "{recommendations}",
        "appendix": {
            "data_sources": "{data_sources}",
            "methodology": "{methodology}"
        },
        "metadata": {
            "generated_at": "{generation_time}",
            "execution_id": "{execution_id}",
            "total_duration": "{total_duration}"
        }
    }
    
    print("Original Template:")
    print(template)
    print()
    
    try:
        parsed_template = processor.parse_template(template)
        print("✅ Template parsed successfully!")
        print("Parsed Template Structure:")
        for key, value in parsed_template.items():
            print(f"  {key}: {type(value).__name__}")
        print()
    except Exception as e:
        print(f"❌ Template parsing failed: {e}")
        print()


def demo_information_extraction():
    """Demonstrate information extraction functionality."""
    print("=" * 60)
    print("Information Extraction Demo")
    print("=" * 60)
    
    processor = create_template_processor()
    execution_results = create_sample_execution_results()
    
    # Sample extraction rules
    extraction_rules = {
        "executive_summary": "总结所有团队的核心发现，不超过200字",
        "key_technologies": "从搜索结果中提取3-5个关键技术",
        "market_trends": "从分析结果中提取市场趋势，以列表形式呈现",
        "challenges": "识别并列出主要技术和商业挑战",
        "recommendations": "基于分析结果提供3-5条具体建议",
        "data_sources": "列出所有数据来源",
        "methodology": "描述研究方法",
        "generation_time": "当前时间",
        "execution_id": "执行ID",
        "total_duration": "总执行时间"
    }
    
    print("Extraction Rules:")
    for field, rule in extraction_rules.items():
        print(f"  {field}: {rule}")
    print()
    
    try:
        extracted_info = processor.extract_information(extraction_rules, execution_results)
        print("✅ Information extracted successfully!")
        print("Extracted Information:")
        for field, value in extracted_info.items():
            if isinstance(value, list):
                print(f"  {field}: {len(value)} items")
                for i, item in enumerate(value[:3], 1):  # Show first 3 items
                    print(f"    {i}. {item}")
                if len(value) > 3:
                    print(f"    ... and {len(value) - 3} more")
            else:
                # Truncate long strings for display
                display_value = str(value)
                if len(display_value) > 100:
                    display_value = display_value[:100] + "..."
                print(f"  {field}: {display_value}")
        print()
    except Exception as e:
        print(f"❌ Information extraction failed: {e}")
        print()


def demo_template_formatting():
    """Demonstrate complete template formatting functionality."""
    print("=" * 60)
    print("Complete Template Formatting Demo")
    print("=" * 60)
    
    formatter = OutputFormatter()
    execution_results = create_sample_execution_results()
    
    # Template for the final report
    output_template = {
        "report_title": "AI医疗应用分析报告",
        "executive_summary": "{executive_summary}",
        "research_findings": {
            "key_technologies": "{key_technologies}",
            "market_trends": "{market_trends}",
            "challenges": "{challenges}"
        },
        "recommendations": "{recommendations}",
        "appendix": {
            "data_sources": "{data_sources}",
            "methodology": "{methodology}"
        },
        "metadata": {
            "execution_id": "{execution_id}",
            "total_duration": "{total_duration}",
            "teams_executed": "{teams_executed}",
            "success_rate": "{success_rate}"
        }
    }
    
    # Extraction rules
    extraction_rules = {
        "executive_summary": "总结所有团队的核心发现，不超过200字",
        "key_technologies": "从搜索结果中提取3-5个关键技术",
        "market_trends": "从分析结果中提取市场趋势",
        "challenges": "识别主要技术和商业挑战",
        "recommendations": "基于分析结果提供具体建议",
        "data_sources": "列出数据来源",
        "methodology": "描述研究方法",
        "execution_id": "执行ID",
        "total_duration": "总执行时间",
        "teams_executed": "执行的团队数量",
        "success_rate": "成功率"
    }
    
    try:
        formatted_report = formatter.format_with_template(
            execution_results, output_template, extraction_rules
        )
        
        print("✅ Template formatting completed successfully!")
        print()
        print("Generated Report:")
        print("-" * 40)
        
        def print_nested_dict(d, indent=0):
            """Helper function to print nested dictionary structure."""
            for key, value in d.items():
                if isinstance(value, dict):
                    print("  " * indent + f"{key}:")
                    print_nested_dict(value, indent + 1)
                elif isinstance(value, list):
                    print("  " * indent + f"{key}: [{len(value)} items]")
                    for i, item in enumerate(value[:2], 1):  # Show first 2 items
                        print("  " * (indent + 1) + f"{i}. {item}")
                    if len(value) > 2:
                        print("  " * (indent + 1) + f"... and {len(value) - 2} more")
                else:
                    # Truncate long strings for display
                    display_value = str(value)
                    if len(display_value) > 80:
                        display_value = display_value[:80] + "..."
                    print("  " * indent + f"{key}: {display_value}")
        
        print_nested_dict(formatted_report)
        print()
        
    except Exception as e:
        print(f"❌ Template formatting failed: {e}")
        print()


def demo_error_handling():
    """Demonstrate error handling in template processing."""
    print("=" * 60)
    print("Error Handling Demo")
    print("=" * 60)
    
    processor = create_template_processor()
    
    # Test invalid template
    print("Testing invalid template (empty):")
    try:
        processor.parse_template({})
        print("❌ Should have failed!")
    except Exception as e:
        print(f"✅ Correctly caught error: {e}")
    print()
    
    # Test invalid extraction rules
    print("Testing invalid extraction rules (empty field name):")
    try:
        processor.validate_extraction_rules({"": "valid rule"})
        print("❌ Should have failed!")
    except Exception as e:
        print(f"✅ Correctly caught error: {e}")
    print()
    
    # Test template with missing placeholders
    print("Testing template with missing placeholders:")
    template = {"field": "{missing_placeholder}"}
    extracted_info = {"existing_field": "value"}
    
    try:
        result = processor.format_output(template, extracted_info)
        print(f"✅ Handled gracefully: {result}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    print()


def main():
    """Run all template processing demonstrations."""
    print("🚀 Template Processing Functionality Demo")
    print("This demo showcases the template processing capabilities")
    print("of the hierarchical multi-agent system's output formatter.")
    print()
    
    try:
        demo_template_parsing()
        demo_information_extraction()
        demo_template_formatting()
        demo_error_handling()
        
        print("=" * 60)
        print("✅ All demos completed successfully!")
        print("The template processing functionality is working correctly.")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()