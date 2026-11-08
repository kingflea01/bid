# 标书编写平台开发设计文档

## 1. 文档目的与建设结论

### 1.1 文档目的

本文档用于指导“标书编写平台”首版的产品设计、技术实现、测试验收和部署。目标是让后续开发人员在不再补充产品决策的情况下，能够按本文档完成一个可运行的全流程平台。

### 1.2 建设结论

平台覆盖以下完整流程：

1. 企业、产品、知识素材、红线条款、标书模板的结构化配置；
2. 招标项目创建与招标文件上传；
3. 招标文件的确定性解析、索引和章节骨架生成；
4. 在少数环节调用 AI，完成关键信息提取、风险与策略分析，以及可选的编排歧义处理；
5. 以“章节树 + 候选版本 + 当前选择”为核心，生成卡片式初稿；
6. 用户完成版本选择、章节结构调整、内容补充、附件补齐和逐章确认；
7. 通过确定性质量门禁后，导出审阅版或正式版标书；
8. 保存不可变项目快照，为后续续约项目提供历史章节候选版本。

首版的核心原则是：

> 确定性工作流负责主线，AI 只负责招标语义理解和风险分析，人负责所有配置质量、版本选择、内容修改、风险处置和最终确认。

### 1.3 首版明确不做

- 不做知识库、红线、模板内容的 AI 自动整理、自动发布或质量判断；
- 不做扫描件 OCR；图片型 PDF、图片型表格和扫描模板只标记待人工处理；
- 不做 AI 自动写作技术或商务正文；
- 不做逐章节、逐段落的 AI 素材满足度判断；
- 不做编辑问答、自然语言修改标书、修改后的 AI 语义复核；
- 不做 AI 最终审阅、AI 导出或 AI 自动资产入库；
- 不做报价推荐、价格分测算或中标概率预测；
- 不做多 Agent 自主协作和模型自主多轮修正；
- 不做 Office 在线文档编辑和多人同时编辑同一文本块；
- 不将模型直接连接到数据库、知识库或素材库。

---

## 2. 当前状态与可复用基础

### 2.1 当前工作区状态

当前工作区没有生产级前后端工程、数据库、接口、权限体系或部署配置，只有一个单文件交互原型：

- `/workspace/bid-review-prototype.html`

该原型使用原生 HTML、CSS 和 JavaScript，实现了：

- 三栏章节工作区；
- 章节树、锁定章节、同级拖拽和层级调整；
- 卡片式初稿；
- 候选版本、差异对比、版本切换和确认状态；
- 条款原文弹窗、缺口处理、快照和导出门禁。

原型中的 `state.sections`、`allSections`、`getCurrentVersion`、`openDiff`、`applyVersion`、`openExport` 等仅用于交互演示。生产实现应将状态迁移到后端持久化模型，前端改为受控组件，不能继续以单个 HTML 文件作为系统主体。

### 2.2 shoot1 的可复用实现

用户提供的归档文件：

- `/workspace/.uploads/787e93ec-017a-4568-ad50-ba78b99140d2_shoot1.zip`

其中 `shoot1/tender-bid-analyzer` 已验证以下能力：

- `scripts/core/extract_docx.py`：DOCX 文本与表格提取；
- `scripts/core/outline.py`：结合编号、样式、粗体和字号识别招标章节；
- `scripts/core/extract.py`：生成 `tender.json` 和全文索引；
- `scripts/core/structure.py`：招标章节与用户模板合并；
- `scripts/core/validate_tables.py`：预算、日期、分包和异常字段检查；
- `scripts/builder/build.py`：Word 组装、占位符清单和输出校验；
- `scripts/builder/clean.py`：模板说明清理、字段替换和附件占位符；
- `scripts/builder/clone.py`：OOXML 块克隆；
- `references/extraction-schema.md`：15 类招标信息提取框架；
- `references/redline-rules.md`：红线冲突类型、等级和建议动作；
- `references/scoring-rules.md`：非价格评分证据和区间测算规则；
- `references/bid-generation.md`：确定性生成、最多三次模型调用、缓存和速度架构。

shoot1 的关键经验必须保留：

1. 解析、结构合并、克隆、填充、组装和校验由脚本完成；
2. 模型调用不处于骨架生成的关键路径；
3. 标书构建不读取自然语言分析报告；
4. 无内容的章节使用显式占位符，不让模型猜测；
5. 复杂表格深拷贝 OOXML，不重新绘制；
6. 提取与结构缓存按文件、分包和模板版本复用。

### 2.3 需要新建的平台能力

- 多用户、项目权限和配置发布；
- 结构化资产配置及不可变版本；
- 数据库持久化的章节树和候选版本；
- 文本 PDF 解析与统一原文锚点；
- 后端 AI 网关、任务状态、结果校验和缓存；
- 卡片工作区的服务端状态与并发控制；
- 历史项目快照与续约复用；
- 正式导出门禁、审计、备份和容器化部署。

---

## 3. 范围、角色与业务规则

### 3.1 用户角色

