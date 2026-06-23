# bid-skeleton-extraction Skill 改进计划

## 1. 概述

### 1.1 问题根因

当前 Skill 流程中，步骤 2-4 完全依赖 Agent 使用 LLM 能力执行，没有标准化的 CLI 入口。Agent 在执行过程中：
- 创建了 4 个临时 Python 脚本（generate_step2_3.py、fix_step3.py、step4_enhance.py、fix_issues.py）污染输出目录
- 去重逻辑误判导致步骤4的增强内容被跳过
- 章节切分逻辑需要反复调试
- 输出结果不可重现、不可验证

### 1.2 改进目标

为步骤 2-4 添加 CLI 脚手架命令，使 Agent 执行时有标准化的输入/输出接口，消除临时脚本的产生，并提供输出验证机制。

### 1.3 实现方式

**CLI 脚手架 + Agent 填充**：CLI 负责输入读取、结构化数据展示、输出格式校验和文件写入，Agent 负责核心内容生成。CLI 不替代 LLM 能力，但提供标准化的执行框架。

## 2. 当前状态分析

### 2.1 现有目录结构

```
.trae/skills/bid-skeleton-extraction/
├── SKILL.md                          # 流程定义
├── scripts/
│   ├── cli.py                        # CLI 入口（仅 parse + template）
│   ├── extractor.py                  # 文件解析模块
│   └── inject_placeholders.py        # Word 模板生成
└── references/
    └── company-profile.json          # 公司风险规则库
```

### 2.2 现有 CLI 命令

| 命令 | 类型 | 状态 |
|------|------|------|
| `parse` | CLI | ✅ 已有 |
| `template` | CLI | ✅ 已有 |
| 步骤2（关键信息提取） | Agent LLM | ❌ 无 CLI |
| 步骤3（骨架提取） | Agent LLM | ❌ 无 CLI |
| 步骤4（骨架完善） | Agent LLM | ❌ 无 CLI |

### 2.3 输入输出数据流

```
inputs/招标文件.docx
  │
  ├─[parse CLI]──► structured_content.json
  │                    │
  │    ┌───────────────┼───────────────┐
  │    ▼               │               ▼
  │  [步骤2: Agent]    │          [步骤3: Agent]
  │  bid-extraction-   │          skeleton.json
  │  result.json       │               │
  │    │               │               ▼
  │    │               └──────► [步骤4: Agent]
  │    │                        skeleton.json（更新）
  │    │                        bid-writing-guide.json
  │    │                               │
  │    │                               ▼
  │    │                     [template CLI]──► template.docx
```

## 3. 改进方案

### 3.1 新增 CLI 子命令

新增 3 个子命令，使 Agent 可以通过 CLI 执行步骤 2-4：

```
cli.py
├── parse          # 已有：解析招标文件
├── template       # 已有：生成 Word 模板
├── extract-info   # 新增：步骤2 - 关键信息提取（脚手架）
├── skeleton-gen   # 新增：步骤3 - 骨架提取（脚手架）
├── skeleton-enhance # 新增：步骤4 - 骨架完善（脚手架）
└── validate       # 新增：验证 skeleton.json 结构
```

### 3.2 子命令详细设计

#### 3.2.1 `extract-info` — 步骤2 关键信息提取脚手架

```
用法：python3 scripts/cli.py extract-info <structured_content.json> --output <bid-extraction-result.json>

功能：
1. 读取 structured_content.json，提取 plain_text
2. 将 plain_text 输出为格式化文本供 Agent 分析
3. 输出提示：Agent 需按照 bid-info-extraction SKILL.md 的 JSON Schema 生成 bid-extraction-result.json
4. Agent 生成 bid-extraction-result.json 后，CLI 校验 JSON 结构和必要字段
5. 验证通过后保存到指定路径
```

**关键行为**：
- 读取 `structured_content.json` 的 `plain_text` 字段
- 打印文档概要（word count、H1 标题列表、关键数据位置提示）供 Agent 上下文参考
- Agent 使用 LLM 生成 `bid-extraction-result.json` 内容
- CLI 校验字段完整性（meta、basicInfo、timeline 等必填字段是否存在）
- 用 `json.dumps` 保存，避免中文引号问题

**CLI 参数**：
- `structured_content_path`（必填）：structured_content.json 路径
- `--output, -o`（必填）：输出 bid-extraction-result.json 路径

