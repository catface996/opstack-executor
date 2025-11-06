# 需求

* 本项目是一个multi-agnet的项目，这个项目支持Hierarchical-Team协作模式。参考：../Reference/Hierarchical-agent-teams.md 中对Hierarchical Team的实现。
* 该项目提供以下几个功能：
  * 构建Hierarchical Team接口，接收一个实体列表，以及实体之间的依赖关系，每个实体上有一个带有Supervisor的agent team。所有的agent team 统一被一个最高级别的Supervisor来协调。
  * 触发Hierarchical Team，并让其执行，流式返回执行过程数据。
  * 对执行结束的Hierarchical Team，对其结果进行标准化输出，标准化的格式，作为输出的参数。