| 角色 | 权限 |
|---|---|
| 系统管理员 | 用户、角色、系统参数、模型接口和存储配置 |
| 配置管理员 | 企业、产品、素材、红线、模板的新增、修改、提交和发布 |
| 标书编辑 | 创建项目、上传文件、确认解析、选择版本、编辑章节、处理缺口、保存快照 |
| 审阅人 | 查看原文与分析、复核风险、确认章节、确认风险处置、批准正式导出 |
| 只读用户 | 查看被授权项目及其审阅版，不得修改或导出正式版 |

项目权限采用“全局角色 + 项目成员角色”双重判断。所有项目、文件、快照和导出接口都校验项目成员关系，防止通过修改 ID 越权访问。

### 3.2 配置发布规则

- 企业、产品、素材、红线和模板均具有草稿、已发布、已归档状态；
- 只有已发布版本可以用于新项目；
- 已发布版本不可直接修改，修改时创建新修订；
- 老项目始终保留创建时使用的配置版本，不受后续发布影响；
- 配置内容质量由录入人和发布人负责，首版不使用 AI 审核；
- 企业级与产品级红线同时生效，冲突时采用更严格的立场；
- 资质、证书、人员、案例和 SLA 等素材必须支持有效期、责任人和适用范围。

### 3.3 标书内容规则

- 招标明确规定的章节名称、顺序、层级和格式模板优先；
- 招标固定章节禁止随意调整结构和正文格式；
- 企业补充章节可以在允许范围内排序、升级或降级；
- 正文块必须来自招标模板、已发布素材、历史项目确认版本或用户显式编辑；
- AI 输出不得直接成为标书正文；
- 资质编号、业绩金额、人员、服务期、质保期等统一使用事实字段；
- 未知信息保留占位符，不以“未找到”推断“不具备”；
- 切换版本或修改事实字段后，相关章节必须重新确认；
- 正式导出必须来自一个人工确认的项目快照。

---

## 4. 总体技术架构

### 4.1 技术选型

| 层次 | 首版选型 | 选择原因 |
|---|---|---|
| 前端 | React、TypeScript、Vite、Ant Design、TanStack Query、Zustand、dnd-kit | 适合企业后台和三栏工作区，支持章节拖拽与受控状态 |
| 章节正文编辑 | 受限结构化 Block Editor；必要时使用 TipTap 的受限扩展 | 避免任意 HTML 往返破坏 OOXML，统一事实字段和导出块模型 |
| 后端 | Python 3.12、FastAPI、Pydantic、SQLAlchemy 2、Alembic | 与 shoot1 的 DOCX/OOXML 技术栈一致 |
| 数据库 | PostgreSQL 16，使用 JSONB 保存内容块与快照 | 兼顾事务、章节关系和不可变内容版本 |
| 文件存储 | 部署机持久化目录，文件按 SHA-256 寻址 | 首版单组织私有部署，避免引入额外对象存储服务 |
| 后台任务 | Redis + RQ Worker | AI 分析、PDF 解析和导出不能阻塞 Web 请求 |
| DOCX | python-docx + lxml，必要时直接处理 OOXML | 复用 shoot1 能力并保留复杂表格结构 |
| 文本 PDF | PyMuPDF 为主，pdfplumber 用于指定章节的表格辅助提取 | 支持页码、坐标和文本块锚点，不做 OCR |
| AI 接口 | 后端可配置的 OpenAI 兼容 Chat Completions 接口 | 可接公司批准的外部服务或内网兼容模型 |
| 导出 | DOCX 由 OOXML 构建；PDF 由独立 Worker 调用 LibreOffice Headless | LibreOffice 不参与快速骨架主链路 |
| 部署 | Docker Compose：web、api、worker、postgres、redis | 适合首版公司内网单节点部署 |

### 4.2 运行结构

```text
浏览器 React 应用
  │ HTTPS / HttpOnly Session
  ▼
FastAPI 后端
  ├── 权限、配置、项目、章节、风险、快照接口
  ├── DOCX / PDF 确定性解析
  ├── 章节合并、候选排序、QA、导出准备
  ├── PostgreSQL：业务数据、内容版本、快照、AI 结果
  ├── 文件目录：招标原件、附件、导出文件
  └── Redis / RQ：后台任务
          ├── AI 提取任务
          ├── AI 风险任务
          ├── 可选 AI 编排歧义任务
          ├── PDF 解析任务
          └── DOCX / PDF 导出任务

FastAPI / Worker
  └── 可配置 AI 网关 → 公司批准的外部模型或内网兼容模型
```

### 4.3 两条并行链路

**快速骨架链路：**

上传文件 → 计算哈希 → 解析与索引 → 章节合并 → 固定内容/占位符 → 卡片工作区。

**AI 分析链路：**

解析索引 → AI 关键信息提取 → 结构化校验 → AI 风险与策略分析 → 结果写回项目 → 网页显示状态变化。

快速骨架不读取风险报告，也不等待 AI 完成。AI 失败时，用户仍能处理章节、素材、附件和导出审阅版。

