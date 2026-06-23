# 招标文件信息提取 Skill 拆分实施方案

## 摘要

将当前单一的 `bid-info-extraction` skill 拆分为两个独立的 skill：
1. **file-content-parser**：负责文档内容解析（PDF/Word/HTML/图片等格式转换为纯文本）
2. **bid-info-extraction**：负责招标文件关键信息提取（从纯文本中提取结构化信息并进行风险分析）

## 当前状态分析

### 当前 skill 结构
- **位置**：`/sessions/6a2e3de61930717937a0ba41/workspace/SKILL.md`
- **文档解析脚本**：`scripts/extractor.py`
- **输出模板**：`assets/report-template.html`
- **风险规则库**：`references/company-profile.json`
- **Agent 配置**：`agents/openai.yaml`

### 当前工作流程
```
输入文件 → extractor.py → 纯文本 → 分包识别 → 结构化提取 → 风险分析 → JSON + HTML
```

### 拆分可行性分析
1. **文档解析**：确定性文件 I/O 操作，不涉及 LLM 语义理解
2. **信息提取**：LLM 驱动的语义理解任务
3. **风险分析**：基于规则的数据处理

技术上完全可行，拆分后可实现关注点分离、独立复用、独立迭代。

## 拆分后架构设计

### Skill 1：`file-content-parser`（文档内容解析）
**职责**：将各种格式的文档文件转换为结构化的纯文本输出
- **输入**：文档文件路径
- **输出**：纯文本内容 + 文档元信息
- **特点**：纯确定性操作，可独立复用

### Skill 2：`bid-info-extraction`（招标文件关键信息提取）
**职责**：接收纯文本内容，进行招标文件分包识别、关键信息结构化提取、专属风险分析
- **输入**：纯文本内容（来自 file-content-parser 或直接提供）
- **输出**：结构化 JSON + HTML 报告
- **依赖**：`references/company-profile.json` 进行风险分析

### 拆分后数据流
```
输入文件 → [Skill 1: file-content-parser] → 纯文本 + 元信息
                                                    ↓
                          [Skill 2: bid-info-extraction] → JSON + HTML
```

## 目录结构

### 新目录结构
```
workspace/
├── skills/
│   ├── file-content-parser/          # Skill 1：文档内容解析
│   │   ├── SKILL.md                 # skill 定义文件
│   │   ├── SETUP.md                 # 环境与依赖说明
│   │   └── scripts/
│   │       └── extractor.py         # 从当前位置迁移（不修改）
│   │
│   └── bid-info-extraction/         # Skill 2：招标文件关键信息提取
│       ├── SKILL.md                 # skill 定义文件（精简版）
│       ├── SETUP.md                 # 环境说明（精简版）
│       ├── assets/
│       │   └── report-template.html # 从当前位置迁移（不修改）
│       ├── references/
│       │   └── company-profile.json # 从当前位置迁移（不修改）
│       └── agents/
│           └── openai.yaml          # 从当前位置迁移（更新接口描述）
├── outputs/                         # 保留，输出文件夹不变
├── inputs/                          # 保留，输入文件夹不变
├── SETUP.md                         # 可保留为顶层说明或删除
└── SKILL.md                         # 可保留为顶层编排说明或删除
```

## 详细实施方案

### 1. Skill 1：`file-content-parser` 设计

#### 1.1 SKILL.md 内容
```yaml
---
name: file-content-parser
description: Use when needing to extract plain text content from documents of various formats (PDF, Word .doc/.docx, HTML, images, TXT). Supports OCR for scanned documents. Outputs structured text with metadata.
---
```

文档内容应包含：
1. 简介：职责单一 - 将任意格式的文档文件转换为纯文本
2. 输入：文档文件路径（支持 PDF、Word、HTML、图片、TXT）
3. 输出：纯文本内容输出到 stdout，错误信息输出到 stderr
4. 使用方式：`python3 <skill_dir>/scripts/extractor.py <文件路径>`
5. 支持的文件格式表
6. OCR 处理说明
7. 注意事项

#### 1.2 scripts/extractor.py
与当前 `scripts/extractor.py` 完全相同，不需要修改。

#### 1.3 SETUP.md 内容
从当前 `SETUP.md` 中提取与文档解析相关的部分：
- Python 3 运行环境
- Python 包依赖（pymupdf、python-docx、html2text）
- 系统工具（Tesseract OCR、LibreOffice、textutil、file 命令）
- 各平台安装指南
- 快速验证脚本

### 2. Skill 2：`bid-info-extraction` 设计

#### 2.1 SKILL.md 内容
```yaml
---
name: bid-info-extraction
description: Use when needing to extract structured key information from Chinese bidding/tender document text content, including bid-submission-critical data and company-specific risk warnings. Accepts plain text input (typically from file-content-parser). Outputs JSON schema + HTML report.
---
```

