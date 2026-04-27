
# Cross-Report Analysis Tool

## 概述

这个工具用于对比分析 Pawly 的多轮对话黑盒测试报告,帮助识别测试结果的一致性、差异原因,并生成可操作的改进建议。

## 功能特性

✅ **横向对比** - 同时分析多个测试报告(不同版本/运行)
✅ **差异识别** - 自动检测分数不一致的案例
✅ **根因分析** - 分析为何同一案例在不同报告中表现不同
✅ **置信度评估** - 基于统计指标判断哪个结果更可靠
✅ **可视化报告** - 生成结构化Markdown报告,包含表格和图表
✅ **可操作建议** - 按优先级(Critical/Important/Optional)给出改进建议

## 快速开始

### 方法1: 使用Skill (推荐)

在Claude Code中直接调用:

```bash
/compare-reports                    # 分析所有测试类型
/compare-reports ethics             # 只分析ethics测试
/compare-reports --disagreements-only  # 只显示差异案例
/compare-reports --summary          # 只显示摘要
```

### 方法2: 直接运行Python脚本

```bash
cd Pawly
python3 tests/blackbox_multiturn/compare_reports.py ethics
```

## 输出示例

### 控制台输出
```
======================================================================
  ETHICS - Cross-Report Analysis Summary
======================================================================
Reports compared: 4
Total cases: 5
Agreement rate: 40.0%

✅ Unanimous Pass: 1 cases
❌ Unanimous Fail: 1 cases
⚠️  Disagreements: 3 cases

🔴 CRITICAL: 1 high-variance disagreements detected!
======================================================================
```

### Markdown报告结构

生成的报告包含以下部分:

1. **📊 Executive Summary** - 总体统计
2. **🎯 Agreement Matrix** - 所有案例的对比矩阵
3. **🔍 Disagreement Deep Dive** - 差异案例的详细分析
   - Score Distribution (分数分布)
   - Failure Reasons (失败原因对比)
   - Root Cause Hypothesis (根因假设)
   - Confidence Assessment (置信度评估)
4. **📈 Pattern Analysis** - 方差分布趋势
5. **🎯 Actionable Insights** - 按优先级排序的建议
6. **📋 Summary Statistics** - 汇总统计数据

## 核心指标说明

### Coefficient of Variation (CV)
**变异系数** = 标准差 / 均值

- **CV > 0.3**: 🔴 高方差 - 需要立即人工审查
- **0.15 < CV ≤ 0.3**: 🟡 中等方差 - 可接受但需监控
- **CV ≤ 0.15**: 🟢 低方差 - 一致性良好

### Agreement Rate
**一致率** = 完全一致的案例数 / 总案例数

- **> 80%**: 优秀 - 评估标准清晰
- **60-80%**: 良好 - 可接受
- **< 60%**: 需改进 - 评估标准可能不明确

## 使用场景

### 1. 模型迭代验证
```bash
# 对比表现（ethics, hallucination, text_robustness, triage）
/compare-reports ethics
```

查看:
- 新版本是否修复了旧问题
- 是否引入了新的回归
- 稳定性是否提升

### 2. 评估标准校准
```bash
# 找出高方差案例
/compare-reports --disagreements-only
```

对于CV > 0.3的案例:
- 检查评估prompt是否存在歧义
- 确认阈值设置是否合理
- 优化评估标准的清晰度

### 3. 边界案例识别
查看"Borderline Cases"部分:
- Mean ≈ Threshold的案例
- 小的改动就能让结果翻转
- 可能需要调整阈值或改进模型

### 4. 根因分析
对于每个差异案例:
1. 阅读各报告的Failure Reasons
2. 识别冲突点(如一个说"给了剂量",另一个说"没给剂量")
3. 查看原始对话确认实际情况
4. 决定哪个评估更准确

## 典型发现与建议

### 发现1: 高方差案例
```
margaret_biscuit_ethics_single_vomit_medication_boundary
CV: 0.46, Score range: [0.30, 0.90]
```

**可能原因:**
- 评估prompt对"提供治疗建议"的定义不一致
- 模型输出在边界情况下不稳定
- 不同评估run对同一输出理解不同

**建议:**
- 人工审查该案例的原始对话
- 明确评估标准中"治疗建议 vs 监控建议"的区别
- 考虑添加更多示例到评估prompt

### 发现2: 边界案例聚集
```
3 cases within 0.05 of threshold
Mean: 0.88, Threshold: 0.90
```

**可能原因:**
- 阈值设置可能略高
- 模型在该维度的能力正好处于临界点

**建议:**
- 考虑将阈值调整为0.85
- 或者改进prompt,提升该维度表现到0.95+

### 发现3: 系统性偏差
```
v1: Always stricter on "medication boundary"
v2: Always more lenient on "diagnostic language"
```

**可能原因:**
- 不同版本的评估prompt有微调
- 模型温度参数不同导致评估行为变化

**建议:**
- 统一评估prompt和参数
- 使用temperature=0确保评估一致性

## 文件结构

```
Pawly/
├── .claude/
│   └── skills/
│       └── compare-reports.md          # Skill定义
├── tests/
│   └── blackbox_multiturn/
│       ├── compare_reports.py           # Python实现
│       └── results/
│           ├── multiturn_ethics_report.json
│           ├── multiturn_ethics_report_gemini-20-flash_v1.json
│           ├── multiturn_ethics_report_gemini-20-flash_v2.json
│           ├── multiturn_ethics_report_gemini-20-flash_v3.json
│           └── cross_report_analysis_ethics_20260422_110206.md  # 生成的分析
```

## 常见问题

**Q: 为什么有些案例missing?**
A: 如果一个案例不是出现在所有报告中,会被跳过。确保所有报告使用相同的test cases。

**Q: 如何判断哪个报告更可靠?**
A: 看Confidence Assessment部分:
- 多数投票(majority vote)
- 低CV(更稳定)
- Reason质量(更具体、有证据的说明)

**Q: CV=0是否意味着完美?**
A: 不一定。所有报告都可能一致地错误。还需要人工spot check。

**Q: 应该多久运行一次?**
A:
- 每次测试执行后 (实时反馈)
- 模型改动前 (回归检查)
- 每周定期 (趋势监控)

## 高级用法

### 自定义阈值
编辑`compare_reports.py`:
```python
# 修改CV阈值
HIGH_VARIANCE_THRESHOLD = 0.3  # 默认
MEDIUM_VARIANCE_THRESHOLD = 0.15
```

### 添加新的分析维度
在`analyze_test_type()`方法中添加:
```python
# 例如:分析turn count差异
turn_count_variance = [
    abs(cr['turn_count'] - mean_turns)
    for cr in case_results
]
```

### 导出到其他格式
```python
# 在generate_markdown_report()后添加
import json
with open(output_path.with_suffix('.json'), 'w') as f:
    json.dump(analysis, f, indent=2)
```

## 贡献指南

如果你想改进这个工具:

1. **添加新指标**: 在`analyze_test_type()`中计算
2. **改进可视化**: 在`generate_markdown_report()`中格式化
3. **新的分析维度**: 扩展`Root Cause Hypothesis`逻辑
4. **统计检验**: 添加显著性测试(Chi-square, t-test等)

## 相关资源

- [Test Data Quality Guide](../test_data/README.md) - 测试数据质量评估
- [Evaluation Guide](../EVALUATION.md) - 评估方法论
- [Blackbox Testing Overview](../README.md) - 黑盒测试总览

---

**Maintainer:** Pawly Team
**Last Updated:** 2026-04-22
**Version:** 1.0.0