---

## 5. 建议工程结构

首版新建以下工程，不修改现有原型文件，原型继续作为交互参考。

```text
/workspace/
  bid-platform/
    docker-compose.yml
    .env.example
    README.md
    backend/
      pyproject.toml
      alembic.ini
      app/
        main.py
        core/
          config.py
          database.py
          security.py
          permissions.py
          errors.py
        models/
          user.py
          config.py
          asset.py
          project.py
          tender.py
          section.py
          risk.py
          task.py
        schemas/
          config.py
          asset.py
          project.py
          section.py
          analysis.py
          export.py
        api/
          deps.py
          routes/
            auth.py
            users.py
            companies.py
            products.py
            redlines.py
            assets.py
            templates.py
            projects.py
            tender_documents.py
            analysis.py
            sections.py
            candidates.py
            gaps.py
            risks.py
            snapshots.py
            exports.py
        services/
          files/store.py
          documents/docx_parser.py
          documents/pdf_parser.py
          documents/indexer.py
          documents/anchors.py
          structure/merge.py
          structure/rules.py
          structure/cleanup.py
          assets/repository.py
          assets/ranking.py
          workspace/tree.py
          workspace/versions.py
          workspace/facts.py
          workspace/diff.py
          workspace/qa.py
          export/docx_builder.py
          export/ooxml.py
          export/pdf_builder.py
          ai/gateway.py
          ai/schemas.py
          ai/tasks.py
          ai/cache.py
          ai/prompts/extract.txt
          ai/prompts/risk.txt
          ai/prompts/mapping.txt
        workers/tasks.py
      alembic/versions/0001_initial.py
      tests/
        unit/
        integration/
        contract/
        fixtures/
    frontend/
      package.json
      vite.config.ts
      src/
        main.tsx
        app/router.tsx
        app/api.ts
        app/auth.tsx
        pages/LoginPage.tsx
        pages/ProjectListPage.tsx
        pages/ProjectCreatePage.tsx
        pages/AnalysisPage.tsx
        pages/WorkspacePage.tsx
        pages/ExportCenterPage.tsx
        pages/config/CompaniesPage.tsx
        pages/config/ProductsPage.tsx
        pages/config/AssetsPage.tsx
        pages/config/RedlinesPage.tsx
        pages/config/TemplatesPage.tsx
        components/workspace/ChapterTree.tsx
        components/workspace/ChapterCardList.tsx
        components/workspace/ChapterCard.tsx
        components/workspace/BlockEditor.tsx
        components/workspace/FactToken.tsx
        components/workspace/VersionInspector.tsx
        components/workspace/CandidateList.tsx
        components/workspace/RequirementList.tsx
        components/workspace/DiffDialog.tsx
        components/workspace/SourceDialog.tsx
        components/workspace/GapList.tsx
        components/workspace/ExportDialog.tsx
        stores/workspaceStore.ts
        types/project.ts
    fixtures/
      README.md
```

### 5.1 shoot1 代码迁移方式

- 将上述可复用模块的算法迁入 `backend/app/services`，不要从 ZIP 路径动态加载；
- 保留纯函数和确定性测试，移除对本地工作区目录的依赖；
- 将 `run.py` 中的流程改造成应用服务和 RQ 任务，不保留生产 CLI 作为依赖；
- 将 Markdown 配置解析替换为数据库配置；仅保留一个开发期导入工具，用于迁移 shoot1 模板；
- 将 `build_bid` 的文件读写改为项目快照、文件存储和导出任务；
- 统一 shoot1 中关于真实公司信息输出的冲突口径，以平台数据权限策略为准。

---

## 6. 核心数据模型

### 6.1 用户与项目

| 表 | 关键字段 | 说明 |
|---|---|---|
| users | id、username、password_hash、display_name、global_role、active | 本地账号，密码使用 Argon2 |
| sessions | id、user_id、expires_at、created_at | 服务端会话，浏览器只保存不透明 HttpOnly Cookie |
| projects | id、name、code、customer_name、procurement_type、status、owner_id、version、created_at | version 用于乐观锁 |
| project_members | project_id、user_id、project_role | 项目级权限 |
| project_config_refs | project_id、company_revision_id、product_revision_id、template_revision_id、created_at | 固定项目配置基线 |

### 6.2 企业与产品配置

| 表 | 关键字段 | 说明 |
|---|---|---|
| companies | id、code、name、status | 稳定企业身份 |
| company_revisions | id、company_id、revision_no、fields_json、status、published_by | 工商、资质、联系人和统一事实字段 |
| products | id、code、name、status | 稳定产品身份 |
| product_revisions | id、product_id、revision_no、fields_json、technical_fields_json、status | 参数、部署、服务和证明材料 |
| redline_rules | id、scope_type、scope_id、category、position、condition_json、action、legal_review、revision_no、status | 企业级或产品级红线 |
| templates | id、name、project_type、status | 标书模板身份 |
| template_revisions | id、template_id、revision_no、nodes_json、status、published_by | 固定章节树、锁定策略和默认内容规则 |

