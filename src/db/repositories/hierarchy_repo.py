"""
Hierarchy Repository - 层级团队数据访问层
"""

import uuid
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from ..models import HierarchyTeam


def generate_agent_id() -> str:
    """生成默认的 agent_id"""
    return str(uuid.uuid4())


def check_agent_ids_unique_in_hierarchy(config: dict) -> Tuple[bool, Optional[str]]:
    """
    检查 agent_id 在 Hierarchy 内是否唯一

    Args:
        config: 层级配置，包含 global_supervisor_agent 和 teams

    Returns:
        (是否唯一, 重复的 agent_id 或 None)
    """
    all_agent_ids = []

    # 收集 Global Supervisor agent_id
    global_agent = config.get('global_supervisor_agent', {})
    if global_agent.get('agent_id'):
        all_agent_ids.append(global_agent['agent_id'])

    # 收集所有 Team Supervisor 和 Worker 的 agent_id
    for team in config.get('teams', []):
        team_agent = team.get('team_supervisor_agent', {})
        if team_agent.get('agent_id'):
            all_agent_ids.append(team_agent['agent_id'])
        for worker in team.get('workers', []):
            if worker.get('agent_id'):
                all_agent_ids.append(worker['agent_id'])

    # 检查是否有重复
    seen = set()
    for agent_id in all_agent_ids:
        if agent_id in seen:
            return False, agent_id
        seen.add(agent_id)

    return True, None


def ensure_agent_ids(config: dict) -> dict:
    """
    确保所有 Agent 都有 agent_id，如果没有则自动生成

    Args:
        config: 层级配置

    Returns:
        填充了 agent_id 的配置
    """
    # Global Supervisor
    if 'global_supervisor_agent' in config:
        if not config['global_supervisor_agent'].get('agent_id'):
            config['global_supervisor_agent']['agent_id'] = generate_agent_id()

    # Teams
    for team in config.get('teams', []):
        # Team Supervisor
        if 'team_supervisor_agent' in team:
            if not team['team_supervisor_agent'].get('agent_id'):
                team['team_supervisor_agent']['agent_id'] = generate_agent_id()
        # Workers
        for worker in team.get('workers', []):
            if not worker.get('agent_id'):
                worker['agent_id'] = generate_agent_id()

    return config


class HierarchyRepository:
    """层级团队仓库"""

    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, description: Optional[str], config: dict) -> HierarchyTeam:
        """
        创建层级团队

        Args:
            name: 层级团队名称
            description: 描述
            config: 层级配置 JSON
        """
        # 确保所有 Agent 都有 agent_id
        config = ensure_agent_ids(config)

        hierarchy = HierarchyTeam(
            name=name,
            description=description,
            config=config
        )
        self.session.add(hierarchy)
        self.session.commit()
        self.session.refresh(hierarchy)
        return hierarchy

    def get_by_id(self, hierarchy_id: str) -> Optional[HierarchyTeam]:
        """根据 ID 获取层级团队"""
        return self.session.query(HierarchyTeam) \
            .filter(HierarchyTeam.id == hierarchy_id) \
            .first()

    def get_by_name(self, name: str) -> Optional[HierarchyTeam]:
        """根据名称获取层级团队"""
        return self.session.query(HierarchyTeam) \
            .filter(HierarchyTeam.name == name) \
            .first()

    def list(
        self,
        page: int = 1,
        size: int = 20,
        is_active: Optional[bool] = None
    ) -> tuple[List[HierarchyTeam], int]:
        """
        获取层级团队列表

        Returns:
            (层级列表, 总数)
        """
        query = self.session.query(HierarchyTeam)

        if is_active is not None:
            query = query.filter(HierarchyTeam.is_active == is_active)

        total = query.count()
        hierarchies = query.order_by(HierarchyTeam.created_at.desc()) \
                          .offset((page - 1) * size) \
                          .limit(size) \
                          .all()

        return hierarchies, total

    def update(self, hierarchy_id: str, data: dict) -> Optional[HierarchyTeam]:
        """
        更新层级团队

        Args:
            hierarchy_id: 层级团队 ID
            data: 更新数据，可包含 name, description, config, is_active
        """
        hierarchy = self.get_by_id(hierarchy_id)
        if not hierarchy:
            return None

        # 更新字段
        if 'name' in data:
            hierarchy.name = data['name']
        if 'description' in data:
            hierarchy.description = data['description']
        if 'config' in data:
            # 确保所有 Agent 都有 agent_id
            hierarchy.config = ensure_agent_ids(data['config'])
        if 'is_active' in data:
            hierarchy.is_active = data['is_active']

        # 更新版本号
        hierarchy.version += 1

        self.session.commit()
        self.session.refresh(hierarchy)
        return hierarchy

    def delete(self, hierarchy_id: str) -> bool:
        """删除层级团队"""
        hierarchy = self.get_by_id(hierarchy_id)
        if not hierarchy:
            return False

        self.session.delete(hierarchy)
        self.session.commit()
        return True

    def exists(self, hierarchy_id: str) -> bool:
        """检查层级团队是否存在"""
        return self.session.query(HierarchyTeam) \
            .filter(HierarchyTeam.id == hierarchy_id).count() > 0