#### 3.2.2 `skeleton-gen` — 步骤3 骨架提取脚手架

```
用法：python3 scripts/cli.py skeleton-gen <structured_content.json> --output <skeleton.json>

功能：
1. 读取 structured_content.json 的 elements
2. 识别"响应文件格式"章节（H1 关键词匹配，降级到最后一章）
3. 提取封面和子章节边界，输出结构化的目录供 Agent 参考
4. Agent 根据 SKILL.md 规则生成完整的 skeleton.json
5. CLI 运行 self-check 验证输出
6. 通过后保存
```

**关键行为**：
- 扫描 elements 查找 H1=1 的章节，定位"响应文件格式"（关键词："响应文件格式"、"投标文件格式"、"响应文件组成"）
- 降级策略：未匹配时取最后一个 H1 章节
- 扫描该章节内的 elements，识别封面区域（到第一个编号段落之前）和子章节边界（识别 `数字.关键词` 模式）
- 输出结构化的"章节地图"供 Agent 参考：
  ```
  === 响应文件格式章节结构 ===
  封面元素: [481, 502) — 7 个元素（包含采购编号、供应商、日期行）
  子章节1: [502, 525) 1.响应函 — 23 个元素
  子章节2: [525, 534) 2.授权委托书 — 7 个元素
  ...
  ```
