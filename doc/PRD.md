---
tags:
  - 工具/AI
---
# Product Requirement Document: p2r

| **项目**   | **内容**                                   |
| -------- | ---------------------------------------- |
| **产品名称** | p2r (PDF/Print to Reading)               |
| **核心定位** | 极简主义的学术阅读流自动化工具 (CLI)                    |
| **关键特性** | 阅读/笔记分离、MinerU 高精度解析、PicGo 图床集成、动态元数据重命名 |

---

## 1. 产品概述与工作流 (Product Overview & Workflow)

`p2r` 旨在解决学术文献管理中“文件散乱”与“阅读体验割裂”的问题。它作为一个命令行工具，连接了本地文件系统、云端 AI 解析服务 (MinerU) 和 笔记软件 (Obsidian)。

### 典型用户场景 (The User Journey)

1. **准备阶段**：用户刚刚下载了一篇名为 `10.1109@CVPR.2024.pdf` 的论文，保存在 `~/Downloads/Papers` 目录下。
    
2. **触发动作**：
    
    - 用户在该目录下打开终端 (Terminal/iTerm2)。
        
    - 输入命令：`p2r convert ./10.1109@CVPR.2024.pdf --author "Zhang" --year "2024" --conf "CVPR"`。（更一般的情况，不输入额外信息，识别文献信息并匹配）
        
3. **黑盒处理 (Automated Process)**：
    
    - 工具自动将 PDF 上传至 MinerU 进行解析。
        
    - 解析完成后，工具下载结果并进行清洗。
        
    - 图片自动上传至 PicGo 服务器，获取云端链接。
        
4. **最终交付 (Delivery)**：
    
    - **阅读文件 (HTML)**：被移动到用户指定的“HTML 阅读库”文件夹，用户通过浏览器打开阅读（利用 AI 插件辅助）。
        
    - **笔记文件 (Markdown)**：被移动到“Obsidian 仓库”指定位置。文件名已按规则重命名，且内含指向 HTML 文件的链接，图片也已替换为图床链接。
        
5. **结果**：用户在 Obsidian 中看到新笔记出现，点击笔记头部的 `local_url` 开始阅读，一边看网页一边在 Obsidian 记笔记。
    

---

## 2. 功能需求规格 (Functional Requirements)

### 2.1 交互式初始化配置

首次运行或输入 `p2r configure` 时，启动 TUI 向导。

- **MinerU 配置**：输入 API Token。
    
- **路径配置**：
    
    - `Obsidian Vault Path`: 笔记存放根目录。
        
    - `HTML Library Path`: 纯净 HTML 阅读文件存放目录。
        
- **服务集成**：
    
    - **PicGo 设置**：配置 Server 地址（默认 `http://127.0.0.1:36677`），开关状态。
        
- **命名偏好**：
    
    - 选择默认重命名模板：`Standard` (Author-Year-Title) 或 `BibTeX` (AuthorYearTitle)。
        

### 2.2 核心转换引擎

命令：`p2r convert [FILE] [ARGS]`

- **模糊参数输入**：支持接收任意数量的动态参数（`**kwargs`），如 `--journal`, `--tags`, `--publisher`。这些参数不被硬编码，而是直接存入元数据字典，供重命名和 YAML 注入使用。
    
- **MinerU Batch 流程**：严格遵循 `申请上传链接 -> 上传文件 -> 轮询进度 -> 下载结果` 的异步闭环。
    
- **PicGo 图片托管**：
    
    - 解析 ZIP 包内的图片。
        
    - 调用本地 PicGo 接口上传图片。
        
    - **失败回退机制**：若 PicGo 未响应，自动降级为“复制图片到 Obsidian 本地 assets 目录”并修改引用路径。
        

### 2.3 智能重命名系统

支持对“源文件”、“HTML产物”、“Markdown产物”应用不同的命名策略。

- **模板引擎**：支持使用 Python f-string 风格的占位符。
    
- **预设方案**：
    
    - `Standard`: `{author}-{year}-{title}`
        
    - `BibTeX`: `{author}{year}{title.split(' ')[0]}` (示例逻辑)
        

---

## 3. 数据结构设计 (Data Structure Design)

### 3.1 配置文件结构

