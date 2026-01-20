---
tags:
  - 工具/AI
  - exploration
---
# Phase X: 高级内容处理 - 探索性文档

> **状态**：探索中 / 暂缓实现  
> **结论**：对于 p2r CLI 的 MVP，直接使用 MinerU 原始输出即可。本文档记录技术探索过程，供未来独立产品开发参考。

---

## 1. 问题背景

### 1.1 MinerU 输出的局限性

MinerU 是优秀的 PDF 解析工具，但其默认输出（`full.md` / `full.html`）存在以下局限：

| 问题 | 描述 | 影响 |
|------|------|------|
| 脚注丢失 | `page_footnote` 类型内容不出现在最终输出中 | 丢失作者贡献、通讯作者、代码链接等信息 |
| 识别不一致 | 较长注释有时识别为文本（保留），有时识别为脚注（丢弃） | 同类内容处理方式不一致 |
| 标题层级扁平 | 所有标题都标记为 `text_level: 1` | 无法区分 h1/h2/h3 |
| 跨页段落 | 可能存在段落被截断的情况 | 阅读体验受影响 |

### 1.2 核心数据：content_list.json

MinerU 输出的 `*_content_list.json` 包含完整的结构化信息：

```json
{
  "type": "page_footnote",
  "text": "*Project leader.",
  "bbox": [189, 881, 285, 893],
  "page_idx": 0
}
```

元素类型包括：
- `text`（含 `text_level` 标题层级）
- `image`（含 `image_caption`）
- `table`（含 `table_body` HTML）
- `list`（含 `list_items`）
- `page_footnote`（被丢弃的脚注）
- `page_number`（页码）
- `aside_text`（边注）

---

## 2. 已探索的技术方案

### 2.1 方案 A：编辑现有 full.md

**思路**：从 JSON 提取脚注，注入到现有 `full.md` 文件

**实现方式**：
- 在文件末尾追加脚注区块
- 或尝试"贴回正文"（匹配脚注标号）

**优点**：
- 保留 MinerU 的格式处理逻辑
- 实现相对简单

**缺点**：
- 无法精确定位脚注在页内的位置
- "贴回正文"的锚点匹配容易出错（如多个 `*` 符号）
- 幂等性处理复杂

### 2.2 方案 B：从 JSON 完全重建

**思路**：放弃 MinerU 的 `full.md`，完全基于 `content_list.json` 重建文档

**实现方式**：
```python
def rebuild_markdown(content_list):
    for item in content_list:
        if item['type'] == 'text':
            yield format_text(item)
        elif item['type'] == 'page_footnote':
            yield format_footnote(item)  # 脚注自然出现在正确位置
        # ...
```

**优点**：
- 脚注位置精确（按 JSON 顺序自然出现在每页末尾）
- 完全可控的输出格式
- 可以添加页面分隔标记

**缺点**：
- 需要重新实现所有格式转换逻辑
- 可能丢失 MinerU 的一些智能处理（如段落合并）
- LaTeX 公式处理需要额外工作
- 标题层级信息本身就是扁平的（JSON 中也没有）

**实验结果**：已实现原型（见 `output_rebuilt/rebuild_from_json.py`），效果可接受但不完美。

### 2.3 方案 C：JSON 可视化阅读器

**思路**：开发专门的工具直接渲染 JSON

**可能形式**：
- Web 单页应用
- Obsidian 插件
- 独立桌面应用

**优点**：
- 交互性强（折叠、跳转、搜索）
- 保留完整元数据
- 一次开发，所有文档通用

**缺点**：
- 开发成本高
- 脱离 Obsidian 笔记流程
- 维护负担

---

## 3. 潜在问题分析

基于实际测试（MinerU 论文 PDF），发现以下潜在问题：

### 3.1 从 JSON 重建的问题

| 问题 | 严重程度 | 是否可解决 |
|------|----------|-----------|
| 标题层级丢失 | 中 | 可通过正则推断（`/^\d+\.\d+/` → h2） |
| LaTeX 公式显示 | 中 | HTML 需要 MathJax；Markdown 依赖渲染器 |
| 跨页段落断裂 | 低 | 需要启发式合并逻辑 |
| 图片标题缺失 | 低 | 无法解决（源数据问题） |

### 3.2 编辑现有文件的问题

| 问题 | 严重程度 | 是否可解决 |
|------|----------|-----------|
| 脚注位置不精确 | 中 | 只能追加到文末或尝试启发式匹配 |
| 符号脚注匹配困难 | 高 | `*` 可能出现多次，无法准确对应 |
| 幂等性实现复杂 | 中 | 需要标记注释，可能被用户误删 |

---

## 4. 未来产品方向（独立于 p2r CLI）

### 4.1 Diff + AI 后处理

