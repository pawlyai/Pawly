# Multi-Turn Blackbox Tests

这个目录放多轮对话黑盒测试。

## 安装

先安装项目测试依赖：

```bash
pip install -e ".[dev]"
```

跑评测测试还需要设置：

```bash
export GOOGLE_API_KEY="your-api-key"
```

如果要跑 `ui_app.py`，还需要额外安装 `streamlit`：

```bash
pip install streamlit
```

## 运行主测试：

```bash
python -m pytest tests/blackbox_multiturn/test_message_handler_multiturn.py --multiturn-topic=multiturn_triage  
```

### 说明

- 测试数据在 `tests/blackbox_multiturn/test_data/`
- 结果会写到 `tests/blackbox_multiturn/results/`
- 运行过程日志会写到 `tests/blackbox_multiturn/logs/`，即使测试中途失败也会保留已完成的 case 和 turn 记录
- ```
  --multiturn-topic=multiturn_hallucination # multiturn_ethics, multiturn_triage_simple, multiturn_triage_middle, multiturn_triage_hard, multiturn_text_robustness
  ```


## 运行 UI

```bash
streamlit run tests/blackbox_multiturn/ui_app.py
```
