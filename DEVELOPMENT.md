# 开发快速入门

## 快速启动

```bash
# 1. 激活虚拟环境
source activate.sh

# 2. 配置 API Token（首次使用）
p2r config-token YOUR_TOKEN_HERE

# 3. 测试转换（需要一个 PDF 文件）
p2r convert test.pdf -o ./output
```

## 开发工作流

### 安装开发依赖

```bash
source venv/bin/activate
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
# 格式化代码
black src/

# 检查代码质量
ruff check src/
```

## 调试技巧

### 查看配置

```bash
p2r show-config
```

### 测试 API 连接

直接在 Python 中测试：

```python
from p2r.mineru import MinerUClient
from p2r.config import get_api_token
from pathlib import Path

# 初始化客户端
client = MinerUClient()

# 测试解析
pdf_path = Path("test.pdf")
output_dir = Path("./output")

for update in client.parse_pdf(pdf_path, output_dir):
    print(update)
```

### 环境变量方式（避免保存 Token 到配置文件）

```bash
export P2R_MINERU_TOKEN="your-token-here"
p2r convert paper.pdf
```

## 项目结构说明

```
src/p2r/
├── __init__.py      # 包初始化，定义版本号
├── cli.py           # Click 命令行界面
├── config.py        # 配置文件管理（读取/写入 ~/.p2r_config.json）
└── mineru.py        # MinerU API 客户端（核心逻辑）
```

### 各模块职责

**config.py**
- 管理 `~/.p2r_config.json` 配置文件
- 支持环境变量 `P2R_MINERU_TOKEN` 覆盖配置
- 文件权限设置为 600（仅用户可读写）

**mineru.py**
- `request_upload_urls()`: 申请上传链接
- `upload_file()`: 上传 PDF 文件
- `get_batch_status()`: 查询任务状态
- `wait_for_completion()`: 轮询等待完成（生成器，支持进度显示）
- `download_result()`: 下载并解压 ZIP 结果
- `parse_pdf()`: 高层接口，整合所有步骤

**cli.py**
- 使用 Click 框架构建 CLI
- 使用 Rich 库显示进度和美化输出
- 三个命令：`convert`, `config-token`, `show-config`

## 常见问题

### Q: 虚拟环境在哪里？
A: `venv/` 目录，已在 `.gitignore` 中排除

### Q: 配置文件在哪里？
A: `~/.p2r_config.json`，权限为 600

### Q: 如何重置配置？
```bash
rm ~/.p2r_config.json
p2r show-config  # 会自动创建默认配置
```

### Q: 如何添加新的 CLI 命令？
1. 在 `cli.py` 中添加新的 `@main.command()` 函数
2. 重新安装：`pip install -e .`

### Q: MinerU API 限制是什么？
- 单文件不超过 200MB
- 单文件不超过 600 页
- 每天 2000 页高优先级额度

## Phase 1 完成标准

根据 `doc/phase1_plan.md`，以下功能已实现：

- ✅ 项目结构搭建
- ✅ 配置管理（Token、环境变量）
- ✅ MinerU API 客户端（完整流程）
- ✅ 基础 CLI 命令
- ✅ 进度显示
- ✅ 错误处理

**未实现（后续 Phase）**：
- ⏳ 文件重命名（基于论文标题）
- ⏳ 移动到 Obsidian 目录
- ⏳ 图片上传图床
- ⏳ 提取元数据（作者、年份等）
- ⏳ 生成 Frontmatter

## 贡献代码

1. 创建功能分支
2. 编写代码和测试
3. 运行 `black` 和 `ruff`
4. 提交 PR

## 联系方式

如有问题，请参考：
- [PRD 文档](doc/PRD.md)
- [Phase 1 计划](doc/phase1_plan.md)
- [MinerU API 参考](doc/mineru_api_reference.md)
