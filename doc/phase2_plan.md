---
tags:
  - 工具/AI
  - phase2
---
# Phase 2 开发计划：脚注提取与注入（Markdown + HTML）

## 0. 背景与目标

现状：MinerU 的默认输出（`full.md`/`full.html`）通常会**丢弃页眉、页脚、页码**等“非正文”内容。对论文来说，**脚注（footnote）**有时包含作者贡献、通讯作者、代码链接、伦理声明、额外解释等关键信息，因此需要在 `p2r` 的交付物中可见。

Phase 2 目标（本计划）：
- 从 MinerU 的结构化结果中**提取脚注**（优先使用 `content_list.json` 的 `page_footnote`）
- 将脚注**注入**到最终交付的 `full.md` 与 `full.html` 中（不破坏图片引用，不重排正文）
- 让该处理**可控、可重复执行（幂等）**，便于后续 Phase（重命名、移动库、PicGo、Frontmatter）叠加

非目标（本 Phase 不做）：
- 不做“脚注编号与正文引用（[^1]）”的精准对齐与双向链接（可作为后续增强）
- 不重建 MinerU 的 Markdown（避免破坏正文排版/图表/公式）
- 不做跨页脚注合并的强语义推断（仅做轻量去重与排序）

---

## 1. MinerU 输出与数据来源

根据 MinerU 文档与现有实测输出：
- `output/raw/*_content_list.json`：列表结构，每个元素包含 `type/text/bbox/page_idx` 等字段
- `type` 可能包含：`text`、`image`、`table`、`list`，以及在 discarded blocks 中输出的：`header`、`footer`、`page_number`、`aside_text`、`page_footnote`
- 实测：`page_footnote` 结构示例：
  - `{"type": "page_footnote", "text": "*Project leader.", "bbox": [x1,y1,x2,y2], "page_idx": 0}`

结论：Phase 2 优先使用 `page_footnote`，这是最“贴近 MinerU 识别”的脚注来源。

---

## 2. 实现方式对比（方案评估）

### 方案 A：仅使用 `content_list.json` 的 `page_footnote`（推荐）

做法：
- 读取 `*_content_list.json` → 过滤 `type == "page_footnote"` → 按 `page_idx` 分组、按 `bbox`（y 坐标）排序 → 注入到 `full.md`/`full.html`

优点：
- 无需额外解析 PDF/OCR，**实现成本低**、速度快
- 利用 MinerU 的版面理解结果，通常比纯规则更稳
- 与 `p2r` 现有“下载 ZIP → 后处理”的架构天然兼容

缺点/风险：
- 依赖 MinerU 是否能正确识别为 `page_footnote`
- 部分脚注可能被识别为 `aside_text` 或 `footer`（需要可选补充策略）

适用结论：作为 MVP/默认实现最合适。

---

### 方案 B：从 PDF 直接提取脚注（pdfplumber/布局规则/OCR）

做法：
- 读取 `*_origin.pdf`（或用户原 PDF）→ 逐页检测底部区域文本块 → 规则判定脚注 → 追加到产物

优点：
- 不依赖 MinerU 是否输出 `page_footnote`
- 允许“更完整地恢复被 MinerU 丢弃的文本”

缺点/风险：
- 版式多样（双栏、脚注跨栏/跨页、扫描件），规则非常脆弱
- 扫描件需要 OCR，复杂度/依赖/成本显著上升
- 极易引入重复内容（页脚/页码/版权信息混入）

适用结论：不适合做默认；可作为“当 MinerU 缺失时”的可选 fallback（后续 Phase 再考虑）。

---

### 方案 C：混合方案（A 为主，B 为补）

做法：
- 优先 `page_footnote`
- 若某页缺失脚注但疑似存在（例如出现 `*`、`†` 标记、或 bbox 靠底部的 `aside_text/footer`），再触发 PDF 规则提取

优点：
- 覆盖率更高

缺点：
- 实现复杂、测试成本高；容易“补错”导致噪声增加

适用结论：作为 Phase 2.1 或 Phase 3 之后的增强更合理。

---

### 本阶段结论

Phase 2 采用：**方案 A（仅用 `page_footnote`）为默认**。并预留参数与内部接口，为后续“将 `aside_text/footer` 纳入候选”或“PDF fallback”扩展。

---

## 3. 交付物形态（注入策略与放置位置）

本阶段重点回答两个问题：
1) 脚注是否需要“筛选/挑选”？
2) 脚注应该插回到正文哪里？