- Agent 根据此地图和 SKILL.md 占位符规则生成 skeleton.json
- CLI 运行 [3.2.4 validate](#324-validate--验证-skeletonjson-结构) 中的校验逻辑
- 通过后保存到 `--output`

**CLI 参数**：
- `structured_content_path`（必填）：structured_content.json 路径
- `--output, -o`（必填）：输出 skeleton.json 路径

#### 3.2.3 `skeleton-enhance` — 步骤4 骨架完善脚手架

```
用法：python3 scripts/cli.py skeleton-enhance --skeleton <skeleton.json> --bid-info <bid-extraction-result.json> --output-dir <目录>

功能：
1. 读取 skeleton.json 和 bid-extraction-result.json
2. 识别目标章节（商务资料、响应方案）
3. 输出增强提示供 Agent 参考
4. Agent 生成增强后的 skeleton.json 和 bid-writing-guide.json
5. CLI 运行验证
6. 通过后保存
```

**关键行为**：
- 读取两个输入文件，解析章节结构
- 识别"商务资料"章节（关键词：商务资料、商务文件、商务部分）和"响应方案"章节
- 从 `bid-extraction-result.json` 提取可合并数据：
  - `qualifications` → 商务资料
  - `evaluationCriteria` + `technicalRequirements` → 响应方案
  - `disqualifyingFactors` → 编写指南
- 输出增强提示：
  ```
  === 增强提示 ===
  [商务资料] 可合并：资质要求 4 项、人员要求 3 项、业绩要求 2 项、财务要求 1 项
  [响应方案] 可合并：评审方式 1 项、技术需求 1 项、服务要求 1 项
  [编写指南] 废标因素 7 项
  === 去重警告 ===
  [商务资料] "营业执照" 已存在于 5.1.2
  [商务资料] "人员资质" 已存在于 5.4
  ```
- Agent 根据提示生成增强内容，按 SKILL.md 4.1-4.4 规则合并
- CLI 运行 [3.2.4 validate](#324-validate--验证-skeletonjson-结构) 中的校验逻辑
- 通过后保存 skeleton.json（更新）和 bid-writing-guide.json

**CLI 参数**：
- `--skeleton, -s`（必填）：skeleton.json 路径
- `--bid-info, -b`（必填）：bid-extraction-result.json 路径
- `--output-dir, -o`（必填）：输出目录
- `--guide-only`（可选）：仅生成 bid-writing-guide.json，不更新 skeleton.json

#### 3.2.4 `validate` — 验证 skeleton.json 结构

```
用法：python3 scripts/cli.py validate <skeleton.json>

功能：
1. 验证 JSON 可解析
2. 检查 cover_template 结构完整性
3. 检查章节结构
4. 检查占位符有效性
5. 输出验证报告
```

**验证项目**（对应 SKILL.md 3.7 Self-Check）：

| 检查项 | 检测逻辑 | 错误级别 |
|--------|----------|----------|
| JSON 可解析 | `json.load()` | FATAL |
| cover_template 存在 | 检查 `skeleton.cover_template` | FATAL |
| cover_template.elements 非空 | `len(elements) > 0` | ERROR |
| 封面含 SUPPLIER_NAME | 检查 elements text 中含 `{{SUPPLIER_NAME}}` | ERROR |
| 封面含 PROJECT_NO | 检查 elements text 中含 `{{PROJECT_NO}}` | ERROR |
| 封面含 SIGN_DATE | 检查 elements text 中含 `{{SIGN_DATE}}` | ERROR |
| chapters 存在 | 检查 `skeleton.chapters` | FATAL |
| 章节数 >= 2 | `len(chapters) >= 2` | ERROR |
| 章节标题合理性 | 检查标题不含"邀请书"、"须知"、"合同草案"等非法内容 | WARNING |
| 无效占位符 | 检查占位符列表中不含 `{{填写说明}}` 等非法值 | WARNING |
| 连续空行 | 检查连续 `text=""` 不超过 2 个 | WARNING |
| 表格行数 | 表格至少 1 行 | ERROR |
| 元素结构完整 | 每个元素含 type/text/is_heading/heading_level | ERROR |

**输出示例**：
```
=== skeleton.json 验证报告 ===
✅ JSON 可解析
✅ cover_template.elements 非空（7 个元素）
✅ 封面含 SUPPLIER_NAME
✅ 封面含 PROJECT_NO
✅ 封面含 SIGN_DATE
✅ 章节数: 6（>= 2）
⚠️ 警告: 章节 "4.报价表" 无 placeholders
⚠️ 警告: 封面未包含 {{PROJECT_NAME}} 占位符
✅ 无无效占位符
✅ 无连续 3+ 空行
=== 结果: 通过（2 条警告）===
```

### 3.3 目录结构变更

```
.trae/skills/bid-skeleton-extraction/
├── SKILL.md                          # 更新：新增 CLI 子命令说明
├── scripts/
│   ├── cli.py                        # 更新：新增 extract-info、skeleton-gen、skeleton-enhance、validate 子命令
│   ├── extractor.py                  # 不变：文件解析模块
│   ├── inject_placeholders.py        # 不变：Word 模板生成
│   ├── skeleton_gen.py               # 新增：步骤3 骨架提取脚手架脚本
│   ├── skeleton_enhance.py           # 新增：步骤4 骨架完善脚手架脚本
│   └── validator.py                  # 新增：skeleton.json 结构验证器
└── references/
    └── company-profile.json          # 不变
```

### 3.4 更新后的完整流程

```bash
SKILL_DIR=".trae/skills/bid-skeleton-extraction"
BID_SKILL_DIR=".trae/skills/bid-info-extraction"
OUTPUT_DIR="outputs/$(date +%Y%m%d_%H%M%S)_招标文件名"
mkdir -p "$OUTPUT_DIR"

# 步骤1：解析招标文件
python3 $SKILL_DIR/scripts/cli.py parse inputs/招标文件.docx --output "$OUTPUT_DIR/structured_content.json"

# 步骤2：关键信息提取（CLI 脚手架 + Agent 填充）
python3 $SKILL_DIR/scripts/cli.py extract-info "$OUTPUT_DIR/structured_content.json" --output "$OUTPUT_DIR/bid-extraction-result.json"

# 步骤3：骨架提取（CLI 脚手架 + Agent 填充）
python3 $SKILL_DIR/scripts/cli.py skeleton-gen "$OUTPUT_DIR/structured_content.json" --output "$OUTPUT_DIR/skeleton.json"

# 步骤3.5：验证骨架（可选，可在步骤3后立即执行）
python3 $SKILL_DIR/scripts/cli.py validate "$OUTPUT_DIR/skeleton.json"

# 步骤4：骨架完善（CLI 脚手架 + Agent 填充）
python3 $SKILL_DIR/scripts/cli.py skeleton-enhance \
    --skeleton "$OUTPUT_DIR/skeleton.json" \
    --bid-info "$OUTPUT_DIR/bid-extraction-result.json" \
    --output-dir "$OUTPUT_DIR"

# 步骤5：生成 Word 模板
python3 $SKILL_DIR/scripts/cli.py template "$OUTPUT_DIR/skeleton.json" --output "$OUTPUT_DIR/template.docx"
```

### 3.5 Agent 执行规范

Agent 在执行 CLI 脚手架命令时，必须遵循以下规矩：

1. **禁止在输出目录中创建 Python 脚本**：所有逻辑通过 CLI 命令完成，不得创建 generate_*.py、fix_*.py 等临时文件。
2. **文件写入使用 Write 工具**：Agent 生成 JSON 内容后直接写入文件，不创建中间脚本。
3. **执行完成后必须验证**：使用 `validate` 子命令检查生成的 skeleton.json。
4. **输出目录只保留 5 个核心文件**：`structured_content.json`、`bid-extraction-result.json`、`skeleton.json`、`bid-writing-guide.json`、`template.docx`。

## 4. 实现步骤

### 步骤1：创建 validator.py（验证器）
- **文件**：`.trae/skills/bid-skeleton-extraction/scripts/validator.py`
- **功能**：实现 skeleton.json 结构验证
- **模块**：`validate_skeleton(skeleton_dict) -> (bool, list[ValidationResult])`
- **验证 12 项**：JSON 解析、封面结构、占位符、章节、空行、表格等
- **测试**：用已有的 outputs/20260623_ABC软件_自采/skeleton.json 验证

### 步骤2：创建 skeleton_gen.py（步骤3 脚手架）
- **文件**：`.trae/skills/bid-skeleton-extraction/scripts/skeleton_gen.py`
- **功能**：
  - 读取 structured_content.json 的 elements
  - 识别"响应文件格式"章节边界
  - 输出"章节地图"供 Agent 参考
- **模块**：`generate_chapter_map(elements) -> ChapterMap`

### 步骤3：创建 skeleton_enhance.py（步骤4 脚手架）
- **文件**：`.trae/skills/bid-skeleton-extraction/scripts/skeleton_enhance.py`
- **功能**：
  - 读取 skeleton.json + bid-extraction-result.json
  - 识别目标章节
  - 检测去重冲突
  - 输出增强提示供 Agent 参考
- **模块**：`generate_enhance_hints(skeleton, bid_info) -> EnhanceHints`

### 步骤4：更新 cli.py（添加新子命令）
- **文件**：`.trae/skills/bid-skeleton-extraction/scripts/cli.py`
- **变更**：
  - 添加 `cmd_extract_info` 函数
  - 添加 `cmd_skeleton_gen` 函数
  - 添加 `cmd_skeleton_enhance` 函数
  - 添加 `cmd_validate` 函数
  - 注册 4 个新子命令到 argparse
- **向后兼容**：`parse` 和 `template` 子命令不变

### 步骤5：更新 SKILL.md
- **文件**：`.trae/skills/bid-skeleton-extraction/SKILL.md`
- **变更**：
  - 更新核心流程图，标注所有步骤都有 CLI 脚手架
  - 新增 CLI 子命令说明章节
  - 更新步骤 2-4 的描述，说明 CLI 脚手架的使用方式
  - 新增"Agent 执行规范"章节（禁止创建临时脚本等）
  - 更新目录结构
  - 更新完整流程示例

## 5. 验证方案

### 5.1 单元验证
- 用已有的 `outputs/20260623_ABC软件_自采/` 数据测试所有 CLI 命令
- 验证 `validate` 命令对正确 skeleton.json 返回通过
- 验证 `validate` 命令对故意破坏的 skeleton.json 返回错误

### 5.2 集成验证
- 完整执行流程，确认输出目录只包含 5 个核心文件
- 确认不再产生临时 Python 脚本
- 对比新旧流程生成的 template.docx 内容一致性

### 5.3 回归验证
- 对另一个招标文件（`XXdd证券股份有限公司ABC金融终端项目`）执行完整流程
- 验证骨架提取结果正确

## 6. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 步骤2-4 实现方式 | CLI 脚手架 + Agent 填充 | 用户指定。CLI 提供标准化 I/O，Agent 负责核心生成 |
| 步骤2 是否需要 CLI | 是，添加 extract-info | 用户指定。消除步骤2的临时脚本 |
| 验证器 | 独立 validate 子命令 | 可单独调用，也可集成到 skeleton-gen/enhance 中 |
| CLI 语言 | Python 3.8+ | 与现有代码一致 |
| 向后兼容 | 保持 parse/template 不变 | 已有输出不受影响 |
