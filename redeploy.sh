#!/bin/bash
#
# 重新部署脚本
# 用法: ./redeploy.sh [--no-cache]
#
# 选项:
#   --no-cache    构建时不使用缓存
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
COMPOSE_FILE="docker-compose.yml"
API_CONTAINER="hierarchical-agents-api"
HEALTH_URL="http://localhost:18080/health"
HEALTH_TIMEOUT=60
HEALTH_INTERVAL=2

# 解析参数
NO_CACHE=""
for arg in "$@"; do
    case $arg in
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}       重新部署 AIOps Executor         ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 停止服务
echo -e "${YELLOW}[1/5] 停止服务...${NC}"
if docker-compose -f $COMPOSE_FILE ps -q 2>/dev/null | grep -q .; then
    docker-compose -f $COMPOSE_FILE down
    echo -e "${GREEN}      服务已停止${NC}"
else
    echo -e "${GREEN}      服务未运行，跳过${NC}"
fi
echo ""

# 2. 删除旧镜像
echo -e "${YELLOW}[2/5] 删除旧镜像...${NC}"
IMAGE_NAME=$(docker-compose -f $COMPOSE_FILE config | grep "image:" | head -1 | awk '{print $2}')
if [ -z "$IMAGE_NAME" ]; then
    # 如果没有指定 image，使用默认的项目名_服务名格式
    PROJECT_NAME=$(basename "$(pwd)")
    IMAGE_NAME="${PROJECT_NAME}-api"
fi

if docker images -q "$IMAGE_NAME" 2>/dev/null | grep -q .; then
    docker rmi -f "$IMAGE_NAME" 2>/dev/null || true
    echo -e "${GREEN}      镜像 $IMAGE_NAME 已删除${NC}"
else
    echo -e "${GREEN}      镜像不存在，跳过${NC}"
fi

# 清理悬空镜像
DANGLING=$(docker images -f "dangling=true" -q 2>/dev/null)
if [ -n "$DANGLING" ]; then
    echo -e "      清理悬空镜像..."
    docker rmi $DANGLING 2>/dev/null || true
fi
echo ""

# 3. 重新构建镜像
echo -e "${YELLOW}[3/5] 重新构建镜像...${NC}"
if [ -n "$NO_CACHE" ]; then
    echo -e "      使用 --no-cache 模式"
fi
docker-compose -f $COMPOSE_FILE build $NO_CACHE
echo -e "${GREEN}      镜像构建完成${NC}"
echo ""

# 4. 启动服务
echo -e "${YELLOW}[4/5] 启动服务...${NC}"
docker-compose -f $COMPOSE_FILE up -d
echo -e "${GREEN}      服务已启动${NC}"
echo ""

# 5. 健康检查
echo -e "${YELLOW}[5/5] 健康检查...${NC}"
echo -e "      等待服务就绪 (最多 ${HEALTH_TIMEOUT}s)..."

elapsed=0
while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
    # 检查容器状态
    if ! docker ps -q -f "name=$API_CONTAINER" | grep -q .; then
        echo -e "${RED}      容器未运行，检查日志：${NC}"
        docker-compose -f $COMPOSE_FILE logs --tail=20 api
        exit 1
    fi

    # 检查健康接口
    response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        echo -e "${GREEN}      健康检查通过!${NC}"
        echo ""

        # 显示健康检查响应
        echo -e "${BLUE}健康检查响应:${NC}"
        curl -s $HEALTH_URL | python3 -m json.tool 2>/dev/null || curl -s $HEALTH_URL
        echo ""

        # 显示容器状态
        echo -e "${BLUE}容器状态:${NC}"
        docker-compose -f $COMPOSE_FILE ps
        echo ""

        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}       部署成功!                        ${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "API 地址: http://localhost:18080"
        echo -e "健康检查: $HEALTH_URL"
        exit 0
    fi

    sleep $HEALTH_INTERVAL
    elapsed=$((elapsed + HEALTH_INTERVAL))
    echo -e "      等待中... (${elapsed}s)"
done

# 健康检查超时
echo -e "${RED}      健康检查超时!${NC}"
echo ""
echo -e "${RED}容器日志:${NC}"
docker-compose -f $COMPOSE_FILE logs --tail=50 api
exit 1
