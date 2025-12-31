#!/usr/bin/env python3
"""
测试跨 Team 上下文共享功能
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
from strands_tools import calculator, http_request

def main():
    """测试跨 Team 上下文共享"""
    
    print("=" * 80)
    print("测试跨 Team 上下文共享功能")
    print("=" * 80)
    
    # 创建启用上下文共享的系统
    agent, tracker, team_names = (
        HierarchyBuilder(enable_context_sharing=True)  # 启用全局上下文共享
        .set_global_system_prompt("""你是量子力学研究中心的首席科学家。
你负责协调三个团队的工作：
1. 理论物理学团队 - 负责理论研究
2. 实验物理学团队 - 负责实验设计（会接收理论团队的成果）
3. 专家评审团队 - 负责评审（会接收所有团队的成果）

请用中文回答。
""")
        .add_team(
            name="理论物理学团队",
            system_prompt="""你是理论物理学团队的负责人。
你管理量子理论专家。

请用中文回答，提供理论分析。
""",
            workers=[
                {
                    'name': '量子理论专家',
                    'role': '量子力学理论研究',
                    'system_prompt': """你是量子理论专家。
请简洁地分析 Bell 态的纠缠特性（不超过200字）。
使用中文回答。
""",
                    'tools': [calculator]
                }
            ],
            share_context=False  # 理论团队不需要其他团队的上下文
        )
        .add_team(
            name="实验物理学团队",
            system_prompt="""你是实验物理学团队的负责人。
你管理实验设计师。

【重要】：你会收到理论团队的研究成果，请基于这些理论来设计实验。

请用中文回答。
""",
            workers=[
                {
                    'name': '实验设计师',
                    'role': '量子实验设计',
                    'system_prompt': """你是实验设计师。
请简洁地设计验证实验（不超过200字）。
使用中文回答。
""",
                    'tools': [calculator]
                }
            ],
            share_context=True  # 实验团队接收理论团队的上下文
        )
        .add_team(
            name="专家评审团队",
            system_prompt="""你是专家评审团队的负责人。
你管理同行评审专家。

【重要】：你会收到理论团队和实验团队的研究成果，请基于这些成果进行评审。

请用中文回答。
""",
            workers=[
                {
                    'name': '同行评审专家',
                    'role': '研究成果评审',
                    'system_prompt': """你是同行评审专家。
请简洁地评审研究（不超过200字）。
使用中文回答。
""",
                    'tools': []
                }
            ],
            share_context=True  # 评审团队接收所有团队的上下文
        )
        .build()
    )
    
    # 研究任务
    print("\n\n【研究任务】")
    print("-" * 80)
    task = """研究量子纠缠态：
1. 理论团队：分析 Bell 态的纠缠特性
2. 实验团队：基于理论设计验证实验
3. 评审团队：评估整体研究价值"""
    
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
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
