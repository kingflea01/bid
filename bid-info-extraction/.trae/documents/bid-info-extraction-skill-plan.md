# 计划：将招标关键信息提取封装为独立 Skill（CLI 可调用）

## 摘要

将当前项目中分散在 `skills/bid-info-extraction/` 和 `skills/file-content-parser/` 的功能封装为一个独立的、自包含的 Trae Skill，放在 `.trae/skills/bid-info-extraction/` 下。该 Skill 既可被 Trae IDE Agent 通过 SKILL.md 触发，也可通过 CLI 命令行被任何 Agent 调用。

## 当前状态分析

### 现有资源
- `skills/bid-info-extraction/` — 招标信息提取 Skill（LLM 驱动，无 Python 脚本）
  - `SKILL.md` — 提取流程定义 + JSON Schema（303 行）
  - `references/company-profile.json` — 公司风险规则库（12 条规则）
  - `assets/report-template.html` — HTML 报告模板（513 行）
  - `agents/openai.yaml` — Trae Agent 接口配置
- `skills/file-content-parser/scripts/extractor.py` — 文档解析脚本（308 行）
  - 支持 .docx / .pdf / .txt / .doc / .html / 图片
  - 输出 JSON（含 `plain_text` + `elements`）

### 核心问题
1. **功能分散**：文件解析和信息提取在两个独立 Skill 中，调用者需要自行串联
2. **依赖外部**：当前 bid-info-extraction 不包含文件解析，需先手动运行 file-content-parser
3. **不可 CLI 调用**：信息提取是 LLM 驱动的，没有 Python 脚本入口
4. **路径耦合**：SKILL.md 中的命令路径引用 `skills/file-content-parser/scripts/extractor.py`，脱离项目后无法工作

### 约束
- 信息提取的核心工作（阶段1 + 阶段2）由 LLM 完成，无法用纯 Python 实现
- 需要提供 CLI 入口，让非 Trae Agent 也能调用
- company-profile.json 需要内嵌，使 Skill 完全自包含

## 设计方案

### 核心思路

将整个提取流程分为 3 个确定性步骤 + 1 个 LLM 步骤，CLI 工具负责确定性步骤，SKILL.md 负责 LLM 步骤的指引：

```
步骤1: 文件解析（Python CLI）→ structured_content.json
步骤2: LLM 信息提取（Agent 执行）→ bid-extraction-result.json
步骤3: HTML 报告生成（Python CLI）→ report.html
```

CLI 提供两个子命令：
- `parse` — 执行步骤1（文件 → JSON）
- `report` — 执行步骤3（JSON → HTML）

Agent 调用完整流程：
```bash
# 步骤1：解析文件
python3 .trae/skills/bid-info-extraction/scripts/cli.py parse inputs/招标文件.docx > output/structured_content.json

# 步骤2：Agent 使用 LLM 从 plain_text 提取信息，保存到 output/bid-extraction-result.json
# （遵循 SKILL.md 中的 schema 和流程指引）

# 步骤3：生成报告
python3 .trae/skills/bid-info-extraction/scripts/cli.py report output/bid-extraction-result.json --output output/report.html
```

### 目标目录结构

```
.trae/skills/bid-info-extraction/
├── SKILL.md                              # Skill 定义（含完整提取流程指引 + JSON Schema）
├── scripts/
│   ├── cli.py                            # CLI 入口（parse + report 子命令）
│   └── extractor.py                      # 文件解析模块（从 file-content-parser 复制）
├── references/
│   └── company-profile.json              # 公司风险规则库
└── assets/
    └── report-template.html              # HTML 报告模板
```

## 实施步骤

### 步骤1：创建目录结构

```bash
mkdir -p .trae/skills/bid-info-extraction/scripts
mkdir -p .trae/skills/bid-info-extraction/references
mkdir -p .trae/skills/bid-info-extraction/assets
```

### 步骤2：复制文件解析模块

- **操作**：复制 `skills/file-content-parser/scripts/extractor.py` → `.trae/skills/bid-info-extraction/scripts/extractor.py`
- **来源**：`/Users/kingflea/Documents/workbuddy/bid-info-extraction/skills/file-content-parser/scripts/extractor.py`（308 行）
- **修改**：无需修改，该脚本本身不依赖任何外部路径

### 步骤3：复制资源文件

- **操作**：复制 `references/company-profile.json` 和 `assets/report-template.html`
- **来源**：
  - `skills/bid-info-extraction/references/company-profile.json`
  - `skills/bid-info-extraction/assets/report-template.html`
- **修改**：无需修改

### 步骤4：创建 CLI 入口脚本