### 6.3 素材与版本

素材模型必须区分“候选方案”和“修订版本”。

| 表 | 关键字段 | 说明 |
|---|---|---|
| assets | id、code、title、asset_type、scope、industry、product_id、customer_name、owner_id、valid_from、valid_to、status | 稳定素材身份与过滤元数据 |
| asset_variants | id、asset_id、code、name、description、status | 标准方案、驻场方案、客户专属方案等不同内容路线 |
| asset_revisions | id、variant_id、revision_no、content_json、source_format、status、created_by、published_by、created_at | 不可变内容修订，发布后不可原地修改 |
| asset_attachments | id、asset_id、file_id、attachment_type、valid_to、metadata_json | 扫描件、证书、合同证明等 |
| files | id、sha256、path、mime_type、size、original_name、uploaded_by | 文件按哈希去重，数据库不保存大二进制 |

`content_json` 只支持有限块类型：

- `paragraph`：普通段落；
- `heading`：内容内部标题；
- `list`：有序或无序列表；
- `table`：结构化表格；
- `fact_ref`：统一事实字段引用；
- `attachment_ref`：附件引用；
- `placeholder`：字段、附件或内容缺口；
- `tender_ooxml_ref`：招标原始 OOXML 块引用。

不允许直接保存任意可执行 HTML、脚本或外部资源引用。

### 6.4 招标文件与原文锚点

| 表 | 关键字段 | 说明 |
|---|---|---|
| tender_documents | id、project_id、file_id、document_type、sha256、status、page_count、parser_version、created_at | 招标原件及解析状态 |
| tender_blocks | id、document_id、anchor_key、block_type、order_no、page_no、paragraph_index、bbox_json、text、ooxml_path、style_json | 统一 DOCX/PDF 原文定位 |
| tender_outlines | id、document_id、parent_id、position、title、level、source_start_anchor、source_end_anchor、recognition_confidence | 招标目录树和格式章节 |
| requirements | id、document_id、code、category、response_type、text、normalized_json、mandatory_level、score_max、status、confidence | AI 提取后经确认的结构化要求 |
| requirement_anchors | requirement_id、anchor_key、quote | 每条要求必须能回到原文 |

`anchor_key` 是稳定内部标识。DOCX 使用段落/表格索引和 OOXML 路径，PDF 使用页码、块序号和坐标。页面显示原文时以锚点读取，不依赖模型生成页码。

### 6.5 项目章节与候选版本

| 表 | 关键字段 | 说明 |
|---|---|---|
| project_sections | id、project_id、parent_id、position、title、section_key、source_type、locked、content_mode、selected_revision_id、content_status、review_status、version | 稳定章节槽位 |
| project_section_revisions | id、section_id、revision_no、content_json、source_type、source_asset_revision_id、source_history_revision_id、created_by、created_at | 项目内的不可变内容版本 |
| section_candidates | id、section_id、candidate_type、candidate_id、rank_score、rank_reasons_json、status | 确定性候选排序及解释 |
| section_requirements | section_id、requirement_id、mapping_source、mapping_status、confirmed_by | 条款与章节的关联 |
| section_dependencies | section_id、depends_on_section_id、dependency_type、fact_keys_json | 版本切换和事实变化的影响范围 |
| project_facts | id、project_id、fact_key、value_json、value_type、source_type、source_id、status、confirmed_by | 跨章节统一事实 |
| gaps | id、project_id、section_id、requirement_id、gap_type、title、blocking、status、resolved_by、resolution_json | 缺口及实际解决依据 |
| project_snapshots | id、project_id、snapshot_no、tree_json、selected_revisions_json、facts_json、risk_states_json、created_by、created_at | 不可变完整项目状态 |

章节采用两个独立状态，避免“Word 生成成功”被误认为“内容已完成”：

- `content_status`：`empty / ready / gap`；
- `review_status`：`unconfirmed / confirmed / needs_review`。

界面组合显示为：待补内容、待确认、已确认、待复核。分组章节的状态由后代汇总，不直接承载正文。

### 6.6 风险、任务与审计

| 表 | 关键字段 | 说明 |
|---|---|---|
| risks | id、project_id、requirement_id、redline_rule_id、category、conflict_type、severity、recommendation、legal_review、disposition、disposed_by、disposition_note | AI 建议与人工处置分离 |
| score_assessments | id、project_id、requirement_id、score_min、score_max、evidence_json、gap_json、status | 非价格分区间，不输出中标概率 |
| ai_runs | id、project_id、task_type、input_hash、prompt_version、model、status、attempts、input_manifest_json、output_json、error_code、token_usage、started_at、finished_at | AI 调用审计与缓存 |
| export_tasks | id、project_id、snapshot_id、export_kind、format、status、qa_json、file_id、error_code、created_by | 审阅版/正式版导出 |
| activities | id、project_id、actor_id、action、entity_type、entity_id、detail_json、created_at | 配置、结构、版本、确认和导出审计 |