文档内容应包含：
1. 简介：从已解析的纯文本中提取招标文件关键信息
2. 输入：
   - 招标文件的纯文本内容（从 `file-content-parser` 获取，或用户直接提供）
   - 可选：原始文件名（用于输出文件命名和元数据记录）
   - 可选：原始文件路径（如需重新解析时使用）
3. 前置依赖：明确说明需要纯文本输入，如用户提供文件需先调用 `file-content-parser`
4. 阶段0：分包识别（从当前 SKILL.md 原样迁移）
5. 阶段1：招标关键信息提取（从当前 SKILL.md 原样迁移，含 JSON Schema 定义）
6. 阶段2：专属风险分析（从当前 SKILL.md 原样迁移，含匹配流程、R012 交叉比对、公司政策底线）
7. 输出生成（从当前 SKILL.md 原样迁移）
8. 输出文件夹命名规则（从当前 SKILL.md 原样迁移）
9. 注意事项和常见陷阱（从当前 SKILL.md 原样迁移）

关键修改点：将"文件读取流程"一节替换为对接 `file-content-parser` 的说明。

#### 2.2 其他文件
- **assets/report-template.html**：与当前文件完全相同，不修改
- **references/company-profile.json**：与当前文件完全相同，不修改
- **agents/openai.yaml**：更新接口描述以反映新的输入方式
- **SETUP.md**：精简版环境说明，只包含 HTML 报告生成相关依赖

### 3. 依赖关系处理

#### 3.1 Skill 间调用关系
推荐方案：由编排层协调
- 在顶层或用户的使用流程中，先调用 `file-content-parser`，再将其输出传给 `bid-info-extraction`
- 两个 skill 本身互不感知，各自独立
- 优点：解耦彻底，每个 skill 可独立测试、独立复用

#### 3.2 文件引用路径更新
- 所有 `<skill_dir>/scripts/extractor.py` 引用更新为 `<file-content-parser_dir>/scripts/extractor.py`
- `bid-info-extraction` 中对 `references/company-profile.json` 和 `assets/report-template.html` 的引用路径更新为相对于新 skill 目录的路径

#### 3.3 输出目录
- `outputs/` 目录保持在 workspace 根级别
- `file-content-parser` 通常不产生持久化输出文件（输出到 stdout）
- `bid-info-extraction` 的 JSON + HTML 输出写入 `outputs/` 的子文件夹

## 文件清单

| 序号 | 操作 | 文件路径 | 说明 |
|------|------|----------|------|
| 1 | 创建目录 | `skills/file-content-parser/` | Skill 1 根目录 |
| 2 | 创建目录 | `skills/file-content-parser/scripts/` | 脚本目录 |
| 3 | 创建目录 | `skills/bid-info-extraction/` | Skill 2 根目录 |
| 4 | 创建目录 | `skills/bid-info-extraction/assets/` | 资源目录 |
| 5 | 创建目录 | `skills/bid-info-extraction/references/` | 参考资料目录 |
| 6 | 创建目录 | `skills/bid-info-extraction/agents/` | Agent 配置目录 |
| 7 | 创建 | `skills/file-content-parser/SKILL.md` | Skill 1 定义文件（新编写） |
| 8 | 创建 | `skills/file-content-parser/SETUP.md` | Skill 1 环境说明（从原 SETUP.md 提取） |
| 9 | 迁移 | `scripts/extractor.py` -> `skills/file-content-parser/scripts/extractor.py` | 不修改 |
| 10 | 创建 | `skills/bid-info-extraction/SKILL.md` | Skill 2 定义文件（从原 SKILL.md 改写） |
| 11 | 创建 | `skills/bid-info-extraction/SETUP.md` | Skill 2 环境说明（精简版） |
| 12 | 迁移 | `assets/report-template.html` -> `skills/bid-info-extraction/assets/report-template.html` | 不修改 |
| 13 | 迁移 | `references/company-profile.json` -> `skills/bid-info-extraction/references/company-profile.json` | 不修改 |
| 14 | 迁移 | `agents/openai.yaml` -> `skills/bid-info-extraction/agents/openai.yaml` | 更新接口描述 |

## 验证步骤