为降低风险，采用“**先尝试贴回正文，失败则回退到文末汇总**”的双策略，并通过显式标记保证幂等。

---

### 3.1 脚注筛选：规则 vs 交互 vs LLM（策略是否足够有力？）

脚注数量通常较少（常见 0~20 条），因此“让用户逐条确认”是可行的；但也可能出现大量噪声（例如版权声明被识别为脚注），需要一定自动化。

建议提供三档策略（由简到强）：

**(S1) 规则过滤（默认）**
- 去空/去重（同页相同文本只保留一次）
- 归一化空白字符
- 黑名单片段（例如明显的版权/出版信息、统一页脚模板等；以配置可扩展）
- 长度阈值：过短（如 1~2 个字符）或过长（如 > N 字）可提示用户确认

结论：对“明显噪声”有效，但对“语义上是否重要”不够有力。

**(S2) 交互式确认（推荐作为可选开关）**
- CLI 逐条展示脚注（含页码、文本预览），用户选择保留/丢弃
- 支持批量操作（全保留/全丢弃/仅保留含链接或含作者贡献关键词）

结论：最可靠，但需要用户投入少量时间；脚注条数少时体验好。

**(S3) LLM 辅助建议 + 用户确认（可选增强）**
- LLM 只做“建议保留/丢弃 + 理由/置信度”，默认仍需用户确认（避免误删重要信息）
- 可将“任务定义”限制在“识别作者贡献/通讯作者/代码链接/伦理声明/资助信息等”以提高有用性

结论：在脚注语义复杂、噪声较多时更有力；但引入新依赖（模型/Token/网络/成本/隐私），且存在误判风险，因此适合作为 `--footnotes-filter llm` 的可选路径，而非默认强制。

---

### 3.2 “贴回正文”的位置与格式（核心设计）

用户期望：脚注内容最好出现在“注释标号”后面，例如用括号+斜体。

难点：MinerU 产物 `full.md/full.html` 通常**没有页边界**，而脚注属于“页级元素”。因此“精确定位到正文某个 token 后”需要策略。

本阶段提供两种放置策略（可配置），并明确回退行为：

**(P1) 贴回正文（优先尝试）**
- 从 `page_footnote.text` 中解析“标号/符号”与“正文”：
  - 例：`"*Project leader."` → marker=`*` content=`Project leader.`
  - 例：`"1 Corresponding author"` → marker=`1` content=`Corresponding author`
- 在 `full.md`/`full.html` 中寻找该 marker 的“可疑锚点”，并在其后追加内容：
  - Markdown：`marker` 后插入 ` (_{content}_)`（括号 + 斜体）
  - HTML：插入 `<span class="p2r-footnote-inline">(<em>content</em>)</span>`
- 幂等：插入内容带上可识别标记（HTML 可用 `data-p2r-footnote="..."`；Markdown 可用 HTML 注释包裹）
- 匹配约束（降低误插风险）：
  - 仅对“符号脚注”（`*`, `†`, `‡` 等）或明确前缀数字脚注尝试
  - 仅在文档前若干段（标题/作者区域附近）优先匹配（常见脚注所在位置）
  - 若匹配到多个候选锚点，放弃贴回（回退到 P2）

**(P2) 文末汇总（回退 & 始终可用）**
- 在文末追加一个脚注区块，并标注页码（见 3.3/3.4）
- 幂等：用 `<!-- p2r:footnotes:start/end -->` 包裹，重复运行会替换

结论：P1 能满足“贴回正文”的阅读体验，但只能在“标号可稳定匹配”时启用；P2 保证任何情况下脚注不丢失。

---

### 3.3 Markdown 注入（回退区块，不破坏正文）

策略：在 `full.md` 末尾追加一个脚注区块，并标注页码。

建议格式（示例）：

```md
<!-- p2r:footnotes:start -->
## Footnotes

### Page 1
- *Project leader.
- †Corresponding author.

### Page 2
- ...
<!-- p2r:footnotes:end -->
```

设计要点：
- 使用“标记注释”包裹，保证**幂等**（重复运行时替换该区块，而不是重复追加）
- 不尝试生成 `[^1]` 这种与正文引用绑定的脚注编号（避免错误链接）

---

### 3.4 HTML 注入（回退区块，不改结构，只追加）

策略：在 `</body>` 之前插入一个 `<section>`，同样使用注释标记保证幂等。

示例：

