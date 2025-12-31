"""
API Routes - API 路由蓝图
"""

# models_bp removed - AIModel table was simplified away
from .hierarchies import hierarchies_bp
from .runs import runs_bp
from .health import health_bp

__all__ = ['hierarchies_bp', 'runs_bp', 'health_bp']
