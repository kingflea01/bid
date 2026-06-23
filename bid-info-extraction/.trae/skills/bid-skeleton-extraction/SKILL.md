---
name: bid-skeleton-extraction
description: |
  自包含的标书骨架提取 Skill。从招标文件中提取标书骨架结构、插入占位符、完善骨架并生成编写指南，最终输出 Word 模板。
  触发场景：
  - 用户说"提取标书骨架"、"生成标书结构"
  - 用户要求识别招标文件的章节模板
  - 用户要求生成标书模板文件
  - 其他 Agent 通过 CLI 调用
---

# 标书骨架提取技能（独立版）

自包含的五步流水线：文件解析 → 关键信息提取 → LLM 骨架提取 → LLM 骨架完善 → Word 模板生成。

## 核心流程

```
步骤1: 文件解析（CLI parse）           → structured_content.json（含 plain_text + elements）
步骤2: 关键信息提取（CLI extract-info + Agent）→ bid-extraction-result.json
步骤3: LLM 骨架提取（CLI skeleton-gen + Agent）→ skeleton.json（标书骨架，含封面+响应文件模板+占位符）
步骤4: LLM 骨架完善（CLI skeleton-enhance + Agent）→ skeleton.json（最终版）+ bid-writing-guide.json
步骤5: 模板生成（CLI template）        → template.docx
```

**核心原则：**
- **步骤 2-4 由 CLI 脚手架 + Agent LLM 能力共同完成。**
- **CLI 脚手架**：负责输入读取、结构化数据展示、输出去重提示和格式校验。
- **Agent LLM**：负责核心内容生成（信息提取、骨架构建、内容合并）。
- **标书骨架的来源是招标文件中的"响应文件格式"章节，而非整个招标文件的目录结构。**

## CLI 子命令总览

```bash
python3 scripts/cli.py parse <招标文件> [--output <path>]          # 步骤1
python3 scripts/cli.py extract-info <structured.json> --output <path>  # 步骤2 脚手架
python3 scripts/cli.py skeleton-gen <structured.json> --output <path>  # 步骤3 脚手架
python3 scripts/cli.py skeleton-enhance -s <skeleton.json> -b <bid-info.json> -o <dir>  # 步骤4 脚手架
python3 scripts/cli.py validate <skeleton.json>                   # 验证
python3 scripts/cli.py template <skeleton.json> [--output <path>] # 步骤5
```

## 前置依赖

- Python 3.8+
- python-docx：`pip3 install python-docx`
- pymupdf（可选，解析 PDF）：`pip3 install pymupdf`

## 步骤1：文件解析

使用 CLI `parse` 子命令将招标文件解析为结构化 JSON：

```bash
# 输出到 stdout
python3 scripts/cli.py parse <招标文件路径>

# 输出到文件
python3 scripts/cli.py parse <招标文件路径> --output <输出目录>/structured_content.json
```

输出 JSON 包含 `plain_text`（纯文本）和 `elements`（结构化元素数组）。

## 步骤2：关键信息提取

使用 CLI `extract-info` 子命令启动关键信息提取脚手架：

```bash
python3 scripts/cli.py extract-info <输出目录>/structured_content.json --output <输出目录>/bid-extraction-result.json
```

**CLI 输出**：
- 文档概要（文件名、类型、字符数、元素数）
- H1 标题列表
- Agent 操作提示

Agent 根据 CLI 输出的文档概要和 SKILL.md 中的 JSON Schema，从 `plain_text` 中提取完整的关键信息，直接使用 Write 工具写入 `<输出目录>/bid-extraction-result.json`。

> **禁止**：不要在输出目录中创建 Python 脚本来生成此文件。Agent 应直接用 Write 工具写入 JSON。

此步骤与步骤 3 可并行执行，共享同一份 `structured_content.json`。

## 步骤3：LLM 骨架提取

### 3.0 启动脚手架

使用 CLI `skeleton-gen` 子命令生成章节地图：

```bash
python3 scripts/cli.py skeleton-gen <输出目录>/structured_content.json --output <输出目录>/skeleton.json
```

CLI 输出结构化的章节地图，帮助 Agent 精确识别封面和子章节边界。**此阶段核心逻辑由 Agent 使用 LLM 能力完成**，从 `structured_content.json` 的 `elements` 中提取**标书骨架**。

