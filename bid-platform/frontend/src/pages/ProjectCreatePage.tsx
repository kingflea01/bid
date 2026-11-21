import { useMemo, useState } from 'react';
import { Alert, App, Button, Form, Input, Select, Steps, Upload } from 'antd';
import type { UploadFile } from 'antd';
import { ArrowRightOutlined, FileAddOutlined, InboxOutlined, RocketOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { api, type ProjectCreateInput } from '../app/api';
import { PageHeader, QueryError } from '../components/Common';
import { items, queryKeys } from '../lib/query';
import type { Project, Revision } from '../types';

interface ProjectFormValues extends ProjectCreateInput {
  company_id?: string;
  product_id?: string;
  template_id?: string;
}

const published = (revisions: Revision[] | undefined) =>
  (revisions || []).filter((revision) => revision.status === 'published');

export default function ProjectCreatePage() {
  const { message } = App.useApp();
  const [params] = useSearchParams();
  const sourceProjectId = params.get('source_project_id') || undefined;
  const [form] = Form.useForm<ProjectFormValues>();
  const [created, setCreated] = useState<Project>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploaded, setUploaded] = useState(false);
  const [parsed, setParsed] = useState(false);

  const companies = useQuery({ queryKey: ['companies'], queryFn: api.companies.list });
  const products = useQuery({ queryKey: ['products'], queryFn: api.products.list });
  const templates = useQuery({ queryKey: ['templates'], queryFn: api.templates.list });
  const projects = useQuery({ queryKey: [...queryKeys.projects, 'history-options'], queryFn: () => api.projects.list({ page_size: 100 }) });

  const companyId = Form.useWatch('company_id', form);
  const productId = Form.useWatch('product_id', form);
  const templateId = Form.useWatch('template_id', form);
  const company = items(companies.data).find((entry) => entry.id === companyId);
  const product = items(products.data).find((entry) => entry.id === productId);
  const template = items(templates.data).find((entry) => entry.id === templateId);
  const sourceProject = items(projects.data).find((entry) => entry.id === sourceProjectId);

  const createMutation = useMutation({
    mutationFn: api.projects.create,
    onSuccess: (project) => {
      setCreated(project);
      message.success('项目已创建，请上传招标文件');
    },
    onError: (error) => message.error(error.message),
  });
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.projects.uploadTender(created!.id, file),
    onSuccess: async () => {
      setUploaded(true);
      if (created) setCreated(await api.projects.get(created.id));
      message.success('招标文件已上传，可以开始确定性解析');
    },
    onError: (error) => message.error(error.message),
  });
  const parseMutation = useMutation({
    mutationFn: () => api.projects.parse(created!.id, created!.version),
    onSuccess: async () => {
      setParsed(true);
      if (created) setCreated(await api.projects.get(created.id));
      message.success('解析任务已启动，章节骨架生成不依赖 AI 分析');
    },
    onError: (error) => message.error(error.message),
  });
  const analyzeMutation = useMutation({
    mutationFn: () => api.projects.analyze(created!.id, created!.version),
    onSuccess: (result) => {
      const failed = result.tasks?.some((task) => task.status === 'failed');
      if (failed) message.warning('AI 分析未完成，但不影响章节骨架与人工编辑，可在分析页查看原因');
      else message.success('AI 分析任务已启动，可在分析页查看进度');
    },
    onError: (error) => message.error(error.message),
  });

  const configError = companies.error || products.error || templates.error || projects.error;
  const step = parsed ? 2 : created ? 1 : 0;
  const historyOptions = useMemo(
    () => items(projects.data).filter((project) => project.status !== 'draft').map((project) => ({
      value: project.id,
      label: `${project.name} · ${project.customer_name}`,
    })),
    [projects.data],
  );

  const submit = async (values: ProjectFormValues) => {
    await createMutation.mutateAsync({
      name: values.name,
      code: values.code,
      customer_name: values.customer_name,
      procurement_type: values.procurement_type,
      package: values.package,
      company_revision_id: values.company_revision_id,
      product_revision_id: values.product_revision_id,
      template_revision_id: values.template_revision_id,
      source_project_id: values.source_project_id,
    });
  };

  return (
    <div className="page-container project-create-page">
      <PageHeader eyebrow="NEW PROJECT" title={sourceProjectId ? '创建续约项目' : '新建应标项目'} description="固定已发布配置基线；历史最终章节仅进入候选列表。" back />
      <Steps
        current={step}
        items={[{ title: '项目与配置' }, { title: '上传与解析' }, { title: '进入工作区' }]}
        className="create-steps"
      />
      {configError && <QueryError error={configError as Error} />}
      <div className="create-layout">
        <section className="create-main">
          <div className="section-heading"><h2>项目信息</h2><span>带 * 为必填项</span></div>
          <Form<ProjectFormValues>
            form={form}
            layout="vertical"
            onFinish={(values) => void submit(values)}
            initialValues={{ procurement_type: '公开招标', source_project_id: sourceProjectId }}
            disabled={Boolean(created)}
            requiredMark
          >
            <div className="form-grid two-columns">
              <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]} className="span-two">
                <Input placeholder="例如：2026 年度数据库采购项目" maxLength={120} />
              </Form.Item>
              <Form.Item name="code" label="项目编号" rules={[{ required: true, message: '请输入项目编号' }]}>
                <Input placeholder="例如：2026-041" maxLength={60} />
              </Form.Item>
              <Form.Item name="package" label="分包名称 / 编号">
                <Input placeholder="例如：第 03 包" maxLength={80} />
              </Form.Item>
              <Form.Item name="customer_name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
                <Input placeholder="采购人全称" maxLength={120} />
              </Form.Item>
              <Form.Item name="procurement_type" label="采购方式" rules={[{ required: true }]}>
                <Select options={['公开招标', '邀请招标', '竞争性磋商', '竞争性谈判', '询价', '单一来源'].map((value) => ({ value, label: value }))} />
              </Form.Item>
            </div>

            <div className="section-heading with-divider"><h2>发布配置基线</h2><span>项目创建后不受后续发布影响</span></div>
            <div className="form-grid three-columns">
              <Form.Item name="company_id" label="投标企业" rules={[{ required: true, message: '请选择企业' }]}>
                <Select placeholder="选择企业" loading={companies.isLoading} onChange={() => form.setFieldValue('company_revision_id', undefined)} options={items(companies.data).map((entry) => ({ value: entry.id, label: entry.name }))} />
              </Form.Item>
              <Form.Item name="product_id" label="产品" rules={[{ required: true, message: '请选择产品' }]}>
                <Select placeholder="选择产品" loading={products.isLoading} onChange={() => form.setFieldValue('product_revision_id', undefined)} options={items(products.data).map((entry) => ({ value: entry.id, label: entry.name }))} />
              </Form.Item>
              <Form.Item name="template_id" label="标书模板" rules={[{ required: true, message: '请选择模板' }]}>
                <Select placeholder="选择模板" loading={templates.isLoading} onChange={() => form.setFieldValue('template_revision_id', undefined)} options={items(templates.data).map((entry) => ({ value: entry.id, label: entry.name }))} />
              </Form.Item>
              <Form.Item name="company_revision_id" label="企业发布版本" rules={[{ required: true, message: '请选择已发布版本' }]}>
                <Select placeholder="先选择企业" options={published(company?.revisions).map((revision) => ({ value: revision.id, label: `V${revision.revision_no} · 已发布` }))} notFoundContent="暂无已发布版本" />
              </Form.Item>
              <Form.Item name="product_revision_id" label="产品发布版本" rules={[{ required: true, message: '请选择已发布版本' }]}>
                <Select placeholder="先选择产品" options={published(product?.revisions).map((revision) => ({ value: revision.id, label: `V${revision.revision_no} · 已发布` }))} notFoundContent="暂无已发布版本" />
              </Form.Item>
              <Form.Item name="template_revision_id" label="模板发布版本" rules={[{ required: true, message: '请选择已发布版本' }]}>
                <Select placeholder="先选择模板" options={published(template?.revisions).map((revision) => ({ value: revision.id, label: `V${revision.revision_no} · 已发布` }))} notFoundContent="暂无已发布版本" />
              </Form.Item>
            </div>

            <div className="section-heading with-divider"><h2>历史复用</h2><span>可选</span></div>
            <Form.Item name="source_project_id" label="来源项目" extra="按客户、产品、章节键和模板节点匹配历史最终确认版本；沿用后仍需重新确认。">
              <Select allowClear showSearch optionFilterProp="label" placeholder="不使用历史项目" options={historyOptions} loading={projects.isLoading} />
            </Form.Item>
            {sourceProject && <Alert type="info" showIcon message={`将从“${sourceProject.name}”复用候选内容`} description="原项目快照保持不可变，历史日期、人员、服务期与附件需重新校验。" />}
            {!created && <Button type="primary" htmlType="submit" loading={createMutation.isPending} icon={<ArrowRightOutlined />} iconPosition="end">创建项目并上传文件</Button>}
          </Form>
        </section>

        <aside className="create-side">
          <div className="section-heading"><h2>招标文件</h2><span>DOCX / 文本 PDF</span></div>
          {!created ? (
            <div className="upload-placeholder"><InboxOutlined /><p>创建项目后上传</p><span>不支持扫描件 OCR，图片页将标记人工处理。</span></div>
          ) : (
            <>
              <Upload.Dragger
                fileList={fileList}
                maxCount={1}
                accept=".docx,.pdf"
                beforeUpload={(file) => {
                  const valid = /\.(docx|pdf)$/i.test(file.name) && file.size <= 50 * 1024 * 1024;
                  if (!valid) {
                    message.error('仅支持不超过 50 MB 的 DOCX / PDF 文件');
                    return Upload.LIST_IGNORE;
                  }
                  setFileList([file]);
                  setUploaded(false);
                  return false;
                }}
                onRemove={() => { setFileList([]); setUploaded(false); }}
              >
                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                <p className="ant-upload-text">选择或拖入招标文件</p>
                <p className="ant-upload-hint">单个文件，最大 50 MB；按 SHA-256 去重。</p>
              </Upload.Dragger>
              <Button
                block
                type="primary"
                disabled={!fileList.length || uploaded}
                loading={uploadMutation.isPending}
                onClick={() => {
                  const file = fileList[0]?.originFileObj;
                  if (file) void uploadMutation.mutateAsync(file as File);
                }}
              >{uploaded ? '文件已上传' : '上传招标文件'}</Button>
              <div className="create-side-actions">
                <Button disabled={!uploaded || parsed} loading={parseMutation.isPending} onClick={() => void parseMutation.mutateAsync()} icon={<RocketOutlined />}>解析并生成骨架</Button>
                <Button disabled={!parsed} loading={analyzeMutation.isPending} onClick={() => void analyzeMutation.mutateAsync()}>启动 AI 分析（可选）</Button>
              </div>
            </>
          )}
          {parsed && created && (
            <div className="create-complete">
              <FileAddOutlined />
              <strong>解析任务已进入队列</strong>
              <p>可先查看任务状态；骨架完成后即可编辑，无需等待 AI。</p>
              <Link to={`/projects/${created.id}/workspace`}><Button type="primary">进入章节工作区</Button></Link>
              <Link to={`/projects/${created.id}/analysis`}><Button type="link">查看解析与分析状态</Button></Link>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
