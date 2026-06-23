---
name: bid-info-extraction
description: |
  自包含的招标文件关键信息提取 Skill。从招标文件（.docx/.pdf/.txt等）中提取结构化关键信息，结合公司风险规则库生成专属风险分析报告。
  触发场景：
  - 用户说"分析招标文件"、"提取关键信息"
  - 用户提供招标文件要求提取信息
  - 其他 Agent 通过 CLI 调用
---

# 招标关键信息提取技能（独立版）

自包含的三步流水线：文件解析 → LLM 信息提取 → HTML 报告生成。

## 简介

本技能是完全自包含的招标文件信息提取工具，内含文件解析模块、公司风险规则库和 HTML 报告模板。调用方只需传入招标文件路径，即可完成从文件解析到报告生成的完整流程。

### 核心流程

```
步骤1: 文件解析（CLI）    → structured_content.json（含 plain_text + elements）
步骤2: LLM 信息提取（Agent）→ bid-extraction-result.json
步骤3: HTML 报告生成（CLI） → report.html
```

## 前置依赖

- Python 3.8+
- python-docx（解析 .docx 文件）：`pip3 install python-docx`
- pymupdf（解析 PDF 文件，可选）：`pip3 install pymupdf`

## CLI 使用说明

本技能提供 `cli.py` 命令行工具，位于 `scripts/cli.py`。

### 子命令：parse — 解析招标文件

将招标文件解析为结构化 JSON，包含 `plain_text`（纯文本）和 `elements`（结构化元素）。

```bash
# 输出到 stdout
python3 scripts/cli.py parse <招标文件路径>

# 输出到文件
python3 scripts/cli.py parse <招标文件路径> --output <输出路径>

# 示例
python3 scripts/cli.py parse inputs/招标文件.docx
python3 scripts/cli.py parse inputs/招标文件.docx --output output/structured_content.json
```

**输出格式**：
```json
{
  "source_file": "招标文件.docx",
  "file_type": "docx",
  "plain_text": "项目名称：XXX\n第一章 投标须知\n...",
  "elements": [
    {"type": "paragraph", "style": "Normal", "text": "项目名称：XXX", "is_heading": false, "heading_level": null},
    {"type": "paragraph", "style": "Heading 1", "text": "第一章 投标须知", "is_heading": true, "heading_level": 1},
    {"type": "table", "rows": [["项目名称", "XXX"], ["项目编号", "YYY"]]}
  ]
}
```

**支持的文件格式**：.docx、.pdf、.txt、.doc、.html/.htm、.png/.jpg/.tiff/.bmp（需 Tesseract OCR）

### 子命令：report — 生成 HTML 报告

将 `bid-extraction-result.json` 注入 HTML 模板生成可视化报告。

```bash
# 输出到 stdout
python3 scripts/cli.py report <bid-extraction-result.json 路径>

# 输出到文件
python3 scripts/cli.py report <bid-extraction-result.json 路径> --output <输出路径>

# 示例
python3 scripts/cli.py report output/bid-extraction-result.json --output output/report.html
```

### 完整三步流程示例

```bash
# 设置 Skill 目录变量
SKILL_DIR=".trae/skills/bid-info-extraction"

# 步骤1：解析招标文件
python3 $SKILL_DIR/scripts/cli.py parse inputs/招标文件.docx --output output/structured_content.json

# 步骤2：Agent 使用 LLM 从 plain_text 提取信息
# - 读取 output/structured_content.json 中的 plain_text 字段
# - 按照下方"阶段1"的 JSON Schema 提取结构化信息
# - 按照下方"阶段2"进行风险规则匹配
# - 保存结果到 output/bid-extraction-result.json

# 步骤3：生成 HTML 报告
python3 $SKILL_DIR/scripts/cli.py report output/bid-extraction-result.json --output output/report.html
```

## 阶段1：招标关键信息提取（LLM 执行）

**此阶段由 Agent 使用 LLM 能力完成**，从步骤1输出的 `plain_text` 中提取结构化信息。

### 分包识别（阶段0）

在提取前，先判断项目是否包含多个分包：
- 文件中明确列出"分包一览表"、"采购需求一览表"等表格
- 出现"包1"、"包2"等编号，或"第一包"、"第二包"等表述
- 如果是多包项目，先列出所有分包供用户选择，再进行详细提取

### 提取维度

| 维度 | 字段 | 说明 |
|------|------|------|
| **meta** | `extractedAt`, `sourceFile`, `version`, `schema` | 元数据，固定 schema 版本号 |
| **basicInfo** | `projectName`, `projectNumber`, `budget`, `bidder`, `agent`, `projectDescription`, `packageInfo` | 项目基本信息 |
| **timeline** | `bidDeadline`, `bidOpening`, `qaDeadline`, `depositDeadline`, `bidBond`, `otherDates` | 所有时间节点，务必准确 |
| **qualifications** | `companyQualifications`, `personnelQualifications`, `performanceRequirements`, `consortiumAllowed` | 资质要求，逐条列出 |
| **technicalRequirements** | `functionalRequirements`, `technicalArchitecture`, `dataRequirements` | 技术和功能需求 |
| **commercialRequirements** | `pricingMethod`, `paymentTerms`, `invoiceRequirements`, `warrantyPeriod` | 商务报价要求 |
| **evaluationCriteria** | `method`, `items[]` (`name`, `weight`, `scoringRule`) | 评分标准和权重，原始数值保留 |
| **contractTerms** | `deliveryRequirements`, `acceptanceCriteria`, `penaltyClauses`, `ipClauses`, `confidentialityClauses`, `indemnityClauses`, `terminationClauses`, `otherTerms` | 合同关键条款。**注意**：子数组必须是字符串数组，格式为 `【条款类型】条款内容` |
| **submissionRequirements** | `format`, `copies`, `binding`, `sealing`, `submissionMethod` | 投标文件物理要求 |
| **disqualifyingFactors** | `string[]` | 直接导致废标的因素列表，**高优先级** |
| **deviationRequirements** | `mustRespondItemByItem`, `noDeviationAllowed`, `deviationItems[]` | 偏离项要求 |

