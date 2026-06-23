# 计划：封装"提取标书骨架"为独立 Skill

## 摘要

创建 `.trae/skills/bid-skeleton-extraction/`，将标书骨架提取流程封装为自包含的独立 Skill。关键变化：
1. **信息提取**：调用已有的 `.trae/skills/bid-info-extraction/` 的 CLI `parse` 命令解析文件
2. **骨架完善**：从 `enhance.py` 脚本改为 **LLM 执行**，Agent 直接理解 `skeleton.json` + `bid-extraction-result.json` 并生成完善后的骨架和编写指南
3. **模板生成**：复用 `inject_placeholders.py` 脚本生成 Word 模板

## 修改后的完整流程

```
步骤1: 文件解析（CLI parse）         → structured_content.json
步骤2: 关键信息提取（调用 bid-info-extraction Skill）→ bid-extraction-result.json
步骤3: LLM 骨架提取（Agent 执行）     → skeleton.json（形式骨架）
步骤4: LLM 骨架完善（Agent 执行）     → skeleton.json（最终版）+ bid-writing-guide.json
步骤5: 模板生成（CLI template）       → template.docx
```

与原流程的差异：
- 原步骤 8 `enhance.py` 脚本 → 改为 LLM 理解两份 JSON 并生成完善骨架
- 原 `bid-writing-guide.json` 由 `enhance.py` 生成 → 改为 LLM 在步骤 4 中一并生成
- 信息提取由内部调用 → 改为调用独立的 `bid-info-extraction` Skill

## 目标目录结构

```
.trae/skills/bid-skeleton-extraction/
├── SKILL.md                          # Skill 定义（含完整流程 + 占位符规则 + 输出格式）
├── scripts/
│   ├── cli.py                        # CLI 入口（parse + template 子命令）
│   ├── extractor.py                  # 文件解析模块（复用）
│   └── inject_placeholders.py        # Word 模板生成（复用）
└── references/
    └── company-profile.json          # 公司风险规则库（供 LLM 骨架完善时参考）
```

## 实施步骤

### 步骤1：创建目录结构

```bash
mkdir -p .trae/skills/bid-skeleton-extraction/scripts
mkdir -p .trae/skills/bid-skeleton-extraction/references
```

### 步骤2：复制脚本文件

- `extractor.py`：从 `.trae/skills/bid-info-extraction/scripts/extractor.py` 复制
- `inject_placeholders.py`：从 `skills/extract-skeleton/scripts/inject_placeholders.py` 复制
- `company-profile.json`：从 `.trae/skills/bid-info-extraction/references/company-profile.json` 复制

### 步骤3：创建 CLI 入口

**文件**：`.trae/skills/bid-skeleton-extraction/scripts/cli.py`

两个子命令：
- `parse <file_path> [--output <path>]` — 调用 extractor.py 解析文件（与 bid-info-extraction 的 parse 相同）
- `template <skeleton.json 路径> [--output <path>]` — 调用 inject_placeholders.py 从 skeleton.json 生成 template.docx

### 步骤4：编写 SKILL.md

**核心内容**：

1. **frontmatter**：name + description（含触发场景）
2. **完整流程说明**：
   - 步骤 1：CLI parse 解析文件
   - 步骤 2：调用 `.trae/skills/bid-info-extraction/` 的 `cli.py parse` 获取 `plain_text`，然后 Agent 按 bid-info-extraction SKILL.md 中的 schema 提取关键信息
   - 步骤 3：LLM 骨架提取（从 `elements` 提取封面 + 章节 + 占位符）
   - 步骤 4：LLM 骨架完善（理解 skeleton.json + bid-extraction-result.json，添加资质/评分/技术章节，去重，生成 bid-writing-guide.json）
   - 步骤 5：CLI template 生成 Word
3. **骨架提取规则**（从现有 extract-skeleton SKILL.md 迁移）：
   - Boundary Rules（封面边界、章节边界）
   - Placeholder Priority Table（38 种占位符）
   - Execution Steps
   - Self-Check Checklist
4. **骨架完善指引**（原 enhance.py 的逻辑改为 LLM 指引）：
   - 根据资质要求添加章节
   - 根据评分标准添加章节
   - 根据技术需求添加响应点
   - 去重策略
   - bid-writing-guide.json 的完整 schema
5. **输出格式**：
   - skeleton.json 格式
   - bid-writing-guide.json 格式
6. **常见陷阱**

## 文件变更清单

| 序号 | 操作 | 文件路径 | 说明 |
|------|------|----------|------|
| 1 | 创建目录 | `.trae/skills/bid-skeleton-extraction/` | Skill 根目录 |
| 2 | 复制 | `extractor.py` → `.trae/skills/bid-skeleton-extraction/scripts/extractor.py` | 文件解析模块 |
| 3 | 复制 | `inject_placeholders.py` → `.trae/skills/bid-skeleton-extraction/scripts/inject_placeholders.py` | Word 模板生成 |
| 4 | 复制 | `company-profile.json` → `.trae/skills/bid-skeleton-extraction/references/company-profile.json` | 风险规则库 |
| 5 | 新建 | `.trae/skills/bid-skeleton-extraction/scripts/cli.py` | CLI 入口 |
| 6 | 新建 | `.trae/skills/bid-skeleton-extraction/SKILL.md` | Skill 定义 |

**不修改任何现有文件**。

## 关键设计决策

1. **骨架完善由 LLM 执行**：Agent 读取 `skeleton.json` + `bid-extraction-result.json`，理解语义后直接生成完善后的骨架，比规则脚本更灵活
2. **调用已有的 bid-info-extraction Skill**：步骤 2 通过 `.trae/skills/bid-info-extraction/scripts/cli.py` 的 `parse` 子命令获取 `plain_text`，然后 Agent 按其 SKILL.md 提取信息
3. **bid-writing-guide.json 由 LLM 在步骤 4 中一并生成**：不再依赖 enhance.py 的模板化输出
4. **CLI 只处理确定性工作**：parse（文件解析）和 template（Word 生成）

## 验证步骤

1. **结构验证**：确认 `.trae/skills/bid-skeleton-extraction/` 下所有文件存在
2. **CLI parse 验证**：
   ```bash
   python3 .trae/skills/bid-skeleton-extraction/scripts/cli.py parse inputs/XXXX营业部ABC软件单一来源采购文件-自采.docx | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'OK: {len(d[\"elements\"])} elements')"
   ```
3. **CLI template 验证**：
   ```bash
   python3 .trae/skills/bid-skeleton-extraction/scripts/cli.py template outputs/20260623_023953_XXXX营业部ABC软件/skeleton.json --output /tmp/test-template.docx
   ```
4. **SKILL.md 验证**：确认 frontmatter 格式正确，流程描述完整