```html
<!-- p2r:footnotes:start -->
<section id="p2r-footnotes">
  <h2>Footnotes</h2>
  <h3>Page 1</h3>
  <ul><li>*Project leader.</li></ul>
  ...
</section>
<!-- p2r:footnotes:end -->
```

---

## 4. 详细开发任务拆解（代码层面）

### 4.1 解析脚注

- 在 `src/p2r/` 新增模块（建议 `footnotes.py`）：
  - `extract_page_footnotes(content_list_path) -> dict[int, list[str]]`
  - 清洗：`strip()`、去空行、同页去重（保持顺序）
  - 排序：同页按 `bbox[1]`（y1）升序

### 4.2 注入 Markdown/HTML（幂等）

- `inject_footnotes_markdown(md_path, footnotes_by_page)`
  - 若存在 `<!-- p2r:footnotes:start --> ... end -->`：替换
  - 否则：追加到文件末尾（保留原文件换行风格）

- `inject_footnotes_html(html_path, footnotes_by_page)`
  - 若存在标记区块：替换
  - 否则：插入到 `</body>` 前；若找不到 `</body>`，则直接追加

### 4.3 与现有流程集成点

当前流程（Phase 1/现状）：
`download_result()` → 解压 → `_organize_output_dir()`（把 raw 放入 `raw/`）

集成建议：
- 在 `_organize_output_dir()` **之后**执行脚注注入（因为 `*_content_list.json` 已经被移动到 `raw/`，定位更稳定）
- 扫描输出目录：
  - content_list：`output_dir/raw/*_content_list.json`（若多个，按“最新/唯一”策略或直接报错提示）
  - markdown：`output_dir/full.md`（当前默认产物）
  - html：`output_dir/*.html`（可能是 `full.html`，也可能未来出现多文件）

### 4.4 CLI 与配置（建议）

- 默认行为：自动注入脚注（因为这是“阅读重要信息补全”）
- 提供开关：`--no-footnotes`（用于用户明确不需要脚注时）
- （可选）提供 `--footnotes-source page_footnote|all_discarded` 以支持未来扩展

---

### 4.2.1 贴回正文（可选优先策略）

新增：
- `inject_inline_footnotes_markdown(md_path, footnotes_by_page) -> dict`（返回匹配/回退统计）
- `inject_inline_footnotes_html(html_path, footnotes_by_page) -> dict`

行为：
- 尝试按 marker 匹配锚点并插入括号+斜体内容
- 对无法匹配的脚注，保留在“文末汇总区块”中（避免丢失）

### 4.3 脚注筛选（可选）

新增：
- `filter_footnotes_rule_based(...)`
- `filter_footnotes_interactive(...)`（Rich Prompt）
- `filter_footnotes_llm_suggest(...)`（仅建议 + 用户确认；默认关闭）

---

## 5. 测试计划（必须覆盖）

单测建议（pytest）：
- **提取测试**：给定简化的 `content_list` fixture，断言能正确分组/排序/去重
- **幂等测试**：
  - 对同一 `full.md` 连续运行两次，结果不重复
  - HTML 注入同理
- **集成级（无网络）**：
  - 构造临时目录：`full.md`、`full.html`、`raw/*_content_list.json`
  - 执行“后处理函数”，断言产物包含脚注区块且 `images/` 不受影响

验收标准：
- `full.md`、`full.html` 均能看到脚注区块
- 重复运行 `p2r convert ... -o same_dir` 不会重复追加脚注区块
- 若不存在 `page_footnote`，不报错（只是不注入，并在 CLI 输出提示“0 footnotes found”）
 - 若启用“贴回正文”，只有在满足匹配约束时才会插入；其余脚注仍在文末区块可见

---

## 6. 风险与边界情况

- **脚注被识别为其他类型**：短期不处理；未来可把 `aside_text/footer` 纳入候选（需更强去噪规则）
- **跨页脚注**：本阶段按页展示，未来可做“相邻页文本连续性”合并（高风险，需可选开关）
- **重复脚注/版权页脚混入**：本阶段仅做“同页完全相同文本去重”；更强规则留后续
- **多 HTML 文件**：默认对输出目录下所有 `*.html` 注入（未来可仅注入主文件）

---

## 7. 里程碑与工作量预估

- M1（0.5d）：脚注提取 + 样例验证（基于真实输出）
- M2（0.5d）：Markdown/HTML 注入（幂等）
- M3（0.5d）：集成到现有 parse 流程（与 raw 目录整理兼容）
- M4（0.5d）：测试补齐 + 文档更新

合计：约 2 人日（不含后续增强）。