**核心思路**：
1. 对比 `content_list.json` 与 `full.md` 的内容
2. 生成结构化的差异（哪些内容被丢弃、哪些被修改）
3. 将差异交给 AI 进行智能后处理

**AI 可以做的事情**：
- 将丢失的脚注插入到正确位置
- 修正段落划分（合并被截断的句子）
- 推断并修正标题层级
- 优化格式（如将 URL 转为 Markdown 链接）
- 识别并处理特殊内容（如代码块、引用）

**技术实现草案**：
```python
def generate_diff(json_content, markdown_content):
    """生成 JSON 与 Markdown 的内容差异"""
    json_texts = extract_all_text(json_content)
    md_texts = extract_all_text(markdown_content)
    
    missing = json_texts - md_texts  # 被丢弃的内容
    return {
        'missing_footnotes': [...],
        'missing_asides': [...],
        'potential_truncations': [...],
    }

def ai_postprocess(markdown_content, diff, llm_client):
    """AI 智能后处理"""
    prompt = f"""
    以下是一篇学术论文的 Markdown 内容，以及一些被 PDF 解析工具丢弃的信息。
    请将这些信息合理地整合到文档中：
    
    [Markdown 内容]
    {markdown_content}
    
    [被丢弃的脚注]
    {diff['missing_footnotes']}
    
    要求：
    1. 将脚注插入到最相关的位置（通常是对应页面的末尾或引用处）
    2. 保持文档格式一致
    3. 不要修改原有内容的含义
    """
    return llm_client.process(prompt)
```

**优点**：
- 利用 AI 的语义理解能力解决启发式规则难以处理的问题
- 灵活性高，可以处理各种边缘情况

**缺点**：
- 引入 AI 调用成本和延迟
- 结果不确定性（需要人工审核）
- 隐私考虑（文档内容发送到 AI 服务）

### 4.2 交互式编辑器

**设想**：提供 TUI 或 Web 界面，让用户：
- 预览 JSON 结构与最终输出的对比
- 手动拖拽调整脚注位置
- 选择性保留/丢弃某些元素
- 实时预览 Markdown/HTML 效果

### 4.3 独立的文档优化工具

作为 p2r 的下游工具，专门处理学术文档的格式优化：
- 输入：MinerU 的原始输出目录
- 输出：优化后的 Markdown/HTML
- 可以独立运行，也可以集成到 p2r 流程中

---

## 5. 当前决策

### 对于 p2r CLI MVP

**决策**：直接使用 MinerU 的原始输出（`full.md` + `full.html`）

**理由**：
1. 原始输出质量已经足够好，能满足基本阅读需求
2. 脚注丢失虽然遗憾，但不影响核心使用场景
3. 避免引入复杂的后处理逻辑，保持工具简洁
4. 用户可以在 Obsidian 中手动补充重要信息

### 对于高级内容处理

**决策**：作为独立产品方向探索，不阻塞 p2r 主线开发

**下一步**：
- 收集更多实际使用中的问题反馈
- 评估 Diff + AI 方案的可行性和成本
- 考虑是否值得开发独立工具

---

## 6. 实验记录

### 6.1 从 JSON 重建实验

**日期**：2026-01-20

**实验内容**：基于 MinerU 论文的 `content_list.json` 重建 Markdown 和 HTML

**实验脚本**：`output_rebuilt/rebuild_from_json.py`

**结果**：
- 成功保留了 10 个脚注（原版 `full.md` 中全部丢失）
- 脚注自然出现在每页末尾
- 标题层级问题依然存在（源数据限制）
- HTML 输出效果良好，添加了脚注样式

**输出文件**：
- `output_rebuilt/rebuilt.md`
- `output_rebuilt/rebuilt.html`
- `output_rebuilt/rebuilt_no_footnotes.md`（对照组）

### 6.2 脚注内容分析

测试文档（MinerU 论文）中的脚注：

| 页码 | 内容 | 类型 |
|------|------|------|
| 1 | `*Project leader.` | 作者角色 |
| 1 | `† Corresponding author: heconghui@pjlab.org.cn` | 通讯作者 |
| 2 | `³https://github.com/opendatalab/PDF-Extract-Kit` | 代码链接 |
| 3 | `4https://github.com/pymupdf/PyMuPDF` | 工具链接 |
| 3 | `5Current version: v0.8.1` | 版本说明 |
| ... | ... | ... |

**观察**：所有脚注都是有价值的信息，MinerU 的 `page_footnote` 识别准确。

---

## 7. 参考资料

- MinerU API 文档：`doc/mineru_api_reference.md`
- Phase 1 完成总结：`doc/phase1_complete.md`
- 重建脚本：`output_rebuilt/rebuild_from_json.py`