### 核心概念：标书骨架 ≠ 招标文件目录

标书骨架是**供应商需要填写的响应文件模板**，不是招标文件本身的章节结构。

招标文件通常包含：
- 邀请书、供应商须知、合同草案等 → 这些是**采购人**写的内容，**不是标书骨架**
- **响应文件格式**（通常为最后一章） → 这才是**供应商要填写的标书模板**，是骨架的来源

### 3.1 识别"响应文件格式"章节

在 `elements` 中，通过以下方式定位标书模板章节：

**识别关键词**（按优先级）：
1. H1 标题包含："响应文件格式"、"投标文件格式"、"响应文件组成"
2. H1 标题为最后一章（如果上述关键词未命中，默认取最后一个 H1 章节）

**识别方法**：
1. 找到所有 `heading_level=1` 的元素
2. 逐个检查 H1 的 `text` 是否包含上述关键词
3. 如果命中，该 H1 及其后续内容（到下一个 H1 或文件末尾）即为**响应文件格式章节**
4. 如果未命中关键词，取最后一个 H1 章节作为响应文件格式章节

### 3.2 提取封面

封面 = 响应文件格式章节中，第一个 H2/H3 **之前**的模板封面内容。

响应文件格式章节通常以一个子封面开始（如"项目单一来源采购 / 响应文件 / 采购编号：xxx / 供应商：xxx / 日期：xxx"）。

封面提取规则：
- 从响应文件格式章节的 elements 开始
- 收集所有元素，直到遇到第一个 `heading_level >= 2` 的元素
- 这些元素构成封面模板

**封面占位符替换**：
- 封面中出现的**第一个非空、非标题的段落文本**（通常是公司名） → `{{SUPPLIER_NAME}}`
- "项目名称"、"采购项目名称"后的具体名称 → `{{PROJECT_NAME}}`
- "采购编号"、"项目编号"后的编号 → `{{PROJECT_NO}}`
- "采购人"后的名称 → `{{BUYER_NAME}}`
- "日期"处 → `{{SIGN_DATE}}`

> **重要**：封面首行的公司名是**应标公司名称**，必须替换为 `{{SUPPLIER_NAME}}`，而非 `{{PROJECT_NAME}}`。

### 3.3 提取子章节模板

在响应文件格式章节内，按 `heading_level=2` 或 `heading_level=3`（或带编号的段落如"1.响应函"、"2.授权委托书"）切分子章节。

**典型子章节结构**：
```
1.响应函
2.授权委托书
3.响应保证金
4.报价表
5.商务资料
6.响应方案
```

**切分规则**：
- 以 `heading_level >= 2` 的元素或以"数字.标题"格式的段落作为子章节起点
- 从该起点到下一个子章节起点之间的所有元素属于当前子章节
- 过滤掉非模板内容（如通用的编制说明、装订要求），保留具体的格式模板

**每个子章节对象结构**：
```json
{
  "title": "子章节标题（如"1.响应函"）",
  "elements": [/* 子章节范围内的所有元素，1:1 复制 */],
  "placeholders": [/* 本章出现的占位符列表 */]
}
```

### 3.4 占位符替换规则

逐条扫描所有元素的 text 字段，匹配即替换。

#### 封面占位符（P0）

| 占位符 | 识别方法 |
|--------|----------|
| `{{SUPPLIER_NAME}}` | 封面中第一个非空、非标题的段落文本（通常是应标公司名） |
| `{{PROJECT_NAME}}` | 紧跟"项目名称"、"采购项目名称"后的具体名称 |
| `{{PROJECT_NO}}` | 紧跟"采购编号"、"项目编号"后的编号 |
| `{{BUYER_NAME}}` | 紧跟"采购人"、"采 购 人"后的名称 |
| `{{SIGN_DATE}}` | "日期"处的空白或具体日期 |

#### 响应文件占位符（P1-P2）