- **文件**：`.trae/skills/bid-info-extraction/scripts/cli.py`
- **功能**：
  - `cli.py parse <file_path>` — 调用 extractor.py 解析文件，输出 JSON 到 stdout
  - `cli.py report <json_path> [--output <path>]` — 读取 bid-extraction-result.json，注入 report-template.html 生成 HTML 报告
- **设计要点**：
  - 使用 argparse 解析子命令
  - `parse` 子命令直接复用 extractor.py 的 main 逻辑（import 并调用）
  - `report` 子命令读取 JSON 数据，注入到 HTML 模板的 `window.__BID_DATA__` 变量中
  - 所有路径基于 `__file__` 计算，确保 Skill 移动后仍可工作
  - 输出到 stdout 或通过 `--output` 指定文件路径

### 步骤5：编写独立 SKILL.md

- **文件**：`.trae/skills/bid-info-extraction/SKILL.md`
- **内容设计**：
  - frontmatter：name + description（含触发场景描述）
  - 简介：自包含的招标文件信息提取 Skill
  - 前置依赖：Python 3.8+、python-docx、pymupdf（可选）
  - **CLI 使用说明**：
    - `parse` 子命令的用法和示例
    - `report` 子命令的用法和示例
    - 完整三步流程示例
  - **Agent 提取流程指引**（从现有 bid-info-extraction/SKILL.md 迁移）：
    - 阶段0：分包识别
    - 阶段1：关键信息提取（含完整 JSON Schema）
    - 阶段2：风险规则匹配（含 R012 交叉比对、公司政策底线）
  - 输出文件命名规则
  - 常见陷阱
- **与现有 SKILL.md 的区别**：
  - 文件路径引用更新为相对于 `.trae/skills/bid-info-extraction/`
  - 新增 CLI 使用说明
  - 删除对 project-tracker 的自动集成描述（独立 Skill 不依赖）
  - 删除对 file-content-parser 的前置依赖描述（已自包含）

### 步骤6：验证

1. **结构验证**：确认 `.trae/skills/bid-info-extraction/` 下所有文件存在
2. **CLI parse 验证**：
   ```bash
   python3 .trae/skills/bid-info-extraction/scripts/cli.py parse inputs/XXXX营业部ABC软件单一来源采购文件-自采.docx | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'plain_text: {len(d[\"plain_text\"])} chars, elements: {len(d[\"elements\"])}')"
   ```
3. **CLI report 验证**：
   ```bash
   python3 .trae/skills/bid-info-extraction/scripts/cli.py report outputs/20260623_023953_XXXX营业部ABC软件/bid-extraction-result.json --output /tmp/test-report.html
   open /tmp/test-report.html
   ```
4. **SKILL.md 验证**：确认 frontmatter 格式正确，JSON Schema 完整

## 文件变更清单

| 序号 | 操作 | 文件路径 | 说明 |
|------|------|----------|------|
| 1 | 创建目录 | `.trae/skills/bid-info-extraction/` | Skill 根目录 |
| 2 | 创建目录 | `.trae/skills/bid-info-extraction/scripts/` | 脚本目录 |
| 3 | 创建目录 | `.trae/skills/bid-info-extraction/references/` | 参考资料目录 |
| 4 | 创建目录 | `.trae/skills/bid-info-extraction/assets/` | 资源目录 |
| 5 | 复制 | `extractor.py` → `.trae/skills/bid-info-extraction/scripts/extractor.py` | 文件解析模块 |
| 6 | 复制 | `company-profile.json` → `.trae/skills/bid-info-extraction/references/company-profile.json` | 风险规则库 |
| 7 | 复制 | `report-template.html` → `.trae/skills/bid-info-extraction/assets/report-template.html` | HTML 模板 |
| 8 | 新建 | `.trae/skills/bid-info-extraction/scripts/cli.py` | CLI 入口脚本 |
| 9 | 新建 | `.trae/skills/bid-info-extraction/SKILL.md` | Skill 定义文件 |

**不修改任何现有文件**。

## Assumptions & Decisions

1. **LLM 步骤由调用方 Agent 负责**：CLI 工具不内置 LLM 调用，信息提取的语义分析由调用方 Agent 完成。CLI 只处理确定性的文件 I/O。
2. **company-profile.json 内嵌**：风险规则库直接打包在 Skill 中，不依赖外部路径。
3. **不集成 project-tracker**：独立 Skill 不自动记录项目历史，调用方可按需自行集成。
4. **不修改现有文件**：所有现有 skills/ 和 backend/ 文件保持不变。
5. **extractor.py 原样复制**：文件解析模块无需修改，本身就是自包含的。