---

## 7. 确定性文档解析与骨架生成

### 7.1 DOCX 处理

1. 校验扩展名、MIME、大小、ZIP 完整性和可解析性；
2. 计算 SHA-256，相同文件复用解析结果；
3. 使用 python-docx 提取段落、样式、表格和编号；
4. 使用 shoot1 的编号、粗体、字号和目录过滤规则识别章节；
5. 识别响应文件格式章节及其 OOXML 起止位置；
6. 生成 `tender_documents`、`tender_blocks`、`tender_outlines`；
7. 运行预算合计、日期顺序、分包号、包名和空白字段检查；
8. 记录低置信度标题和无法识别的块，不擅自补写。

### 7.2 文本 PDF 处理

1. 使用 PyMuPDF 逐页提取文本块、页码和坐标；
2. 根据字体信息、编号和文本模式重建目录；
3. 仅在评分办法、响应格式等必要章节使用 pdfplumber 辅助提取表格；
4. 保存页码和 bbox 作为原文锚点；
5. 无文本页标记为 `scanned_page`，不调用 OCR；
6. PDF 中的复杂格式模板若无法可靠恢复，生成“按招标附件格式填写”的占位符，不伪造 Word 表格；
7. PDF 解析结果必须经过用户确认，确认前不进入正式导出。

### 7.3 章节合并规则

按 shoot1 已验证顺序执行：

1. 招标章节名称、顺序和层级优先；
2. 招标没有子项时挂载用户模板同义子树；
3. 招标提供格式模板时，以招标模板为准，用户同名内容作为补充；
4. 用户独有章节追加到同层末尾；
5. 招标明确不要求的章节省略；
6. 按招标用词统一“响应/投标”“成交/中标”；
7. 同义词、亲和规则和模板清洗规则版本化；
8. 只有规则无法处理的少量节点才进入可选 AI 编排任务。

### 7.4 占位符与骨架

- 无内容章节生成 `[[待编写：章节名]]`；
- 缺失附件生成 `[[附件：名称]]`；
- 未知字段生成 `[[字段名]]`；
- 图片模板生成 `[[按招标文件格式填写：名称]]`；
- 占位符同时生成 Gap，不仅显示在正文中；
- 骨架生成后即可进入卡片工作区，无需等待 AI。

---

## 8. AI 接入设计

### 8.1 接入边界

AI 仅由后端 `ai/tasks.py` 调用，浏览器不得直接接触模型地址或密钥。

环境配置：

- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_TIMEOUT_SECONDS`
- `AI_ENABLED`

`AI_API_KEY` 只通过部署环境或密钥管理注入，不写入数据库、前端包或日志。模型只能访问本次任务由后端组装的文本和字段，不能自主查询平台数据库。

### 8.2 调用预算

- 常规项目两次：关键信息提取、风险与策略分析；
- 仅存在规则无法处理的编排歧义时增加第三次；
- 不按章节调用，不进行多 Agent 对话；
- 网络超时或模型 5xx 最多进行一次相同请求重试；
- 输出 Schema 校验失败不做语义重试，标记 `needs_review`；
- AI 失败不阻塞骨架、编辑、快照和审阅版导出。

### 8.3 任务一：关键信息提取

**输入：**

- 目标分包文本及必要通用章节；
- 文档索引和真实 `anchor_key`；
- 采购方式分支；
- 固定提取 Schema 和版本号。

**输出：**15 类信息，沿用 shoot1 框架：项目、费用、分包、时间、资格、评分、实质性条款、技术、商务、合同、响应格式、无效情形、授予程序、附件、异常。

每个结果必须包含：

- 固定类别和响应处理类型；
- 原文 `quote`；
- 已存在的 `anchor_key` 列表；
- `original / inferred / missing / needs_review` 状态；
- 置信度；
- 强制性、分值等明确结构化字段。

后端校验：JSON Schema、类别枚举、锚点存在性、目标分包范围和数值格式。校验失败不进入正式 Requirement。

### 8.4 任务二：风险与策略分析

**输入：**

- 经 Schema 校验的提取结果；
- 企业与产品的已发布红线；
- 确定性 QA 结果；
- 企业与产品的必要非敏感字段。

**输出：**

- 风险类别、冲突类型、等级、建议动作和法务复核标记；
- 非价格评分项证据、可得分区间或“无法测算”；
- Go/No-Go 建议、前置条件、可争取项、不可让步项和待澄清问题；
- 所有判断关联 Requirement 或原文锚点。

人工风险处置与 AI 建议分开保存。AI 不得自行将风险标记为已接受或已解决。

### 8.5 可选任务三：编排歧义处理

**输入仅限：**未解决节点、允许的候选父节点、候选清洗动作和规则上下文。

**输出仅限：**

- `source_node_id`；
- `map / append / omit / clean / needs_review`；
- 允许的 `target_node_id`；
- 置信度和理由。

不得输出正文、公司事实或新的章节内容。后端拒绝不在允许集合中的节点 ID。

### 8.6 缓存与审计

结构缓存键：文件哈希 + 分包 + 模板版本 + 解析器版本。

AI 缓存键：文件哈希 + 分包 + Schema 版本 + 企业版本 + 产品版本 + 红线版本 + Prompt 版本 + 模型名。

默认日志不记录完整招标文本，只记录输入清单、哈希、模型、耗时、Token、结果状态和错误码。AI 原始输出保存在受项目权限保护的 `ai_runs.output_json` 中。

---

## 9. 候选素材与历史续约复用

### 9.1 候选来源

- 企业通用已发布素材；
- 行业或产品线已发布素材；
- 同客户专属素材；
- 同客户历史项目最终确认章节；
- 当前项目中的人工修订版本。

### 9.2 无 AI 的推荐排序

先按固定字段过滤：项目类型、行业、产品、客户、素材类型、有效期、密级和发布状态。

再按可解释规则排序：

1. 同客户且同产品的历史最终版本；
2. 同客户已发布专属素材；
3. 同产品、同行业的当前有效版本；
4. 企业通用当前有效版本；
5. 最近发布且使用范围匹配的版本。

排序分只表示“推荐顺序”，不得显示为“条款满足率”。条款覆盖状态只来自明确的章节条款关联和人工确认，不根据向量相似度虚构百分比。

### 9.3 续约项目

创建项目时可选择 `source_project_id`：

1. 新招标文件仍独立解析并生成新章节槽位；
2. 根据客户、产品、章节 `section_key`、模板节点和同义规则匹配历史最终章节；
3. 历史最终内容作为候选，不自动覆盖当前版本；
4. 沿用后状态为待确认，历史日期、人员、服务期和附件重新校验；
5. 原历史项目快照保持不可变。

---

## 10. 卡片式工作区与编辑规则

### 10.1 页面组成

**左侧：章节树**

- 搜索、展开、状态过滤；
- 锁定图标和可拖拽标识；
- 同级拖拽、自动编号；
- 评分项与缺口入口。

**中间：章节卡片流**

- 当前内容版本、来源、状态和占位符；
- 展开/收起、正文编辑、附件处理；
- 候选版本和关联条款入口；
- 切换后内容差异和关联影响提示。

**右侧：章节检查器**

- 候选版本、来源、推荐理由和有效期；
- 版本差异对比；
- 条款及原文锚点；
- 缺口、风险和审阅记录；
- 当前版本确认按钮。

### 10.2 结构调整

- 服务端在事务中校验 `parent_id`、`position` 和项目版本；
- 锁定章节不可移动，不可挂到锁定章节下改变其招标结构；
- 企业补充章节只能在允许的模板子树内调整；
- 移动后重新计算显示编号，不改变 `section_id`；
- 章节引用使用 ID，导出时生成编号，正文不得写死“第 X 章”。

### 10.3 版本切换

1. 用户查看当前与候选版本的结构化 Diff；
2. 确认后，将候选内容复制为新的 `project_section_revision`，保留来源血缘；
3. 更新 `selected_revision_id`；
4. 当前章节变为 `unconfirmed`；
5. 根据 `section_dependencies` 和事实引用，将关联章节标记为 `needs_review`；
6. 不自动改写其他章节；
7. 保存审计记录。

### 10.4 人工编辑

- 每次保存创建新修订，不覆盖旧修订；
- 编辑器只允许受支持的块和有限格式；
- 事实字段通过 `fact_ref` 插入，不能在同一项目中维护多个副本；
- 修改事实字段后，引用该字段的章节全部标记待复核；
- 缺口关闭必须上传附件、选择素材或填写实际解决依据，不能只点击按钮改变状态；
- 自动保存采用短防抖和乐观锁，冲突时提示用户比较，不静默覆盖他人修改。

### 10.5 快照

快照保存：章节树、每个章节的当前修订、事实字段、风险处置、缺口状态和配置基线。导出期间即使继续编辑，也不影响正在生成的文件。

---

## 11. 确定性 QA 与导出

### 11.1 审阅版

允许存在占位符和待确认章节，但必须显示：

- 审阅版水印；
- 未确认章节统计；
- 未关闭缺口统计；
- 可选的素材来源和原文追溯附录；
- 对应快照号。

### 11.2 正式版阻断条件

以下任一条件存在即禁止正式导出：

- 必需章节缺失；
- 内容章节未确认；
- 存在未关闭的阻塞缺口；
- 存在未处置风险；
- 存在未填写字段或附件占位符；
- 使用已过期素材或附件；
- 统一事实字段未确认或相互冲突；
- 必要招标格式块缺失；
- OOXML 结构校验失败；
- 项目快照与当前确认状态不一致。

风险“接受”必须由有权限的审阅人填写处置意见，不能由 AI 接受。

### 11.3 DOCX 导出

- 从快照构建，不读取自然语言风险报告；
- 招标复杂表格继续深拷贝 OOXML；
- 校验行数、网格列、列宽、`gridSpan`、`vMerge`；
- 统一注入事实字段、目录、章节编号和页码域；
- 保留签字盖章位；
- 重新打开生成文件进行完整性检查；
- 输出 QA 清单和文件哈希。

### 11.4 PDF 导出

- 由独立 RQ Worker 调用 LibreOffice Headless；
- 使用部署镜像内置的中文字体；
- 不参与快速骨架主链路；
- 检查页数、空白页异常和文本可提取性；
- PDF 导出失败不影响 DOCX 下载。

---

## 12. API 设计

统一前缀 `/api/v1`，写操作使用事务和项目版本校验。

### 12.1 配置接口

- `POST/GET/PATCH /companies`、`/products`；
- `POST /companies/{id}/revisions`、`/products/{id}/revisions`；
- `POST /company-revisions/{id}:publish`、`/product-revisions/{id}:publish`；
- `POST/GET/PATCH /redline-rules`；
- `POST/GET /assets`；
- `POST /assets/{id}/variants`；
- `POST /variants/{id}/revisions`；
- `POST /asset-revisions/{id}:publish`；
- `POST/GET /templates`、`/templates/{id}/revisions`；
- `POST /template-revisions/{id}:publish`。

### 12.2 项目与分析接口

- `POST /projects`：创建项目，可带 `source_project_id`；
- `POST /projects/{id}/tender-documents`：上传 DOCX/PDF；
- `POST /projects/{id}:parse`：解析并生成骨架；
- `POST /projects/{id}:analyze`：启动两次常规 AI 分析；
- `POST /projects/{id}:resolve-mapping`：仅在有歧义时启动第三次；
- `GET /projects/{id}/workspace`：章节、状态、风险、缺口和任务的聚合视图；
- `GET /projects/{id}/requirements`、`/risks`、`/score-assessments`；
- `GET /tender-documents/{id}/anchors/{anchor_key}`：读取原文；
- `GET /tasks/{id}`：任务状态；
- `GET /projects/{id}/events`：SSE 状态推送，断线后轮询补偿。

### 12.3 章节编辑接口

- `PATCH /sections/{id}`：修改允许的标题或属性；
- `POST /sections/{id}:move`：调整父级和位置；
- `GET /sections/{id}/candidates`：候选版本及推荐理由；
- `GET /sections/{id}/diff?candidate_id=...`：结构化差异；
- `POST /sections/{id}:select-version`：选择候选并生成项目修订；
- `POST /sections/{id}/revisions`：保存人工编辑；
- `POST /sections/{id}:confirm`：确认当前修订；
- `POST /gaps/{id}:resolve`：带解决依据关闭缺口；
- `POST /risks/{id}:disposition`：人工风险处置；
- `PATCH /projects/{id}/facts/{fact_key}`：更新事实并传播待复核状态。

### 12.4 快照与导出接口

- `POST /projects/{id}/snapshots`；
- `GET /projects/{id}/snapshots`；
- `POST /projects/{id}/exports`：指定快照、审阅/正式、DOCX/PDF；
- `GET /exports/{id}`：状态与 QA；
- `GET /exports/{id}/download`：权限校验后下载。

错误响应统一包含 `code、message、details、request_id`，不向浏览器暴露模型密钥、服务器路径或堆栈。

---

## 13. 安全、保密与运维

### 13.1 安全基线

- 全站 HTTPS；
- HttpOnly、SameSite Cookie，生产环境设置 Secure；
- 登录限速、会话过期和密码 Argon2 哈希；
- 所有项目资源执行服务端权限检查；
- 上传限制扩展名、MIME、大小和解压后大小；
- 文件以随机 ID 和哈希保存，禁止路径穿越；
- 富文本块白名单，禁止脚本和外部资源；
- 导出任务不使用用户输入拼接 Shell 命令；
- AI 密钥仅存在服务端环境；
- 审计日志不记录密码、密钥和完整敏感招标文本。

### 13.2 数据与备份

- PostgreSQL 定期备份并做恢复验证；
- 文件目录与数据库保持同一备份周期；
- 删除项目采用受权限控制的归档，不默认物理删除；
- 审阅版、正式版和快照保留创建人、时间和哈希；
- 外部 AI 是否保留数据由公司批准的模型服务配置决定，平台默认只发送任务必需文本。

### 13.3 运行监控

记录：解析耗时、骨架耗时、AI 调用次数与耗时、AI 失败率、缓存命中率、候选采用率、缺口关闭率、导出耗时和导出阻断原因。

重点监控“骨架生成”和“AI 分析”两类耗时，不合并成一个全链路指标。

---

## 14. 实施步骤

### 阶段 A：工程基线与确定性内核

1. 创建 monorepo、Docker Compose、数据库迁移和测试基座；
2. 迁移 shoot1 DOCX 提取、目录识别、结构合并和 OOXML 克隆；
3. 完成文本 PDF 解析和统一锚点；
4. 用 shoot1 样例建立 golden fixtures；
5. 完成项目上传、解析和快速骨架接口。

**验收：**AI 未配置时，DOCX 和文本 PDF 均能生成结构化骨架；扫描页明确提示；复杂表格结构保持。

### 阶段 B：配置中心与权限

1. 用户、会话、角色和项目成员；
2. 企业、产品、红线固定表单；
3. 素材、Variant、Revision、附件和发布流程；
4. 模板树编辑、锁定规则和发布；
5. 项目配置基线和审计。

**验收：**已发布配置不可原地修改；老项目版本不受新发布影响；越权访问被拒绝。

### 阶段 C：AI 分析与分析页面

1. 实现可配置模型网关和任务 Worker；
2. 实现提取、风险和可选编排三个固定契约；
3. 实现 Schema、锚点、范围和预算校验；
4. 实现缓存、失败状态、SSE 和审计；
5. 实现关键信息、风险、评分和待澄清页面。

**验收：**常规最多两次、特殊最多三次；AI 失败不阻塞骨架；AI 不生成正文，不自动接受风险。

### 阶段 D：卡片工作区与历史复用

1. 将原型拆为 React 组件并接入真实 API；
2. 实现章节移动、版本 Diff、版本切换和确认；
3. 实现 Block Editor、事实字段、附件和缺口；
4. 实现快照与续约项目历史候选；
5. 实现乐观锁和活动记录。

**验收：**固定章节不可移动；切换版本使当前及关联章节重新确认；历史内容只作为候选，跨客户不可见。

### 阶段 E：导出、部署与总体验收

1. 完成快照导出、审阅版门禁和正式版阻断；
2. 完成 DOCX QA 和 LibreOffice PDF Worker；
3. 完成备份、日志、监控和部署文档；
4. 完成单元、集成、契约和浏览器端到端测试；
5. 完成 AI 不可用、解析异常、并发冲突和导出失败演练。

**验收：**完成“配置 → 上传 → 分析 → 初稿 → 编辑 → 确认 → 导出 → 续约复用”的完整闭环。

---

## 15. 测试与验收

### 15.1 单元测试

- DOCX 目录识别、PDF 文本块与锚点；
- 章节合并、同义词、清洗和占位符；
- 候选过滤与可解释排序；
- 章节移动约束和编号；
- 版本切换、Diff、事实依赖和确认失效；
- 风险处置与正式导出门禁；
- OOXML 表格结构校验。

### 15.2 AI 契约测试

- CI 使用 Fake Model Gateway，不访问真实模型；
- 验证输入最小化、Schema、枚举和锚点校验；
- 验证最多三次调用和无自主语义重试；
- 验证无效节点、伪造锚点和正文输出被拒绝；
- 验证配置、编辑、确认和导出路径的 AI 调用次数为零。

### 15.3 集成与回归测试

- 使用 shoot1 的两份样例建立匿名化 golden fixtures；
- 比较招标索引、章节树、占位符和 QA；
- 验证相同文件与配置命中缓存；
- 验证 PDF 文本页可定位、图片页不进入 OCR；
- 验证项目权限、跨客户素材隔离和乐观锁；
- 验证快照导出期间继续编辑不影响文件。

### 15.4 浏览器端到端测试

覆盖：

1. 配置发布；
2. 创建项目和上传；
3. 骨架先于 AI 结果出现；
4. 查看原文、风险和评分；
5. 候选版本比较与切换；
6. 章节排序和层级调整；
7. 附件补齐与逐章确认；
8. 审阅版导出；
9. 未处理项阻断正式版；
10. 全部处理后正式导出；
11. 从历史项目创建续约项目并选择历史候选。

### 15.5 性能与可靠性验收

- 以 shoot1 的 DOCX 机械链路为回归基准，保持解析与结构合并不依赖 AI；
- DOCX、PDF、AI 和导出分别记录性能，不用一个总耗时掩盖差异；
- AI 不可用时，骨架、编辑、快照和审阅版导出仍可使用；
- LibreOffice 不可用时，DOCX 导出仍可使用；
- 正式版不存在未解释占位符、未确认章节和未处置风险。

---

## 16. 已确认的决策与假设

1. 平台首版部署在公司环境，浏览器不直接调用模型；
2. AI 通过可配置的 OpenAI 兼容接口接入，可连接公司批准的外部服务或内网模型；
3. 首版支持 DOCX 和可复制文本的 PDF，不支持扫描件 OCR；
4. 配置内容采用固定字段、固定表单和人工发布；
5. AI 只保留两次常规调用和一次可选编排调用；
6. 素材推荐采用固定元数据过滤和可解释规则，不做逐段 AI 满足度判断；
7. 初稿的主数据是章节树和不可变内容修订，Word/PDF 是快照的导出视图；
8. 用户从编辑、确认、导出到归档均不调用 AI；
9. 正式版必须来自通过确定性 QA 的人工确认快照；
10. 历史最终章节按权限作为续约候选，不自动成为新项目正文；
11. 首版采用单组织、单节点私有部署，暂不设计多租户和水平扩容；
12. 首版不包含报价、价格分、中标概率和法律结论自动化。
