# 依赖安装说明

## 集成测试前置条件

集成测试需要以下Python包：

```bash
# 方式1: 使用虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate
pip install langgraph langchain-core jinja2

# 方式2: 系统级安装（需要终端sudo）
sudo apt install python3-langgraph python3-langchain-core python3-jinja2
```

## 运行集成测试

```bash
# 激活虚拟环境（如果使用方式1）
source venv/bin/activate

# 运行测试
python3 tests/test_integration.py
```

## 当前状态

- ✅ 集成测试脚本已创建（tests/test_integration.py）
- ❌ 依赖未安装（需要langgraph、langchain-core）
- ⏳ 等待依赖安装后验证

## 依赖列表

| 包名 | 用途 | 状态 |
|------|------|------|
| langgraph | workflow编排 | ❌ 未安装 |
| langchain-core | LangGraph依赖 | ❌ 未安装 |
| jinja2 | 模板渲染 | ✅ 已安装 |
| asyncio | 异步执行 | ✅ 内置 |