| 占位符 | 识别方法 |
|--------|----------|
| `{{TOTAL_PRICE_CN}}` | 报价表中"总价（大写）"行后的中文金额，或"大写："后的空白 |
| `{{TOTAL_PRICE_NUM}}` | "总价（小写）"、"¥"前的数字金额，或"小写："后的空白 |
| `{{BID_DEADLINE}}` | "截止时间"后的具体时间 |
| `{{MAX_PRICE}}` | "最高限价"后的数字金额 |
| `{{BID_BOND}}` | "响应保证金"的金额或状态 |
| `{{BUYER_ADDRESS}}` | "地址"后的具体地址 |
| `{{BUYER_CONTACT}}` | "联系人"后的人名 |
| `{{BUYER_PHONE}}` | "联系电话"后的号码 |
| `{{DELIVERY_DATE}}` | "工期/服务期/交货期"后的日期 |
| `{{PURCHASE_SCOPE}}` | "采购范围/采购内容"后的描述 |
| `{{PROJECT_LOCATION}}` | "项目实施地点"后的地址 |
| `{{LEGAL_REP_NAME}}` | "法定代表人"后的人名 |
| `{{AUTH_REP_NAME}}` | "被授权人"、"代理人"后的姓名 |
| `{{AUTH_REP_ID}}` | "身份证号"后的号码 |

#### 替换注意事项

- 替换时只改 `text` 字段，不改 `style`、`is_heading`、`heading_level`
- 同一值出现在多处时全部替换（如项目名称在封面和正文都出现）
- 如果原文值是"______"或空白 → 替换为对应语义的占位符
- **无法确定占位符类型 → 保守处理，保留原文**
- **不要生成 `{{填写说明}}` 这样的无效占位符** —— 填写说明类文本保留为普通文本即可

### 3.5 空行清理

提取骨架后，遍历 `elements`，清理多余空行：

- **封面**：移除开头连续的 `text=""` 空段落
- **各章节**：将连续 3 个及以上的空段落缩减为 1 个
- **保留**：章节间用于分隔的单个空段落

### 3.6 逐元素复制规则

| element.type | 操作 |
|-------------|------|
| `paragraph` | 完整复制 type/style/text/is_heading/heading_level；按占位符规则替换 text 中的具体值 |
| `table` | 完整复制 type/rows；逐行逐列按占位符规则替换单元格内容 |

### 3.7 Self-Check Checklist

生成 skeleton.json 前，验证以下各项：

- [ ] `cover_template.elements` 不为空
- [ ] 封面首行占位符是 `{{SUPPLIER_NAME}}`（不是 `PROJECT_NAME`）
- [ ] `cover_template.placeholders` 包含 `{{SUPPLIER_NAME}}`、`{{PROJECT_NAME}}`、`{{PROJECT_NO}}`、`{{BUYER_NAME}}`
- [ ] 章节数 >= 2（至少有响应函 + 一个其他章节）
- [ ] 章节标题来自"响应文件格式"章节（如"1.响应函"、"4.报价表"），而非招标文件的邀请书、须知等
- [ ] 各章节的 `is_heading` 和 `heading_level` 正确
- [ ] 表格的 `rows` 第一行是表头
- [ ] 无 `{{填写说明}}` 等无效占位符
- [ ] 无连续 3 个以上空段落
- [ ] JSON 可被 Python `json.load()` 正常解析

## 步骤4：LLM 骨架完善

### 4.0 启动脚手架

使用 CLI `skeleton-enhance` 子命令生成增强提示：

```bash
python3 scripts/cli.py skeleton-enhance \
    --skeleton <输出目录>/skeleton.json \
    --bid-info <输出目录>/bid-extraction-result.json \
    --output-dir <输出目录>
```

CLI 输出增强提示（可合并的数据项）和去重警告（已存在的内容），帮助 Agent 精确决策哪些内容需要合并、哪些需要跳过。**此阶段核心逻辑由 Agent 使用 LLM 能力完成**，理解 `skeleton.json` + `bid-extraction-result.json`，将招标要求**合并**到对应的标书模板章节中。

### 输入

- `skeleton.json`：步骤 3 生成的标书骨架（基于响应文件格式）
- `bid-extraction-result.json`：步骤 2 生成的招标关键信息

### 核心原则：合并而非追加

增强内容必须**合并到已有的对应章节中**，不能追加为新的独立章节。

| 来源数据 | 合并目标 | 说明 |
|----------|----------|------|
| `qualifications`（资质要求） | "商务资料"章节 | 在商务资料章节末尾添加资质证明子节 |
| `evaluationCriteria`（评分标准） | "响应方案"章节 | 在响应方案中添加评分响应要点 |
| `technicalRequirements`（技术需求） | "响应方案"章节 | 在响应方案中添加技术需求响应 |
| `disqualifyingFactors`（废标因素） | bid-writing-guide.json | 不合并到骨架，写入编写指南的检查清单 |
| `contractTerms`（合同条款） | 通常不合并 | 除非招标文件要求提供合同条款响应表 |

