---
name: tender-bid-analyzer
description: 解析中文招标文件指定分包，结合公司代码 Cx 与产品代码 Px，生成应标分析报告与可编辑的 bid.docx。适用于用户提供招标文件、包号、Cx、Px 的场景。
---

# 招标文件应标工作台

一个 Skill，三个模块：`core` 负责提取、结构合并与校验，`analysis` 负责应标分析，`builder` 负责标书 Word 组装。唯一入口是 `scripts/run.py`。

## 硬性规则

- 分析前必须收齐四项输入：招标文件、包号、公司代码 `Cx`、产品代码 `Px`。缺少任一项，只追问一次并停止。
- 用户提供的每个 `Px` 都视为属于所给分包，不校验产品与分包是否匹配。
- `Cx`、`Px` 只作为配置文件名和内部选择代码。分析报告和标书**可以**写入 C1/P1 的真实公司名、信用代码、法人、地址等信息。
- 单一来源项目默认 `Cx` 具备应标资格且为被邀请单位，不再核验身份。
- 不计算、不推荐报价。只记录价格分公式。
- 不提供法律意见。法律敏感条款标注需人工复核。
- 内部提取时标注来源；报告中不展示来源标记。
- 报告中不列“未载明”的关键信息行；招标文件未载明的项目直接省略。
- 不得用假设填补空白或打码字段。
- 提取前读 `references/extraction-schema.md`；写报告前读 `references/output-template.md`；做标书前读 `references/bid-generation.md`。

## 模块与入口

```text
scripts/
├── run.py                 # 唯一入口
├── core/
│   ├── extract.py         # tender.json + extracted.txt
│   ├── outline.py         # 响应文件章节识别
│   ├── structure.py       # 招标章节 + 用户模板合并
│   ├── extract_docx.py    # DOCX 文本提取
│   ├── validate_tables.py # 质量门禁
│   └── output_dir.py      # 项目输出目录
├── analysis/              # 报告规则（按 references 执行）
└── builder/               # 标书组装
```

运行方式：

```bash
# 提取 + 结构合并
python3 scripts/run.py structure --root <工作区> --tender <文件> \
  --package <包号> --company C1 --product P1 \
  --template config/bid-templates/default.md

# 只提取
python3 scripts/run.py extract --root <工作区> --tender <文件>

# 生成标书
python3 scripts/run.py build --root <工作区> --tender <文件> \
  --package <包号> --company C1 --product P1
```

## 输入与配置

```text
config/companies/Cx.md          # 公司信息 + 公司级红线
config/products/Px.md           # 产品信息 + 产品级红线
config/bid-templates/*.md       # 标书章节模板
config/bid-content/*.md         # 章节内容模板
```

只读取与所给代码匹配的文件。代码文件不存在时，停止并列出可用代码。公司级与产品级红线同时适用，取并集。

## 目录约定

- `input/`：工作区根目录下的 `input/`，用户放置招标文件。用户只给文件名时从该目录查找。
- `output/`：所有输出只能写入工作区根目录下的 `output/`。
- 每个项目新建 `output/yyyymmdd-hhmm-招标公司名-项目名/`。招标公司名优先采购人，其次代理机构；项目名优先项目名称，其次项目编号。非法字符替换为 `-`，每段最多 40 字，重名追加 `-2`。
- 文件夹名只使用招标单位、项目名称等公开信息，不得写入 C1/P1 的真实名称。

每个项目文件夹输出：

```text
report.md          # 应标分析报告
bid.docx           # 标书正文
structure.md       # 标书章节结构
structure.json     # 结构树
placeholders.md    # 占位符清单
template_cleanup.md # 模板清洗记录
qa-bid.txt         # 标书校验结果
tender.json        # 招标结构化索引
extracted.txt      # 招标全文
qa.txt             # 质量门禁结果
timing.json        # 各阶段耗时
```

## 执行流程

1. 校验四项输入；定位招标文件、`Cx`、`Px` 配置文件。
2. 运行 `scripts/run.py structure`，生成 `tender.json`、`extracted.txt`、`qa.txt`、`structure.md`、`structure.json`、`timing.json`。
3. 阅读 `structure.md`。若有“待确认”项（未识别格式章节、内容模板缺失、章节未匹配），先向用户说明，不擅自猜测。
4. 依据 `tender.json` 与 `extracted.txt` 完成分析：采购方式、资格、技术、商务、红线、评分、策略、风险。
5. 按 `references/output-template.md` 写 `report.md`，保存到项目文件夹。
6. 运行 `scripts/run.py build` 生成 `bid.docx`、`placeholders.md`、`template_cleanup.md`、`qa-bid.txt`。`build` 只读 `tender.json`、`structure.json`、Cx/Px 配置，不读 `report.md`。

## 采购方式分支

单一来源：

- 不使用竞争性投标措辞。
- 聚焦资格合规、最终报价上限、合同偏差和协商要点。
- 默认 `Cx` 为被邀请单位，直接进入资格、响应与合同分析。

竞争性：

- 识别子类型与评审方法。
- 执行资格性、符合性、技术偏差、商务偏差和评分分析。
- 不宣称中标概率。

## 红线与评分

按 `references/redline-rules.md`、`references/scoring-rules.md` 执行。

- 公司级和产品级红线同时适用。
- 摘录触及红线的招标条款，再说明风险、等级和建议。
- 与红线冲突的实质性条款一律为 `否决`。
- 合同空白字段按风险处理。
- 价格分只记录公式，不测算、不推荐报价。
- 没有评分规则时，删除评分章节。

## 质量门禁

检查 `qa.txt`：

- 各分包预算合计与总预算是否一致。
- 日期顺序：文件获取 < 递交截止 < 开启。
- 分包号连续，包名跨章节一致。
- 空白、打码或“详见附件”字段已列出。
- `structure.md` 的章节数、层级、来源标注是否合理。
- `timing.json` 是否在预算内：提取与结构合计应低于 1 秒。

## 输出

报告按 `references/output-template.md` 的七段结构：一页结论、项目与目标包全貌、资格门槛、技术与商务匹配、商务与合同风险、策略与待澄清、风险与文件异常。有评分规则时增加“评分测算（非价格）”。

标书结构按 `references/bid-generation.md` 执行。`build` 产出 `bid.docx`、占位符清单、模板清洗记录和 `qa-bid.txt`；`build` 不读取 `report.md`，两条链路互不等待。

## 禁止事项

- 不得把任何输出写到 `output/` 以外。
- 不得输出“仅关键信息”的报告。
- 不得分析其他分包的技术内容。
- 不得推荐投标报价。
- 不得编造资格、参数、分数或日期。
- 不得把单一来源项目当作竞争性投标。
