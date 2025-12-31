#!/usr/bin/env python3
"""
流式事件测试脚本

测试 SSE 流式事件格式:
{
    "run_id": "...",
    "timestamp": "...",
    "sequence": 123,
    "source": { agent_id, agent_type, agent_name, team_name },
    "event": { category, action },
    "data": { ... }
}

使用方法:
    python test_stream.py [--hierarchy ID] [--task "任务描述"]
"""

import json
import requests
import sseclient
import argparse

# API 基础 URL
BASE_URL = "http://localhost:8082"


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_event(event_num: int, event_data: dict):
    """打印格式化的事件"""
    source = event_data.get('source')
    event = event_data.get('event', {})
    data = event_data.get('data', {})

    category = event.get('category', 'unknown')
    action = event.get('action', 'unknown')

    # 根据 category 选择颜色
    color = Colors.RESET
    if category == 'lifecycle':
        color = Colors.GREEN
    elif category == 'llm':
        color = Colors.CYAN
    elif category == 'dispatch':
        color = Colors.YELLOW
    elif category == 'system':
        color = Colors.RED

    print(f"\n{Colors.BOLD}[EVENT #{event_num}]{Colors.RESET}")
    print(f"  {color}event: {category}.{action}{Colors.RESET}")

    if source:
        agent_type = source.get('agent_type', 'unknown')
        agent_name = source.get('agent_name', 'unknown')
        team_name = source.get('team_name')

        source_str = f"{agent_type}: {agent_name}"
        if team_name:
            source_str += f" @ {team_name}"
        print(f"  source: {source_str}")

    # 打印关键数据
    if 'content' in data:
        content = data['content'][:100]
        print(f"  content: {content}...")
    elif 'task' in data:
        print(f"  task: {data['task']}")
    elif 'name' in data:
        print(f"  name: {data['name']}")
    elif 'error' in data:
        print(f"  {Colors.RED}error: {data['error']}{Colors.RESET}")


def create_hierarchy():
    """创建测试用的层级团队"""
    payload = {
        "name": "测试团队",
        "description": "流式事件格式测试",
        "global_supervisor_agent": {
            "agent_id": "gs-001",
            "system_prompt": "你是首席科学家，负责协调研究团队。根据任务需求调用合适的团队。"
        },
        "teams": [
            {
                "name": "研究组",
                "team_supervisor_agent": {
                    "agent_id": "ts-research-001",
                    "system_prompt": "你是研究组主管，负责协调研究员完成任务。"
                },
                "workers": [
                    {
                        "agent_id": "worker-alice-001",
                        "name": "Alice",
                        "role": "研究员",
                        "system_prompt": "你是 Alice，一名研究员，擅长解释复杂概念。"
                    }
                ]
            }
        ]
    }

    resp = requests.post(f"{BASE_URL}/api/executor/v1/hierarchies/create", json=payload)
    if resp.status_code == 200:
        result = resp.json()
        if result.get('success'):
            return result['data']['id']
    return None


def get_or_create_hierarchy():
    """获取或创建测试层级"""
    # 先尝试获取已存在的
    resp = requests.post(f"{BASE_URL}/api/executor/v1/hierarchies/list", json={"page": 1, "size": 10})
    if resp.status_code == 200:
        result = resp.json()
        items = result.get('data', {}).get('items', [])
        for item in items:
            if item.get('name') == '测试团队':
                return item['id']

    # 不存在则创建
    return create_hierarchy()


def test_stream(hierarchy_id: str, task: str):
    """测试流式事件"""
    print(f"\n{'='*60}")
    print(f"  流式事件测试")
    print(f"{'='*60}")

    # 启动运行
    start_payload = {
        "hierarchy_id": hierarchy_id,
        "task": task
    }

    print(f"\n启动任务: {task}")
    print(f"Hierarchy ID: {hierarchy_id}")

    resp = requests.post(f"{BASE_URL}/api/executor/v1/runs/start", json=start_payload)
    if resp.status_code != 200:
        print(f"启动失败: {resp.text}")
        return

    result = resp.json()
    if not result.get('success'):
        print(f"启动失败: {result}")
        return

    run_id = result['data']['id']
    print(f"Run ID: {run_id}")

    # 监听事件流
    print(f"\n{'='*60}")
    print(f"  开始监听事件流")
    print(f"{'='*60}")

    stream_url = f"{BASE_URL}/api/executor/v1/runs/stream"
    stream_resp = requests.post(stream_url, json={"id": run_id}, stream=True)

    client = sseclient.SSEClient(stream_resp)
    event_count = 0

    for event in client.events():
        if event.event == 'close':
            print(f"\n{Colors.GREEN}[STREAM CLOSED]{Colors.RESET}")
            break

        try:
            event_data = json.loads(event.data)
            event_count += 1
            print_event(event_count, event_data)
        except json.JSONDecodeError:
            print(f"[RAW] {event.data}")

    print(f"\n{'='*60}")
    print(f"  测试完成，共收到 {event_count} 个事件")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='流式事件测试')
    parser.add_argument('--hierarchy', type=str, help='Hierarchy ID')
    parser.add_argument('--task', type=str, default='请用一句话解释人工智能', help='任务描述')
    args = parser.parse_args()

    # 获取或创建层级
    if args.hierarchy:
        hierarchy_id = args.hierarchy
    else:
        print("正在获取或创建测试层级...")
        hierarchy_id = get_or_create_hierarchy()
        if not hierarchy_id:
            print("无法创建测试层级")
            return

    print(f"使用层级: {hierarchy_id}")

    # 测试流式事件
    test_stream(hierarchy_id, args.task)


if __name__ == '__main__':
    main()