### 合并方法

1. **定位目标章节**：遍历 `skeleton.chapters`，通过标题关键词定位：
   - 包含"商务资料"、"商务文件"、"资质" → 资质合并目标
   - 包含"响应方案"、"技术方案"、"技术响应" → 评分/技术合并目标

2. **插入位置**：在目标章节的 `elements` 列表**末尾**插入新元素（不要在开头或中间插入）

3. **插入内容格式**：
   - 使用 `Heading 3` 样式作为子节标题
   - 使用 `Normal` 样式作为内容段落
   - 为填写项添加占位符

4. **去重检查**：插入前，扫描目标章节已有 elements 的 text 字段，使用**精确匹配 + 子串匹配**（去除空格标点后比较），避免重复内容

### 4.1 资质要求合并

从 `bid-extraction-result.json` 的 `qualifications` 中读取，合并到"商务资料"章节：

```
[Heading 3] 公司资质证明
[Normal] （1）营业执照
[Normal] （2）资质证书（具体未列明，需在响应文件中提供）
[Normal] 注：请提供上述资质证书的扫描件，加盖公章。

[Heading 3] 人员资质要求
[Normal] 请提供以下人员资质证明材料：
[Normal] （1）拟投入主要人员的学历证
[Normal] （2）拟投入主要人员的资格证书
[Normal] （3）拟投入主要人员的工作履历说明
[Normal] 注：上述材料请提供扫描件，加盖公章。

[Heading 3] 业绩要求说明
[Normal] • 供应商近三年类似项目情况（需提供合同扫描件）
[Normal] • 近三年指响应文件递交截止日之前完整三个年度
```

### 4.2 评分标准合并

从 `evaluationCriteria.items` 中读取，合并到"响应方案"章节：

```
[Heading 3] 评审响应说明
[Normal] 评审方式说明：{evaluationCriteria.method}

[Heading 3] {item.name}响应要点
[Normal] 评分标准：{item.scoringRule}
[Normal] 请确保响应文件针对"{item.name}"要求逐项响应。
```

### 4.3 技术需求合并

从 `technicalRequirements` 中读取，合并到"响应方案"章节：

```
[Heading 3] 技术需求响应
[Normal] 1. {functionalRequirement1}
[Normal] 2. {functionalRequirement2}
[Normal] 注：请逐项响应上述技术需求。
```

### 4.4 生成 bid-writing-guide.json

同时生成编写指南，包含以下字段：

```json
{
  "meta": {
    "projectName": "从 bid-extraction-result.json 提取",
    "projectNo": "从 bid-extraction-result.json 提取",
    "generatedAt": "ISO 时间戳"
  },
  "fillingPriorities": [
    {
      "placeholder": "{{PLACEHOLDER_NAME}}",
      "label": "填写项名称",
      "priority": "required|important|optional",
      "reason": "填写原因说明"
    }
  ],
  "disqualificationChecklist": [
    {
      "id": "check_001",
      "category": "废标因素分类",
      "item": "具体废标条件",
      "isRequired": true,
      "consequence": "废标"
    }
  ],
  "fillingInstructions": [
    {
      "sectionId": "章节标识",
      "sectionName": "章节名称",
      "subsections": [
        {
          "id": "子章节标识",
          "name": "子章节名称",
          "instruction": "填写说明",
          "documentType": "所需文档类型",
          "requiredFormat": "原件扫描件",
          "tips": "注意事项"
        }
      ]
    }
  ],
  "scoringGuide": [
    {
      "category": "评分类别",
      "maxScore": 30,
      "items": [
        {
          "name": "评分项名称",
          "score": 10,
          "requirements": "评分要求描述",
          "suggestion": "填写建议"
        }
      ]
    }
  ],
  "deduplicationLog": {
    "skipped": [
      {"content": "已存在内容", "reason": "已存在于某章节"}
    ],
    "added": [
      {"content": "新增内容", "location": "添加位置"}
    ]
  }
}
```

### 保存要求