### 1. 结构验证
```bash
# 验证目录结构是否完整
ls -la skills/file-content-parser/
ls -la skills/file-content-parser/scripts/
ls -la skills/bid-info-extraction/
ls -la skills/bid-info-extraction/assets/
ls -la skills/bid-info-extraction/references/
ls -la skills/bid-info-extraction/agents/

# 验证关键文件存在
test -f skills/file-content-parser/SKILL.md && echo "OK" || echo "MISSING"
test -f skills/file-content-parser/scripts/extractor.py && echo "OK" || echo "MISSING"
test -f skills/bid-info-extraction/SKILL.md && echo "OK" || echo "MISSING"
test -f skills/bid-info-extraction/assets/report-template.html && echo "OK" || echo "MISSING"
test -f skills/bid-info-extraction/references/company-profile.json && echo "OK" || echo "MISSING"
```

### 2. 功能验证 - file-content-parser
```bash
# 用已有招标文件测试（如果 inputs/ 中有招标文件）
python3 skills/file-content-parser/scripts/extractor.py inputs/招标文件.docx > /tmp/test-output.txt
# 检查输出是否为有意义的纯文本
wc -l /tmp/test-output.txt
head -20 /tmp/test-output.txt
```

### 3. 功能验证 - bid-info-extraction
```bash
# 比较迁移的文件是否完全一致
diff references/company-profile.json skills/bid-info-extraction/references/company-profile.json
diff assets/report-template.html skills/bid-info-extraction/assets/report-template.html
```

### 4. 端到端验证
```bash
# 步骤1：使用 file-content-parser 解析文档
python3 skills/file-content-parser/scripts/extractor.py inputs/招标文件.docx > /tmp/bid-text.txt

# 步骤2：检查纯文本内容可用于后续提取
# （这一步需要 LLM 介入，手动验证或在 agent 中测试）
# 验证点：纯文本包含完整内容、分包信息可识别、关键时间节点可提取
```

### 5. SKILL.md 内容验证
- **bid-info-extraction/SKILL.md**：
  1. 不包含对 `extractor.py` 的直接调用指令
  2. 包含完整的 JSON Schema 定义
  3. 包含完整的阶段0/1/2 流程描述
  4. 包含完整的风险规则匹配逻辑
  5. 输出文件夹命名规则完整保留
  6. frontmatter 中的 `description` 字段已更新

- **file-content-parser/SKILL.md**：
  1. frontmatter 中的 `name` 和 `description` 准确描述文档解析职责
  2. 包含完整的文件格式支持表
  3. 包含 OCR 相关说明
  4. 不包含任何招标信息提取相关内容

## 风险与注意事项

1. **提取脚本中的相对路径**：当前 `extractor.py` 不包含任何对其他文件的相对路径引用，迁移后无需修改。

2. **report-template.html 中的硬编码数据**：模板中 `window.__BID_DATA__` 包含示例数据，拆分后保留不影响功能。

3. **outputs 目录中的已有输出**：历史输出目录保留，拆分不影响。

4. **顶层文件的处理**：建议将原 `workspace/SKILL.md` 改为顶层编排说明文件；原 `workspace/SETUP.md` 的内容已分别拆入两个 skill，可删除或保留。

5. **inputs/ 目录**：保持在 workspace 根级别不变，两个 skill 共享同一输入目录。

6. **agent 配置的隐式调用**：拆分后，`file-content-parser` 应在用户提到"解析文件"、"提取文本"等场景时被隐式调用；`bid-info-extraction` 应在用户提到"招标信息提取"、"风险分析"等场景时被隐式调用。

## 实施步骤建议

按以下顺序执行，每完成一步后进行验证：

1. 创建 `skills/` 目录及子目录结构
2. 将 `scripts/extractor.py` 复制到 `skills/file-content-parser/scripts/`
3. 编写 `skills/file-content-parser/SKILL.md`
4. 编写 `skills/file-content-parser/SETUP.md`（从原 SETUP.md 提取文档解析部分）
5. 将 `assets/report-template.html` 复制到 `skills/bid-info-extraction/assets/`
6. 将 `references/company-profile.json` 复制到 `skills/bid-info-extraction/references/`
7. 将 `agents/openai.yaml` 复制到 `skills/bid-info-extraction/agents/` 并更新描述
8. 编写 `skills/bid-info-extraction/SKILL.md`（从原 SKILL.md 改写，去掉文档解析部分，增加对 file-content-parser 的引用）
9. 编写 `skills/bid-info-extraction/SETUP.md`（精简版）
10. 将原 `workspace/SKILL.md` 改写为顶层编排说明（或删除）
11. 清理或归档原位置的文件（`scripts/`、`assets/`、`references/`）
12. 执行全部验证步骤

## 总结

此次拆分的核心思路是将"确定性的文件 I/O 操作"与"LLM 驱动的语义理解任务"分离。`file-content-parser` 负责把各种格式的文件变成纯文本，`bid-info-extraction` 负责从纯文本中挖掘招标信息并进行风险分析。两者通过"纯文本"这一中间产物连接，各自独立、各自可复用。