### JSON Schema（稳定版本）

```json
{
  "meta": { "extractedAt": "", "sourceFile": "", "version": "1.0.0", "schema": "bid-info-extraction" },
  "basicInfo": { "projectName": "", "projectNumber": "", "budget": "", "bidder": {}, "agent": {}, "projectDescription": "", "packageInfo": { "hasPackages": false, "totalPackages": 0, "selectedPackage": { "packageNumber": "", "packageName": "", "packageBudget": "", "packageDescription": "" } } },
  "timeline": { "bidDeadline": "", "bidOpening": "", "qaDeadline": "", "depositDeadline": "", "bidBond": "", "otherDates": [] },
  "qualifications": { "companyQualifications": [], "personnelQualifications": [], "performanceRequirements": [], "consortiumAllowed": false, "otherRequirements": [] },
  "technicalRequirements": { "functionalRequirements": [], "technicalArchitecture": [], "dataRequirements": [], "otherTechnical": [] },
  "commercialRequirements": { "pricingMethod": "", "paymentTerms": "", "invoiceRequirements": "", "warrantyPeriod": "", "otherCommercial": [] },
  "evaluationCriteria": { "method": "", "items": [] },
  "contractTerms": { "deliveryRequirements": "", "acceptanceCriteria": "", "penaltyClauses": [], "ipClauses": [], "confidentialityClauses": [], "indemnityClauses": [], "terminationClauses": [], "otherTerms": [] },
  "submissionRequirements": { "format": "", "copies": "", "binding": "", "sealing": "", "submissionMethod": "", "other": [] },
  "disqualifyingFactors": [],
  "deviationRequirements": { "mustRespondItemByItem": false, "noDeviationAllowed": false, "deviationItems": [] },
  "riskAnalysis": { "overallRiskLevel": "", "warnings": [], "summary": "" }
}
```

> **重要**：`contractTerms` 中的子数组（penaltyClauses, ipClauses 等）必须是字符串数组，格式为 `"【条款类型】条款内容"`，不要使用对象数组。

## 阶段2：专属风险分析（LLM 执行）

加载 `references/company-profile.json`，将 `riskRules` 逐条匹配阶段1提取的结果。

### 匹配流程

1. 遍历所有 `riskRules`
2. 对于每条规则，在提取的数据全文搜索 `matchKeywords` 中的关键词
3. 如果匹配到，生成一条 `warning`，包含：
   - `ruleId`: 规则编号
   - `severity`: 继承自规则定义（high/medium/low）
   - `category`: 风险分类
   - `finding`: 具体的发现描述
   - `location`: 匹配到的原文位置/条款
   - `suggestion`: 来自规则定义的应对建议
   - `companyPolicy`: 如果规则涉及公司政策底线，标注对应的公司政策
4. 汇总整体风险等级

### 资质证书交叉比对（R012）

当规则包含 `"crossCheck": true` 时，匹配逻辑不同于普通关键词匹配：

1. **关键词匹配**：先用 `matchKeywords` 触发检查
2. **逐条比对**：将招标文件中所有资质要求与 `companyInfo.availableCompanyQualifications` 和 `companyInfo.availablePersonnelQualifications` 逐条对比
3. **标记差距**：任何不在可用列表中的证书或证明，均作为独立的 warning 条目记录

**示例**：
```json
{
  "ruleId": "R012",
  "severity": "medium",
  "category": "资质证书超出范围",
  "finding": "招标文件要求提供信息系统项目管理师证书，但我司可用证书中不包含此项",
  "location": "资质要求 - 人员资质",
  "suggestion": "识别出招标文件要求但我司不具备的资质证书，评估是否可以办理或替代"
}
```

### 公司政策底线（硬性红线）

以下条款如匹配且无法协商修改，应谨慎评估是否参与投标：
- **R005** 数据赔偿条款 - 与我司数据免责底线原则冲突
- **R006** 知识产权额外赔偿 - 我司只承担法律判决结果，不承担额外赔偿
- **R003/R004** 审计报告/完整合同 - 非上市企业不对外提供

## 输出文件命名规则

统一格式：`YYYYMMDD_HHMMSS_文件名（不含扩展名）`

- 单包项目：`YYYYMMDD_HHMMSS_文件名`
- 多包项目：`YYYYMMDD_HHMMSS_文件名_包N_包名`
- JSON 文件固定命名为 `bid-extraction-result.json`
- HTML 报告固定命名为 `report.html`

## 常见陷阱

| 陷阱 | 说明 |
|------|------|
| 忽略废标因素 | 某些微小条款可能导致废标，如签字盖章要求、密封方式等 |
| 时间计算错误 | 注意节假日顺延、以邮戳为准等特殊规定 |
| 评分权重误读 | 注意价格分/技术分/商务分各占比，以及是否有门槛分 |
| 忽视不可偏离条款 | 部分条款明确标注"不可偏离"，一旦偏离即废标 |
| 遗漏分包信息 | 大项目有多个分包，需确认我司投标的是第几包 |

## 目录结构

```
.trae/skills/bid-info-extraction/
├── SKILL.md                    # 本文件
├── scripts/
│   ├── cli.py                  # CLI 入口（parse + report 子命令）
│   └── extractor.py            # 文件解析模块
├── references/
│   └── company-profile.json    # 公司风险规则库（12 条规则）
└── assets/
    └── report-template.html    # HTML 报告模板
```
