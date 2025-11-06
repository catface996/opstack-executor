"""
Example usage of the Hierarchical Teams API.

This example demonstrates how to use the API endpoints to create
and manage hierarchical teams.
"""

import json
import requests
from typing import Dict, Any


def create_sample_team_config() -> Dict[str, Any]:
    """Create a sample team configuration for testing."""
    return {
        "team_name": "ai_research_analysis_team",
        "description": "AI research and analysis team for comprehensive studies",
        "top_supervisor_config": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "system_prompt": "You are a top-level supervisor coordinating AI research and analysis. You need to intelligently select the most appropriate sub-team based on task requirements and team capabilities.",
            "user_prompt": "Please coordinate the entire hierarchical team to execute AI research and analysis tasks. Select the most suitable sub-team to begin execution based on their expertise and dependencies. Only return the team name.",
            "max_iterations": 10
        },
        "sub_teams": [
            {
                "id": "team_research_a7b9c2d4e5f6",
                "name": "Research Team",
                "description": "Responsible for information gathering and research",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "You are a research team supervisor coordinating information search and data analysis. You need to intelligently select the most appropriate team member based on task characteristics and member expertise.",
                    "user_prompt": "Please coordinate the research team to execute information gathering and analysis work. Select the most suitable member to begin execution based on their expertise. Only return the member name.",
                    "max_iterations": 8
                },
                "agent_configs": [
                    {
                        "agent_id": "agent_search_001",
                        "agent_name": "AI Literature Search Expert",
                        "llm_config": {
                            "provider": "openrouter",
                            "model": "anthropic/claude-3-sonnet",
                            "base_url": "https://openrouter.ai/api/v1",
                            "temperature": 0.3,
                            "max_tokens": 2000
                        },
                        "system_prompt": "You are a professional information search expert, skilled in using various search tools to collect accurate and relevant information. Please always provide reliable information sources and perform initial screening of search results.",
                        "user_prompt": "Please search for the latest research on artificial intelligence applications in healthcare. Focus on collecting research papers and technical advances in areas such as deep learning in medical imaging and natural language processing in medical record analysis. Ensure reliable information sources and perform initial screening.",
                        "tools": ["tavily_search", "web_scraper"],
                        "max_iterations": 5
                    },
                    {
                        "agent_id": "agent_analyze_001",
                        "agent_name": "Trend Analyst",
                        "llm_config": {
                            "provider": "aws_bedrock",
                            "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                            "region": "us-east-1",
                            "temperature": 0.5,
                            "max_tokens": 3000
                        },
                        "system_prompt": "You are a data analysis expert capable of extracting key insights from complex information, identifying trends and patterns. Please provide structured analysis results.",
                        "user_prompt": "Please analyze the technical trends, challenges, and opportunities in AI healthcare applications. Based on collected research materials, identify key technology development patterns, analyze challenges such as data privacy, algorithm interpretability, regulatory compliance, and provide structured analysis results.",
                        "tools": ["data_processor"],
                        "max_iterations": 3
                    }
                ]
            },
            {
                "id": "team_writing_x8y9z1a2b3c4",
                "name": "Writing Team",
                "description": "Responsible for document writing and organization",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.5
                    },
                    "system_prompt": "You are a writing team supervisor coordinating document writing work. You need to intelligently select the most appropriate writing expert based on the type and complexity of writing tasks.",
                    "user_prompt": "Please coordinate the writing team to execute document writing work. Select the most suitable member to begin execution based on member expertise and input materials. Only return the member name.",
                    "max_iterations": 6
                },
                "agent_configs": [
                    {
                        "agent_id": "agent_write_001",
                        "agent_name": "Technical Report Writing Expert",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.7,
                            "max_tokens": 4000
                        },
                        "system_prompt": "You are a professional technical writing expert, skilled in transforming complex technical information into clear and understandable documents. Please ensure content structure is reasonable and logic is clear.",
                        "user_prompt": "Please write a detailed analysis report on artificial intelligence applications in healthcare based on materials provided by the research team. The report should include four main sections: technical background, application cases, challenge analysis, and future prospects, ensuring reasonable content structure and clear logic.",
                        "tools": ["document_writer", "editor"],
                        "max_iterations": 5
                    }
                ]
            }
        ],
        "dependencies": {
            "team_writing_x8y9z1a2b3c4": ["team_research_a7b9c2d4e5f6"]
        },
        "global_config": {
            "max_execution_time": 3600,
            "enable_streaming": True,
            "output_format": "detailed"
        }
    }