必须使用 **Python json.dumps** 保存，避免中文引号导致 JSON 解析失败：

```python
import json
with open('<输出目录>/skeleton.json', 'w', encoding='utf-8') as f:
    json.dump(skeleton, f, ensure_ascii=False, indent=2)
with open('<输出目录>/bid-writing-guide.json', 'w', encoding='utf-8') as f:
    json.dump(guide, f, ensure_ascii=False, indent=2)
```

## 步骤5：生成 Word 模板

使用 CLI `template` 子命令从完善后的 `skeleton.json` 生成 Word 模板：

```bash
python3 scripts/cli.py template <输出目录>/skeleton.json --output <输出目录>/template.docx
```

## 输出格式

### skeleton.json

```json
{
  "cover_template": {
    "elements": [
      {"type": "paragraph", "style": "Normal", "text": "{{SUPPLIER_NAME}}", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "单一来源采购", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "响应文件", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "（采购编号：{{PROJECT_NO}}）", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "供应商：{{SUPPLIER_NAME}}（盖章）", "is_heading": false, "heading_level": null},
      {"type": "paragraph", "style": "Normal", "text": "日  期：{{SIGN_DATE}}", "is_heading": false, "heading_level": null}
    ],
    "placeholders": ["{{SUPPLIER_NAME}}", "{{PROJECT_NO}}", "{{SIGN_DATE}}"]
  },
  "chapters": [
    {
      "title": "1.响应函",
      "elements": [
        {"type": "paragraph", "style": "Heading 2", "text": "响应函", "is_heading": true, "heading_level": 2},
        {"type": "paragraph", "style": "Normal", "text": "致：{{BUYER_NAME}}", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Normal", "text": "1.我方已仔细研究了{{PROJECT_NAME}}采购文件的全部内容...", "is_heading": false, "heading_level": null}
      ],
      "placeholders": ["{{BUYER_NAME}}", "{{PROJECT_NAME}}"]
    },
    {
      "title": "4.报价表",
      "elements": [
        {"type": "paragraph", "style": "Heading 2", "text": "报价表", "is_heading": true, "heading_level": 2},
        {"type": "table", "rows": [["项目", "金额（小写）", "金额（大写）"], ["响应报价", "{{TOTAL_PRICE_NUM}}", "{{TOTAL_PRICE_CN}}"]]}
      ],
      "placeholders": ["{{TOTAL_PRICE_NUM}}", "{{TOTAL_PRICE_CN}}"]
    },
    {
      "title": "5.商务资料",
      "elements": [
        {"type": "paragraph", "style": "Heading 2", "text": "商务资料", "is_heading": true, "heading_level": 2},
        {"type": "paragraph", "style": "Normal", "text": "5.1 供应商基本情况", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Normal", "text": "5.1.1 供应商情况简介；", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Normal", "text": "5.1.2 营业执照、资质证书等。", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Heading 3", "text": "公司资质证明", "is_heading": true, "heading_level": 3},
        {"type": "paragraph", "style": "Normal", "text": "（1）营业执照", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Normal", "text": "（2）ISO27001认证", "is_heading": false, "heading_level": null}
      ],
      "placeholders": []
    },
    {
      "title": "6.响应方案",
      "elements": [
        {"type": "paragraph", "style": "Heading 2", "text": "响应方案", "is_heading": true, "heading_level": 2},
        {"type": "paragraph", "style": "Normal", "text": "1.对项目的理解；", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Normal", "text": "2.项目重点、难点分析", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Heading 3", "text": "评审响应说明", "is_heading": true, "heading_level": 3},
        {"type": "paragraph", "style": "Normal", "text": "评分标准：响应文件需对关键条款逐项响应...", "is_heading": false, "heading_level": null},
        {"type": "paragraph", "style": "Heading 3", "text": "技术需求响应", "is_heading": true, "heading_level": 3},
        {"type": "paragraph", "style": "Normal", "text": "1. 采购ABC软件，软件提供XXXXXX功能", "is_heading": false, "heading_level": null}
      ],
      "placeholders": []
    }
  ]
}
```

## Agent 执行规范

Agent 在执行流程时，必须遵循以下规矩：

