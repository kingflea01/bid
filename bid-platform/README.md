# 标书编写平台

面向公司内部的标书编写与审阅平台。平台以确定性文档处理和章节版本管理为主，AI 仅用于招标关键信息提取、风险策略分析及可选的编排歧义处理。

## 主要能力

- 企业、产品、素材、红线和模板的固定字段配置与人工发布；
- DOCX、文本 PDF 招标解析与原文锚点；
- 不等待 AI 的章节卡片骨架；
- 候选素材比较、章节结构调整、人工编辑、缺口处理和逐章确认；
- 不可变项目快照、审阅版/正式版导出及历史续约复用；
- 项目权限、操作审计和后端受控 AI 调用。

## 私有部署

1. 复制 `.env.example` 为 `.env`，替换数据库密码、会话密钥和管理员密码。
2. 如启用 AI，只配置公司批准的模型接口。`AI_API_KEY` 不会发送到浏览器。
3. 启动服务：

```bash
docker compose --env-file .env up --build
```

默认访问 `http://localhost:8080`。生产环境应在反向代理处启用 HTTPS，并将 `SESSION_SECURE` 设置为 `true`。

## 本地开发

后端需要 Python 3.12+，前端需要 Node.js 22+。

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

本地开发默认使用 SQLite 和同步后台任务；容器部署使用 PostgreSQL、Redis 和 RQ Worker。正式部署前应运行后端测试、前端构建及端到端验收。

## 数据与保密

- 上传文件、项目快照和导出文件保存在持久化文件目录，业务数据保存在 PostgreSQL。
- AI 未配置或不可用时，骨架、编辑、快照和审阅版导出仍可工作。
- 扫描件不执行 OCR；图片页和无法还原的格式模板进入人工处理。
- 正式导出要求章节确认、缺口关闭、风险处置和确定性 QA 全部通过。

## 备份与验证

```bash
# 数据库与文件配套备份；备份包含业务敏感信息，应存放在受控位置。
scripts/backup.sh

# 后端测试与静态检查
cd backend && python3 -m pytest -q && python3 -m ruff check app tests

# 前端构建与单元测试
cd frontend && npm run build && npm test
```