def test_api_endpoints(base_url: str = "http://localhost:8000"):
    """Test the API endpoints with sample data."""
    
    print("🚀 Testing Hierarchical Teams API")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✓ API Status: {health_data['data']['status']}")
        else:
            print(f"   ✗ Health check failed: {response.text}")
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to API server. Make sure it's running on http://localhost:8000")
        return
    
    # Test 2: Teams health check
    print("\n2. Testing teams API health check...")
    try:
        response = requests.get(f"{base_url}/api/v1/teams/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✓ Teams API Status: {health_data['data']['status']}")
        else:
            print(f"   ✗ Teams health check failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Teams health check error: {e}")
    
    # Test 3: Create hierarchical team
    print("\n3. Testing team creation...")
    team_config = create_sample_team_config()
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/hierarchical-teams",
            json=team_config,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print(f"   ✓ Team created successfully!")
            print(f"   ✓ Team ID: {result['data']['team_id']}")
            print(f"   ✓ Team Name: {result['data']['team_name']}")
            print(f"   ✓ Sub-teams: {result['data']['sub_teams_count']}")
            print(f"   ✓ Total Agents: {result['data']['total_agents']}")
            print(f"   ✓ Execution Order: {result['data']['execution_order']}")
            
            team_id = result['data']['team_id']
            
            # Test 4: Get team info
            print(f"\n4. Testing team info retrieval...")
            info_response = requests.get(f"{base_url}/api/v1/hierarchical-teams/{team_id}")
            print(f"   Status: {info_response.status_code}")
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                print(f"   ✓ Team info retrieved: {info_data['data']['team_name']}")
            else:
                print(f"   ✗ Failed to get team info: {info_response.text}")
            
        else:
            result = response.json()
            print(f"   ✗ Team creation failed: {result.get('message', 'Unknown error')}")
            if 'detail' in result:
                print(f"   ✗ Details: {result['detail']}")
    
    except Exception as e:
        print(f"   ✗ Team creation error: {e}")
    
    # Test 5: List teams
    print("\n5. Testing teams listing...")
    try:
        response = requests.get(f"{base_url}/api/v1/hierarchical-teams")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Teams listed successfully")
            print(f"   ✓ Total teams: {result['data']['total_count']}")
        else:
            print(f"   ✗ Failed to list teams: {response.text}")
    
    except Exception as e:
        print(f"   ✗ Teams listing error: {e}")
    
    # Test 6: OpenAPI documentation
    print("\n6. Testing OpenAPI documentation...")
    try:
        response = requests.get(f"{base_url}/openapi.json")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            schema = response.json()
            print(f"   ✓ OpenAPI schema generated")
            print(f"   ✓ API Title: {schema.get('info', {}).get('title', 'N/A')}")
            print(f"   ✓ API Version: {schema.get('info', {}).get('version', 'N/A')}")
            
            # Check if our endpoints are documented
            paths = schema.get('paths', {})
            if '/api/v1/hierarchical-teams' in paths:
                print("   ✓ Teams endpoints are documented")
            else:
                print("   ✗ Teams endpoints not found in documentation")
        else:
            print(f"   ✗ Failed to get OpenAPI schema: {response.text}")
    
    except Exception as e:
        print(f"   ✗ OpenAPI documentation error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 API testing completed!")
    print("\nTo start the API server, run:")
    print("   python -m uvicorn src.hierarchical_agents.main:app --reload")
    print("\nThen visit:")
    print("   http://localhost:8000/docs - Interactive API documentation")
    print("   http://localhost:8000/redoc - Alternative API documentation")


def create_team_with_validation_error():
    """Example of creating a team with validation errors."""
    
    print("\n🔍 Testing validation error handling...")
    
    # Invalid configuration - missing required fields
    invalid_config = {
        "team_name": "",  # Empty name
        "description": "Test team"
        # Missing other required fields
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/hierarchical-teams",
            json=invalid_config,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 400:
            result = response.json()
            print(f"✓ Validation error handled correctly")
            print(f"✓ Error code: {result['code']}")
            print(f"✓ Error message: {result['message']}")
        else:
            print(f"✗ Unexpected response: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API server")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    # Test the API endpoints
    test_api_endpoints()
    
    # Test validation error handling
    create_team_with_validation_error()
    
    # Print sample configuration
    print("\n📋 Sample Team Configuration:")
    print("=" * 50)
    sample_config = create_sample_team_config()
    print(json.dumps(sample_config, indent=2, ensure_ascii=False))