1. **禁止在输出目录中创建 Python 脚本**：所有逻辑通过 CLI 命令完成，不得创建 `generate_*.py`、`fix_*.py`、`step*_*.py` 等临时文件。
2. **文件写入使用 Write 工具**：Agent 生成 JSON 内容后直接写入文件，不创建中间脚本。
3. **执行完成后必须验证**：使用 `validate` 子命令检查生成的 skeleton.json。
4. **输出目录只保留 5 个核心文件**：`structured_content.json`、`bid-extraction-result.json`、`skeleton.json`、`bid-writing-guide.json`、`template.docx`。

## 完整流程示例

```bash
SKILL_DIR=".trae/skills/bid-skeleton-extraction"
OUTPUT_DIR="outputs/$(date +%Y%m%d_%H%M%S)_招标文件名"
mkdir -p "$OUTPUT_DIR"

# 步骤1：解析招标文件
python3 $SKILL_DIR/scripts/cli.py parse inputs/招标文件.docx --output "$OUTPUT_DIR/structured_content.json"

# 步骤2：关键信息提取脚手架
python3 $SKILL_DIR/scripts/cli.py extract-info "$OUTPUT_DIR/structured_content.json" --output "$OUTPUT_DIR/bid-extraction-result.json"
# Agent 根据 CLI 输出生成 bid-extraction-result.json 并写入

# 步骤3：骨架提取脚手架
python3 $SKILL_DIR/scripts/cli.py skeleton-gen "$OUTPUT_DIR/structured_content.json" --output "$OUTPUT_DIR/skeleton.json"
# Agent 根据章节地图和 SKILL.md 规则生成 skeleton.json 并写入

# 步骤3.5：验证骨架
python3 $SKILL_DIR/scripts/cli.py validate "$OUTPUT_DIR/skeleton.json"

# 步骤4：骨架完善脚手架
python3 $SKILL_DIR/scripts/cli.py skeleton-enhance \
    --skeleton "$OUTPUT_DIR/skeleton.json" \
    --bid-info "$OUTPUT_DIR/bid-extraction-result.json" \
    --output-dir "$OUTPUT_DIR"
# Agent 根据增强提示和去重警告合并内容，更新 skeleton.json 并生成 bid-writing-guide.json

# 步骤4.5：验证增强后的骨架
python3 $SKILL_DIR/scripts/cli.py validate "$OUTPUT_DIR/skeleton.json"

# 步骤5：生成 Word 模板
python3 $SKILL_DIR/scripts/cli.py template "$OUTPUT_DIR/skeleton.json" --output "$OUTPUT_DIR/template.docx"
```

## 常见陷阱

| 陷阱 | 检测方法 | 修正 |
|------|---------|------|
| **提取了招标文件目录而非标书模板** | 章节标题是"邀请书"、"须知"、"合同草案"等 | 必须从"响应文件格式"章节提取，而非整个文件 |
| 封面 `PROJECT_NAME` 误用 | 封面首行是 `{{PROJECT_NAME}}` | 封面首行公司名应为 `{{SUPPLIER_NAME}}` |
| 增强内容追加到错误位置 | 资质/评分内容出现在独立章节中 | 必须合并到"商务资料"/"响应方案"对应章节 |
| `{{填写说明}}` 无效占位符 | 占位符列表中出现非标准占位符 | 填写说明保留为普通文本，不生成占位符 |
| 目录被当作内容 | 连续出现大量"第一章...第二章..."短段落 | 跳过封面后的目录区域 |
| 中文引号破坏 JSON | `json.load()` 解析失败 | 用 json.dumps 输出 |
| 多余空行 | 连续 3+ 个 `text=""` 段落 | 清理为最多保留 1 个空段落 |
| 去重不彻底 | 新增内容与已有内容重复 | 使用精确匹配 + 子串匹配去重 |
| 日期/金额漏替换 | text 中仍有具体日期或金额 | 按占位符规则补替换 |

## 目录结构

```
.trae/skills/bid-skeleton-extraction/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── cli.py                        # CLI 入口（6 个子命令）
│   ├── extractor.py                  # 文件解析模块
│   ├── inject_placeholders.py        # Word 模板生成
│   ├── skeleton_gen.py               # 步骤3 骨架提取脚手架（章节地图）
│   ├── skeleton_enhance.py           # 步骤4 骨架完善脚手架（增强提示+去重）
│   └── validator.py                  # skeleton.json 结构验证器
└── references/
    └── company-profile.json          # 公司风险规则库
```
