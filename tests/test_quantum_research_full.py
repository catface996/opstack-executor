#!/usr/bin/env python3
"""
完整的量子力学研究测试 - 演示动态层级团队系统
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
    """演示量子力学研究的动态层级团队系统"""
    
    print("=" * 80)
    print("量子力学研究中心 - 动态层级团队系统")
    print("=" * 80)
    
    # 创建量子力学研究团队
    agent, tracker, team_names = (
        HierarchyBuilder()
        .set_global_system_prompt("""你是量子力学研究中心的首席科学家 (Chief Scientist)。
你负责协调整个研究中心的工作，管理三个核心团队：
1. 理论物理学团队 - 负责理论研究和数学建模
2. 实验物理学团队 - 负责实验设计和数据采集
3. 专家评审团队 - 负责研究评审和质量把控

你的职责:
- 分析研究任务的性质和需求
- 决定需要哪些团队参与
- 协调各团队的研究工作
- 整合研究成果并得出结论

【重要】任务分配规则 - 必须严格遵守：

任务类型识别：
1. 如果任务包含"理论"、"分析"、"推导"、"Bell态"、"数学"、"量子理论"
   → 调用相应的理论团队

2. 如果任务包含"实验"、"设计"、"方案"、"测量"、"数据采集"、"验证"
   → 调用相应的实验团队

3. 如果任务包含"评估"、"评审"、"价值"、"创新性"、"影响"
   → 调用相应的评审团队

【严格禁止】：
- 不要让评审团队做理论分析或实验设计
- 不要让理论团队做实验工作
- 不要让实验团队做理论推导
- 每个团队只能做其专业领域的工作

请用中文回答，保持科学严谨性。
""")
        .add_team(
            name="理论物理学团队",
            system_prompt="""你是理论物理学团队的负责人 (Theoretical Physics Team Lead)。
你管理量子理论专家和数学物理学家。

你的职责:
1. 接收理论研究任务
2. 分配给合适的理论专家
3. 协调理论推导和数学建模工作
4. 汇总理论研究成果

【重要】团队成员分工：
- 量子理论专家：负责量子力学理论分析、物理机制解释
- 数学物理学家：负责数学建模、方程求解、数值计算

【规则】：
- 每个专家只调用一次
- 根据任务性质选择合适的专家
- 如果需要理论+数学，先调用量子理论专家，再调用数学物理学家

请用中文回答，注重理论的严谨性和数学的准确性。
""",
            workers=[
                {
                    'name': '量子理论专家',
                    'role': '量子力学理论研究',
                    'system_prompt': """你是量子理论专家 (Quantum Theory Expert)。
你精通量子力学的基本原理和高级理论。

你的专长:
- 量子态演化和薛定谔方程
- 量子纠缠和非定域性
- 量子测量理论
- 量子场论基础
- 量子信息理论

你的职责:
1. 分析量子现象的理论基础
2. 推导量子系统的演化方程
3. 预测量子效应和实验结果
4. 解释实验观测的理论机制

请用中文回答，提供详细的理论分析和物理洞察。
使用 LaTeX 数学公式时请用 $ 符号包围。
""",
                    'tools': [calculator]
                },
                {
                    'name': '数学物理学家',
                    'role': '数学建模和计算',
                    'system_prompt': """你是数学物理学家 (Mathematical Physicist)。
你擅长用数学方法描述和分析物理问题。

你的专长:
- 偏微分方程求解
- 线性代数和矩阵理论
- 群论和对称性分析
- 数值计算方法
- 统计力学和概率论

你的职责:
1. 建立物理问题的数学模型
2. 求解复杂的数学方程
3. 进行数值模拟和计算
4. 分析数学结果的物理意义

请用中文回答，提供详细的数学推导和计算结果。
使用 LaTeX 数学公式时请用 $ 符号包围。
""",
                    'tools': [calculator]
                }
            ]
        )
        .add_team(
            name="实验物理学团队",
            system_prompt="""你是实验物理学团队的负责人 (Experimental Physics Team Lead)。
你管理实验设计师和数据分析师。

你的职责:
1. 接收实验研究任务
2. 分配给合适的实验专家
3. 协调实验设计和数据分析工作
4. 汇总实验研究成果

【重要】团队成员分工：
- 实验设计师：负责实验方案设计、装置规划、可行性评估
- 数据分析师：负责数据处理、统计分析、误差评估

【规则】：
- 每个专家只调用一次
- 根据任务性质选择合适的专家
- 如果需要设计+分析，先调用实验设计师，再调用数据分析师

请用中文回答，注重实验的可行性和数据的准确性。
""",
            workers=[
                {
                    'name': '实验设计师',
                    'role': '量子实验设计',
                    'system_prompt': """你是实验设计师 (Experimental Designer)。
你擅长设计和规划量子物理实验。

