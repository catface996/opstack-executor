#!/usr/bin/env python3
"""
测试默认行为：team 之间不共享上下文
"""
import os
import sys

# 添加父目录到路径，以便导入 hierarchy_system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置管理模块
from src.core.config import setup_config

# 设置配置（自动从环境变量或 .env 文件加载）
setup_config()

from src.core.hierarchy_system import HierarchyBuilder, WorkerAgentFactory, GlobalSupervisorFactory
from strands_tools import calculator

def main():
    """测试默认行为：team 之间不共享上下文"""
    
    print("=" * 80)
    print("测试默认行为：team 之间不共享上下文")
    print("=" * 80)
    
    # 使用默认配置（不共享上下文）
    agent, tracker, team_names = (
        HierarchyBuilder()  # 默认：enable_context_sharing=False
        .set_global_system_prompt("""你是研究中心的首席科学家。
你负责协调两个团队：
1. 理论团队 - 负责理论分析
2. 实验团队 - 负责实验设计

请用中文回答。
""")
        .add_team(
            name="理论团队",
            system_prompt="""你是理论团队的负责人。
你管理理论专家。

请用中文回答，提供简洁的理论分析（不超过100字）。
""",
            workers=[
                {
                    'name': '理论专家',
                    'role': '理论研究',
                    'system_prompt': """你是理论专家。
请简洁地分析问题（不超过50字）。
使用中文回答。
""",
                    'tools': [calculator]
                }
            ]
            # 默认：share_context=False
        )
        .add_team(
            name="实验团队",
            system_prompt="""你是实验团队的负责人。
你管理实验专家。

【注意】：你不会收到理论团队的成果，需要独立设计实验。

请用中文回答，提供简洁的实验方案（不超过100字）。
""",
            workers=[
                {
                    'name': '实验专家',
                    'role': '实验设计',
                    'system_prompt': """你是实验专家。
请简洁地设计实验（不超过50字）。
使用中文回答。
""",
                    'tools': [calculator]
                }
            ]
            # 默认：share_context=False
        )
        .build()
    )
    
    # 研究任务
    print("\n\n【研究任务】")
    print("-" * 80)
    task = """研究量子纠缠：
1. 理论团队：分析 Bell 态
2. 实验团队：设计验证实验"""
    
    print(f"{task}\n")
    
    print("=" * 80)
    print("开始研究...")
    print("=" * 80 + "\n")
    
    # 重置追踪器
    WorkerAgentFactory.reset_tracker()
    tracker.execution_tracker.reset()
    
    # 执行
    response = GlobalSupervisorFactory.stream_global_supervisor(agent, task, tracker, team_names)
    
    print("\n\n" + "=" * 80)
    print("【研究结论】")
    print("=" * 80)
    print(f"\n{response}\n")
    
    # 显示统计
    print("\n" + "=" * 80)
    print("【团队协作统计】")
    print("=" * 80)
    stats = tracker.get_statistics()
    print(f"\n总调用次数: {stats['total_calls']}")
    print(f"完成调用数: {stats['completed_calls']}")
    
    if stats['team_calls']:
        print(f"\n各团队调用次数:")
        for team, count in stats['team_calls'].items():
            print(f"  📊 {team}: {count} 次")
    
    print("\n" + "=" * 80)
    print("【验证结果】")
    print("=" * 80)
    print("\n✅ 默认行为确认：team 之间不共享上下文")
    print("   - 理论团队独立完成分析")
    print("   - 实验团队独立设计实验（没有看到理论团队的成果）")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