> 详见 [6.1 配置文件规格](#61-配置文件结构-p2r_configjson)

### 3.2 交付物目录结构 (Directory Output)

假设输入参数为：`Author=Vaswani`, `Year=2017`, `Title=Attention Is All You Need`。

**场景 A：PicGo 上传成功 (云端图床模式)**

Plaintext

```
/Users/me/Documents/Paper_HTMLs/  (HTML 库)
└── Vaswani-2017-Attention Is All You Need.html

/Users/me/KnowledgeBase/Papers/   (Obsidian 库)
└── Vaswani-2017-Attention Is All You Need.md  (内部图片链接为 https://...)
```

**场景 B：PicGo 失败 (本地回退模式)**

Plaintext

```
/Users/me/KnowledgeBase/Papers/
├── assets/
│   └── Vaswani-2017-Attention Is All You Need/
│       ├── img1.png
│       └── img2.jpg
└── Vaswani-2017-Attention Is All You Need.md  (内部图片链接为 assets/...)
```

### 3.3 Markdown Frontmatter (YAML) 规范

注入到生成的 Markdown 文件头部，用于 Obsidian 索引。

YAML

```
---
title: "Attention Is All You Need"
authors: ["Vaswani"]
year: 2017
# 动态参数将自动追加到这里
conference: "NIPS"
tags: [literature-note, unread]
# 核心字段：点击即可打开 HTML
local_url: "file:///Users/me/Documents/Paper_HTMLs/Vaswani-2017-Attention Is All You Need.html"
created_date: 2026-01-15 10:00
---
```

---

## 4. 界面与交互流 (Interface & Interaction Flow)

### 4.1 初始设置向导 (Setup Wizard)

使用 Rich `Panel` 和 `Prompt` 构建。

Plaintext

```
╭── p2r Setup Wizard ──────────────────────────────────────────╮
│                                                              │
│  [1/4] 验证 MinerU 服务                                      │
│  请输入 API Token: *********************** ✅     │
│                                                              │
│  [2/4] 设置工作区                                            │
│  Obsidian 路径: /Users/me/Obsidian                    ✅     │
│  HTML 库路径: /Users/me/HTML_Lib                      ✅     │
│                                                              │
│  [3/4] 图片托管 (PicGo)                                      │
│  正在连接 127.0.0.1:36677 ... 连接成功 🟢                    │
│  是否启用自动上传? [Y/n]: Y                                  │
│                                                              │
╰──────────────────────────────────────────────────────────────╯
```

### 4.2 运行时面板 (Runtime Dashboard)

使用 Rich `Progress` (多进度条) 展示实时状态。

Plaintext

```
$ p2r convert paper.pdf --author "He" --year "2016" --tag "ResNet"

╭── p2r Processing: He-2016-ResNet ────────────────────────────╮
│                                                              │
│  1. 上传文件      [====================] 100% (Done)         │
│  2. 云端解析      [==========>.........] 50%  (Page 10/20)   │
│  3. 下载结果      [....................] 0%   (Waiting)      │
│  4. PicGo上传     [....................] 0%   (Waiting)      │
│                                                              │
╰──────────────────────────────────────────────────────────────╯
```

### 4.3 完成报告 (Completion Report)

Plaintext

```
✨ 处理完成!
------------------------------------------------------------
📄 笔记已生成: /Users/me/KnowledgeBase/Papers/He-2016-ResNet.md
🌍 阅读链接: file:///.../He-2016-ResNet.html (⌘+Click 打开)
🖼️  图片状态: 12 张图片已上传至 PicGo
------------------------------------------------------------
```

## 5. 技术决策与约束 (Technical Decisions & Constraints)

### 5.1 开发技术栈

| 项目 | 选择 | 理由 |
| :--- | :--- | :--- |
| 语言 | Python 3.10+ | MinerU API 官方示例均为 Python；丰富的 CLI/PDF 处理生态 |
| CLI 框架 | Typer + Rich | 类型安全的命令行参数解析；美观的 TUI 输出 |
| HTTP 客户端 | httpx | 支持异步请求，适合轮询任务状态 |
| PDF 元数据 | pdfplumber | 轻量级 PDF 解析，提取元数据 |

### 5.2 自动元数据识别策略

为平衡**稳定性**与**效率**，采用三级回退机制：

1. **PDF 内置元数据** (最稳定)
   - 使用 pdfplumber 提取 PDF 的 `/Title`, `/Author`, `/CreationDate` 等字段
   - 大多数学术 PDF 由出版商生成，包含完整元数据

2. **DOI 查询** (可选增强)
   - 若文件名或 PDF 元数据中包含 DOI (正则匹配 `10.\d{4,}/[^\s]+`)
   - 调用 CrossRef API (`https://api.crossref.org/works/{doi}`) 获取完整文献信息
   - 此步骤为可选，网络失败时跳过

3. **用户手动输入** (最终回退)
   - 若以上方式均无法获取，使用命令行参数 `--author`, `--year`, `--title` 等

### 5.3 MinerU 集成规格

基于 API 文档，确定以下技术约束：

| 约束项 | 值 | 说明 |
| :--- | :--- | :--- |
| 单文件大小 | ≤ 200MB | API 硬限制 |
| 单文件页数 | ≤ 600 页 | API 硬限制 |
| 每日高优先级额度 | 2000 页 | 超出后优先级降低 |
| 支持格式 | pdf, doc(x), ppt(x), png, jpg, html | - |
| 默认输出 | markdown + json | 可额外请求 html（本工具默认开启） |
| 模型版本 | `vlm` (默认) | 比 pipeline 更智能 |

**API 调用流程** (本地文件)：
```
申请上传链接 → PUT 上传文件 → 轮询 batch 状态 → 下载 ZIP 结果
POST /file-urls/batch → PUT {upload_url} → GET /extract-results/batch/{id} → GET {zip_url}
```

### 5.4 错误处理与清理策略

**原则：任何情况下不留垃圾文件**

| 阶段 | 失败场景 | 处理方式 |
| :--- | :--- | :--- |
| 上传 | 网络错误/API 错误 | 直接退出，无文件产生 |
| 解析 | MinerU 返回 `failed` | 输出错误信息，不创建任何本地文件 |
| 下载 | ZIP 下载失败 | 重试 3 次后退出，不创建本地文件 |
| 图片上传 | PicGo 失败 | 触发本地回退机制（见 2.2） |
| 用户中断 | Ctrl+C | 捕获 SIGINT，清理临时文件后退出 |

**临时文件管理**：
- 所有中间产物存放于系统临时目录 (`tempfile.mkdtemp()`)
- 仅在全流程成功后，才将最终产物移动到目标目录
- 进程退出时自动清理临时目录

### 5.5 重复文件处理

工具**不维护处理历史**，保持轻量。若目标位置已存在同名文件：

```
Vaswani-2017-Attention Is All You Need.md      # 已存在
Vaswani-2017-Attention Is All You Need_v2.md   # 新生成
Vaswani-2017-Attention Is All You Need_v3.md   # 再次处理
```

### 5.6 批量处理支持

支持以下输入形式：

```bash
# 单文件
p2r convert paper.pdf

# Glob 模式
p2r convert "*.pdf"
p2r convert "papers/*.pdf"

# 目录模式 (处理目录下所有 PDF)
p2r convert ./papers/

# 多文件
p2r convert paper1.pdf paper2.pdf paper3.pdf
```

批量处理时，MinerU 的 batch API 天然支持并行解析（单次最多 200 个文件）。

### 5.7 API Token 安全存储 (开源友好)

作为开源项目，需支持多种安全级别的 Token 配置方式：

| 优先级 | 方式 | 说明 |
| :--- | :--- | :--- |
| 1 | 环境变量 `P2R_MINERU_TOKEN` | CI/CD 友好，不入库 |
| 2 | 配置文件 `~/.p2r_config.json` | 便捷但需注意权限 (chmod 600) |

**安全提示**：
- 配置文件创建时自动设置 `600` 权限
- `p2r configure` 时提示用户环境变量方式更安全
- README 中明确说明不要将配置文件提交到版本控制

### 5.8 可扩展性设计 (预留)

以下功能作为**模块化预留**，不在 MVP 中实现：

- [ ] 断点续传 / 任务恢复
- [ ] 多图床支持 (S3, R2, imgur)
- [ ] 其他笔记软件适配 (Logseq, Notion)
- [ ] 本地 MinerU 部署支持

---

## 6. 配置文件规格 (更新)

### 6.1 配置文件结构 (`~/.p2r_config.json`)

```json
{
  "mineru_token": "YOUR_API_TOKEN",
  "paths": {
    "obsidian_vault": "/Users/me/KnowledgeBase/Papers",
    "html_library": "/Users/me/Documents/Paper_HTMLs"
  },
  "picgo": {
    "enable": true,
    "api_url": "http://127.0.0.1:36677/upload"
  },
  "naming": {
    "style": "standard",
    "template": "{author}-{year}-{title}",
    "rename_source_pdf": true
  },
  "mineru": {
    "model_version": "vlm",
    "enable_formula": true,
    "enable_table": true,
    "language": "en"
  },
  "frontmatter_template": {
    "tags": ["literature-note", "unread"]
  }
}
```

### 6.2 环境变量

| 变量名 | 说明 | 优先级 |
| :--- | :--- | :--- |
| `P2R_MINERU_TOKEN` | MinerU API Token | 高于配置文件 |
| `P2R_CONFIG_PATH` | 自定义配置文件路径 | - |

---

## 7. Frontmatter 模板自定义

用户可在配置文件中定义额外的 frontmatter 字段：

```json
{
  "frontmatter_template": {
    "tags": ["literature-note", "unread"],
    "status": "to-read",
    "custom_field": "value"
  }
}
```

生成的 Markdown 将合并用户模板与动态字段：

```yaml
---
title: "Attention Is All You Need"
authors: ["Vaswani"]
year: 2017
conference: "NIPS"
tags: [literature-note, unread]  # 来自模板
status: "to-read"                # 来自模板
custom_field: "value"            # 来自模板
local_url: "file:///..."         # 动态生成
created_date: 2026-01-15 10:00   # 动态生成
---
```

---

## 8. Action Plan (开发路线)

### Phase 1: 项目骨架与 MinerU 集成

**目标**：验证 MinerU API 可用性，完成核心解析流程

- [x] 初始化 Python 项目结构 (pyproject.toml, src/, tests/)
- [x] 实现配置管理模块 (读取/写入 ~/.p2r_config.json)
- [x] 实现 MinerU API 客户端
  - [x] 文件上传链接申请
  - [x] 文件上传 (PUT)
  - [x] 任务状态轮询
  - [x] ZIP 结果下载与解压
- [x] 添加基础 CLI 命令 (`p2r convert`)
- [x] **测试点**：手动测试不同类型 PDF 的解析效果

### Phase 2: 元数据提取与文件处理

**目标**：脚注补全与阅读产物清洗（Markdown + HTML）

- [ ] 从 `*_content_list.json` 提取脚注（`type=page_footnote`，必要时扩展到 `aside_text/footer`）
- [ ] 将脚注注入到 `full.md` 与 `full.html`（幂等：重复运行不重复追加）
- [ ] 支持脚注放置策略：
  - [ ] 追加式（文末按页汇总）
  - [ ] 贴回正文（在注释标号后追加括号/斜体内容；匹配失败回退到追加式）
- [ ] 支持脚注筛选策略：
  - [ ] 纯规则（去重、去空、黑名单/长度阈值）
  - [ ] 交互式确认（逐条保留/丢弃）
  - [ ] 可选：LLM 辅助建议 + 用户确认（仅建议，不自动删除）
- [ ] 输出目录整理（raw/debug 文件归档，不破坏 `images/` 引用）

### Phase 3: 元数据提取与文件处理

**目标**：完成文件重命名和元数据注入

- [ ] 实现 PDF 元数据提取 (pdfplumber)
- [ ] 实现 DOI 正则匹配与 CrossRef 查询 (可选)
- [ ] 实现命名模板引擎
- [ ] 实现 Frontmatter 生成与注入（包含 `local_url` 指向 HTML）
- [ ] 实现文件移动逻辑 (临时目录 → 目标目录)
- [ ] 实现重复文件版本号递增
- [ ] 实现源 PDF 原地重命名

### Phase 4: PicGo 集成与回退机制

**目标**：完成图片托管功能

- [ ] 实现 PicGo API 客户端
- [ ] 实现 Markdown 图片链接替换
- [ ] 实现 PicGo 失败回退 (本地 assets 目录)
- [ ] 实现 HTML 图片路径处理

### Phase 5: 交互体验优化

**目标**：完善 CLI 交互与错误处理

- [ ] 实现 `p2r configure` 交互式向导 (Rich TUI)
- [ ] 实现运行时进度面板 (多进度条)
- [ ] 实现完成报告输出
- [ ] 实现 Ctrl+C 中断处理与临时文件清理
- [ ] 实现批量文件输入支持 (glob, 目录, 多文件)

### Phase 6: 测试与文档

**目标**：确保稳定性，准备开源发布

- [ ] 编写单元测试 (核心模块)
- [ ] 编写集成测试 (端到端流程)
- [ ] 编写 README.md (安装、配置、使用)
- [ ] 添加 CI 配置 (GitHub Actions)
- [ ] 发布到 PyPI

### Phase 7: 扩展功能 (可选)

- [ ] 断点续传 / 任务恢复
- [ ] 多图床支持
- [ ] 其他笔记软件适配

---

## 9. 命令行接口速查 (CLI Reference)

```bash
# 配置向导
p2r configure

# 单文件转换
p2r convert paper.pdf
p2r convert paper.pdf --author "He" --year "2016" --title "ResNet"

# 批量转换
p2r convert "*.pdf"
p2r convert ./papers/
p2r convert paper1.pdf paper2.pdf

# 查看配置
p2r config show

# 版本信息
p2r --version
```

---

## 10. 术语表 (Glossary)

| 术语 | 说明 |
| :--- | :--- |
| MinerU | OpenDataLab 提供的 PDF 解析云服务 |
| PicGo | 开源图床上传工具，支持多种图床后端 |
| Frontmatter | Markdown 文件头部的 YAML 元数据块 |
| VLM | Vision-Language Model，MinerU 的高级解析模型 |
