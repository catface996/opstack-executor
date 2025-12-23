"""
Hierarchy Repository - 层级团队数据访问层
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from ..models import HierarchyTeam, Team, Worker


class HierarchyRepository:
    """层级团队仓库"""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _extract_hierarchy_llm_config(data: dict) -> dict:
        """
        从请求数据中提取 Global Supervisor 的 LLM 配置

        将嵌套的 llm_config 展开为数据库字段：
        - llm_config.model_id -> global_model_id
        - llm_config.temperature -> global_temperature
        - llm_config.max_tokens -> global_max_tokens
        - llm_config.top_p -> global_top_p
        """
        llm_config = data.pop('llm_config', None)
        if llm_config:
            if isinstance(llm_config, dict):
                if 'model_id' in llm_config:
                    data['global_model_id'] = llm_config['model_id']
                if 'temperature' in llm_config:
                    data['global_temperature'] = llm_config['temperature']
                if 'max_tokens' in llm_config:
                    data['global_max_tokens'] = llm_config['max_tokens']
                if 'top_p' in llm_config:
                    data['global_top_p'] = llm_config['top_p']
        return data

    @staticmethod
    def _extract_team_llm_config(data: dict) -> dict:
        """
        从请求数据中提取 Team Supervisor 的 LLM 配置

        将嵌套的 llm_config 展开为数据库字段
        """
        llm_config = data.pop('llm_config', None)
        if llm_config:
            if isinstance(llm_config, dict):
                if 'model_id' in llm_config:
                    data['model_id'] = llm_config['model_id']
                if 'temperature' in llm_config:
                    data['temperature'] = llm_config['temperature']
                if 'max_tokens' in llm_config:
                    data['max_tokens'] = llm_config['max_tokens']
                if 'top_p' in llm_config:
                    data['top_p'] = llm_config['top_p']
        return data

    @staticmethod
    def _extract_worker_llm_config(data: dict) -> dict:
        """
        从请求数据中提取 Worker 的 LLM 配置

        将嵌套的 llm_config 展开为数据库字段
        """
        llm_config = data.pop('llm_config', None)
        if llm_config:
            if isinstance(llm_config, dict):
                if 'model_id' in llm_config:
                    data['model_id'] = llm_config['model_id']
                if 'temperature' in llm_config:
                    data['temperature'] = llm_config['temperature']
                if 'max_tokens' in llm_config:
                    data['max_tokens'] = llm_config['max_tokens']
                if 'top_p' in llm_config:
                    data['top_p'] = llm_config['top_p']
        return data

    def create(self, data: dict) -> HierarchyTeam:
        """
        创建层级团队（包含嵌套的 Teams 和 Workers）

        Args:
            data: 层级配置数据，格式:
                {
                    'name': str,
                    'global_prompt': str,
                    'llm_config': {'model_id': str, 'temperature': float, ...},
                    'teams': [
                        {
                            'name': str,
                            'supervisor_prompt': str,
                            'llm_config': {...},
                            'workers': [
                                {'name': str, 'role': str, 'system_prompt': str, 'llm_config': {...}}
                            ]
                        }
                    ]
                }
        """
        teams_data = data.pop('teams', [])

        # 提取 Global Supervisor LLM 配置
        data = self._extract_hierarchy_llm_config(data)

        # 创建主记录
        hierarchy = HierarchyTeam(**data)
        self.session.add(hierarchy)
        self.session.flush()  # 获取 ID

        # 创建 Teams 和 Workers
        for i, team_data in enumerate(teams_data):
            workers_data = team_data.pop('workers', [])
            team_data['hierarchy_id'] = hierarchy.id
            team_data['order_index'] = i

            # 提取 Team Supervisor LLM 配置
            team_data = self._extract_team_llm_config(team_data)

            team = Team(**team_data)
            self.session.add(team)
            self.session.flush()

            for j, worker_data in enumerate(workers_data):
                worker_data['team_id'] = team.id
                worker_data['order_index'] = j

                # 提取 Worker LLM 配置
                worker_data = self._extract_worker_llm_config(worker_data)

                worker = Worker(**worker_data)
                self.session.add(worker)

        self.session.commit()
        self.session.refresh(hierarchy)
        return hierarchy

    def get_by_id(self, hierarchy_id: str) -> Optional[HierarchyTeam]:
        """根据 ID 获取层级团队（含完整配置）"""
        return self.session.query(HierarchyTeam) \
            .options(
                joinedload(HierarchyTeam.teams).joinedload(Team.workers),
                joinedload(HierarchyTeam.global_model)
            ) \
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

        支持完整替换 teams 配置
        """
        hierarchy = self.get_by_id(hierarchy_id)
        if not hierarchy:
            return None

        teams_data = data.pop('teams', None)

        # 提取 Global Supervisor LLM 配置
        data = self._extract_hierarchy_llm_config(data)

        # 更新主记录字段
        for key, value in data.items():
            if hasattr(hierarchy, key) and key not in ('id', 'created_at', 'teams'):
                setattr(hierarchy, key, value)

        # 如果提供了 teams 数据，完整替换
        if teams_data is not None:
            # 删除旧的 teams
            for team in hierarchy.teams:
                self.session.delete(team)
            self.session.flush()

            # 创建新的 teams
            for i, team_data in enumerate(teams_data):
                workers_data = team_data.pop('workers', [])
                team_data['hierarchy_id'] = hierarchy.id
                team_data['order_index'] = i

                # 提取 Team Supervisor LLM 配置
                team_data = self._extract_team_llm_config(team_data)

                team = Team(**team_data)
                self.session.add(team)
                self.session.flush()

                for j, worker_data in enumerate(workers_data):
                    worker_data['team_id'] = team.id
                    worker_data['order_index'] = j

                    # 提取 Worker LLM 配置
                    worker_data = self._extract_worker_llm_config(worker_data)

                    worker = Worker(**worker_data)
                    self.session.add(worker)

        # 更新版本号
        hierarchy.version += 1

        self.session.commit()
        self.session.refresh(hierarchy)
        return hierarchy

    def delete(self, hierarchy_id: str) -> bool:
        """删除层级团队（级联删除 Teams 和 Workers）"""
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
