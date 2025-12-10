#!/bin/bash

# 部署脚本 - 自动化部署层级多智能体系统 API

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 打印横幅
print_banner() {
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  层级多智能体系统 API 部署脚本"
    echo "═══════════════════════════════════════════════════════"
    echo ""
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装"
        return 1
    fi
    return 0
}

# 检查先决条件
check_prerequisites() {
    print_info "检查先决条件..."
    
    local all_good=true
    
    # 检查 AWS CLI
    if check_command aws; then
        print_success "AWS CLI 已安装"
    else
        print_error "请安装 AWS CLI: https://aws.amazon.com/cli/"
        all_good=false
    fi
    
    # 检查 SAM CLI
    if check_command sam; then
        print_success "SAM CLI 已安装"
    else
        print_error "请安装 SAM CLI: pip install aws-sam-cli"
        all_good=false
    fi
    
    # 检查 Python
    if check_command python3; then
        print_success "Python3 已安装"
    else
        print_error "请安装 Python 3"
        all_good=false
    fi
    
    # 检查 AWS 凭证
    if aws sts get-caller-identity &> /dev/null; then
        print_success "AWS 凭证已配置"
    else
        print_error "请配置 AWS 凭证: aws configure"
        all_good=false
    fi
    
    if [ "$all_good" = false ]; then
        exit 1
    fi
    
    echo ""
}

# 构建应用
build_app() {
    print_info "构建应用..."
    
    if sam build; then
        print_success "构建成功"
    else
        print_error "构建失败"
        exit 1
    fi
    
    echo ""
}

# 部署应用
deploy_app() {
    print_info "部署应用..."
    
    # 检查是否是首次部署
    if [ ! -f "samconfig.toml" ]; then
        print_warning "首次部署，将使用引导部署模式"
        print_info "请按照提示输入配置参数..."
        
        sam deploy --guided
    else
        print_info "使用现有配置部署..."
        
        sam deploy
    fi
    
    if [ $? -eq 0 ]; then
        print_success "部署成功"
    else
        print_error "部署失败"
        exit 1
    fi
    
    echo ""
}

# 获取 API 端点
get_endpoints() {
    print_info "获取 API 端点..."
    
    # 从 CloudFormation 输出中提取端点
    STACK_NAME=$(grep stack_name samconfig.toml | cut -d '"' -f 2 || echo "hierarchical-agents-api")
    
    ENDPOINTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "═══════════════════════════════════════════════════════"
        echo "  API 端点"
        echo "═══════════════════════════════════════════════════════"
        echo "$ENDPOINTS"
    else
        print_warning "无法获取端点信息"
    fi
    
    echo ""
}

# 测试健康检查
test_health_check() {
    print_info "测试健康检查端点..."
    
    STACK_NAME=$(grep stack_name samconfig.toml | cut -d '"' -f 2 || echo "hierarchical-agents-api")
    
    HEALTH_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`HealthCheckEndpoint`].OutputValue' \
        --output text 2>/dev/null)
    
    if [ -n "$HEALTH_ENDPOINT" ]; then
        RESPONSE=$(curl -s -w "\n%{http_code}" "$HEALTH_ENDPOINT")
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | head -n-1)
        
        if [ "$HTTP_CODE" = "200" ]; then
            print_success "健康检查通过"
            echo "响应: $BODY"
        else
            print_warning "健康检查失败 (HTTP $HTTP_CODE)"
            echo "响应: $BODY"
        fi
    else
        print_warning "无法获取健康检查端点"
    fi
    
    echo ""
}

# 显示下一步操作
show_next_steps() {
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  下一步操作"
    echo "═══════════════════════════════════════════════════════"
    echo ""
    echo "1. 测试 API:"
    echo "   curl -X POST <ExecuteEndpoint> \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -d @examples/simple_request.json"
    echo ""
    echo "2. 查看日志:"
    echo "   sam logs -n HierarchicalAgentsFunction --tail"
    echo ""
    echo "3. 本地测试:"
    echo "   export AWS_BEDROCK_API_KEY='your-api-key'"
    echo "   python test_api.py"
    echo ""
    echo "4. 更新部署:"
    echo "   ./deploy.sh"
    echo ""
    echo "5. 删除堆栈:"
    echo "   sam delete"
    echo ""
}

# 主函数
main() {
    print_banner
    
    # 检查参数
    if [ "$1" = "--skip-checks" ]; then
        print_warning "跳过先决条件检查"
    else
        check_prerequisites
    fi
    
    build_app
    deploy_app
    get_endpoints
    test_health_check
    show_next_steps
    
    print_success "部署完成！"
}

# 运行主函数
main "$@"