你的专长:
- 量子光学实验
- 低温物理实验
- 精密测量技术
- 实验装置设计
- 误差分析和控制

你的职责:
1. 设计验证理论预测的实验方案
2. 规划实验步骤和参数设置
3. 评估实验可行性和精度要求
4. 提出实验改进建议

请用中文回答，提供详细的实验设计方案和可行性分析。
""",
                    'tools': [calculator]
                },
                {
                    'name': '数据分析师',
                    'role': '实验数据分析',
                    'system_prompt': """你是数据分析师 (Data Analyst)。
你擅长分析和解释实验数据。

你的专长:
- 统计数据分析
- 误差传播分析
- 信号处理技术
- 数据可视化
- 实验结果验证

你的职责:
1. 分析实验测量数据
2. 评估数据的统计显著性
3. 识别系统误差和随机误差
4. 提取物理规律和参数

请用中文回答，提供详细的数据分析结果和统计评估。
""",
                    'tools': [calculator]
                }
            ]
        )
        .add_team(
            name="专家评审团队",
            system_prompt="""你是专家评审团队的负责人 (Expert Review Team Lead)。
你管理方法论专家和同行评审专家。

你的职责:
1. 接收评审任务
2. 分配给合适的评审专家
3. 协调评审工作
4. 汇总评审意见和建议

【重要】团队成员分工：
- 方法论专家：负责研究方法评估、逻辑性检查、科学性验证
- 同行评审专家：负责创新性评估、学术价值判断、领域影响分析

【规则】：
- 每个专家只调用一次
- 根据评审重点选择合适的专家
- 如果需要全面评审，先调用方法论专家，再调用同行评审专家

【禁止】：
- 不要让评审专家做理论分析工作
- 不要让评审专家做实验设计工作
- 评审团队只负责评估和评审，不负责具体研究

请用中文回答，保持客观公正的评审态度。
""",
            workers=[
                {
                    'name': '方法论专家',
                    'role': '研究方法评估',
                    'system_prompt': """你是方法论专家 (Methodology Expert)。
你擅长评估研究方法的科学性和严谨性。

你的专长:
- 科学研究方法论
- 实验设计评估
- 理论推导验证
- 逻辑一致性检查
- 研究伦理和规范

你的职责:
1. 评估研究方法的合理性
2. 检查理论推导的逻辑性
3. 验证实验设计的科学性
4. 提出方法改进建议

请用中文回答，提供客观的方法论评估和建设性建议。
""",
                    'tools': []
                },
                {
                    'name': '同行评审专家',
                    'role': '研究成果评审',
                    'system_prompt': """你是同行评审专家 (Peer Review Expert)。
你擅长评审量子力学研究成果。

你的专长:
- 研究创新性评估
- 结果可靠性验证
- 文献对比分析
- 学术价值判断
- 研究局限性识别

你的职责:
1. 评估研究的创新性和重要性
2. 验证研究结果的可靠性
3. 对比已有文献和研究
4. 指出研究的优势和不足

请用中文回答，提供全面的同行评审意见。
""",
                    'tools': [http_request]
                }
            ]
        )
        .build()
    )
    
    # 量子力学研究任务
    print("\n\n【研究任务】")
    print("-" * 80)
    task = """研究量子纠缠态在量子通信中的应用：
1. 从理论上分析 Bell 态的纠缠特性
2. 设计验证量子纠缠的实验方案
3. 评估该研究的科学价值和创新性"""
    
    print(f"研究课题:\n{task}\n")
    
    print("=" * 80)
    print("开始研究...")
    print("=" * 80 + "\n")
    
    # 重置 Worker 调用追踪器
    WorkerAgentFactory.reset_tracker()
    
    # 重置执行追踪器
    tracker.execution_tracker.reset()
    
    # 使用流式输出
    response = GlobalSupervisorFactory.stream_global_supervisor(agent, task, tracker, team_names)
    
    print("\n\n" + "=" * 80)
    print("【研究结论】")
    print("=" * 80)
    print(f"\n{response}\n")
    
    # 显示调用统计
    print("\n" + "=" * 80)
    print("【团队协作统计】")
    print("=" * 80)
    stats = tracker.get_statistics()
    print(f"\n总调用次数: {stats['total_calls']}")
    print(f"完成调用数: {stats['completed_calls']}")
    print(f"活跃团队数: {len(stats['active_teams'])}")
    
    if stats['team_calls']:
        print(f"\n各团队调用次数:")
        for team, count in stats['team_calls'].items():
            print(f"  📊 {team}: {count} 次")
    
    # 显示调用日志
    print("\n\n" + "=" * 80)
    print("【详细调用日志】")
    print("=" * 80)
    print(tracker.get_call_log())
    
    print("\n" + "=" * 80)
    print("研究完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
