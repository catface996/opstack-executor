#!/usr/bin/env python3
"""
测试团队执行模式 - 顺序执行 vs 并行执行
"""
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import setup_config
from src.core.hierarchy_system import HierarchyBuilder
from strands_tools import calculator

# 设置配置
setup_config()


def test_sequential_execution():
    """测试顺序执行模式（默认）"""
    print("=" * 80)
    print("测试 1: 顺序执行模式（默认）")
    print("=" * 80)
    
    agent, tracker, team_names = (
        HierarchyBuilder(parallel_execution=False)  # 显式设置为顺序执行
        .set_global_system_prompt("""你是项目协调者。
你需要协调两个团队完成任务：
1. 数据分析团队 - 负责数据分析
2. 报告撰写团队 - 负责撰写报告

【重要】：你必须按顺序执行，先完成数据分析，再撰写报告。
""")
        .add_team(
            name="数据分析团队",
            system_prompt="你是数据分析团队主管，协调团队成员完成数据分析任务。",
            workers=[
                {
                    'name': '数据分析师',
                    'role': '数据分析专家',
                    'system_prompt': '你是数据分析师，负责分析数据并提供洞察。',
                    'tools': [calculator]
                }
            ]
        )
        .add_team(
            name="报告撰写团队",
            system_prompt="你是报告撰写团队主管，协调团队成员撰写报告。",
            workers=[
                {
                    'name': '报告撰写员',
                    'role': '报告撰写专家',
                    'system_prompt': '你是报告撰写员，负责根据数据分析结果撰写报告。',
                }
            ]
        )
        .build()
    )
    
    print(f"\n执行模式: 顺序执行")
    print(f"团队列表: {team_names}")
    print("\n" + "=" * 80 + "\n")


def test_parallel_execution():
    """测试并行执行模式"""
    print("=" * 80)
    print("测试 2: 并行执行模式")
    print("=" * 80)
    
    agent, tracker, team_names = (
        HierarchyBuilder(parallel_execution=True)  # 设置为并行执行
        .set_global_system_prompt("""你是项目协调者。
你需要协调两个团队完成任务：
1. 前端开发团队 - 负责前端开发
2. 后端开发团队 - 负责后端开发

【重要】：这两个团队可以并行工作，互不依赖。
""")
        .add_team(
            name="前端开发团队",
            system_prompt="你是前端开发团队主管，协调团队成员完成前端开发。",
            workers=[
                {
                    'name': '前端工程师',
                    'role': '前端开发专家',
                    'system_prompt': '你是前端工程师，负责开发用户界面。',
                }
            ]
        )
        .add_team(
            name="后端开发团队",
            system_prompt="你是后端开发团队主管，协调团队成员完成后端开发。",
            workers=[
                {
                    'name': '后端工程师',
                    'role': '后端开发专家',
                    'system_prompt': '你是后端工程师，负责开发服务器端逻辑。',
                }
            ]
        )
        .build()
    )
    
    print(f"\n执行模式: 并行执行")
    print(f"团队列表: {team_names}")
    print("\n" + "=" * 80 + "\n")


def test_builder_method():
    """测试使用 set_parallel_execution 方法"""
    print("=" * 80)
    print("测试 3: 使用 set_parallel_execution 方法")
    print("=" * 80)
    
    agent, tracker, team_names = (
        HierarchyBuilder()
        .set_global_system_prompt("你是协调者")
        .set_parallel_execution(True)  # 使用方法设置
        .add_team(
            name="团队A",
            system_prompt="团队A主管",
            workers=[
                {
                    'name': '成员A',
                    'role': '专家A',
                    'system_prompt': '你是专家A',
                }
            ]
        )
        .build()
    )
    
    print(f"\n执行模式: 并行执行（通过方法设置）")
    print(f"团队列表: {team_names}")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    try:
        print("\n" + "=" * 80)
        print("团队执行模式测试")
        print("=" * 80 + "\n")
        
        # 测试 1: 顺序执行（默认）
        test_sequential_execution()
        
        # 测试 2: 并行执行
        test_parallel_execution()
        
        # 测试 3: 使用方法设置
        test_builder_method()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成")
        print("=" * 80)
        print("\n说明:")
        print("- 顺序执行: Agent 会按顺序调用团队，一个完成后再调用下一个")
        print("- 并行执行: Agent 可以同时调用多个团队，提高效率")
        print("- 默认模式: 顺序执行（更安全，适合有依赖关系的任务）")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
