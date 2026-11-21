import { useState } from 'react';
import { App, Button, Form, Input, Modal, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ApartmentOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { EmptyState, PageHeader, QueryError } from '../../components/Common';
import { RevisionList } from '../../components/config/RevisionList';
import { TemplateNodeEditor } from '../../components/config/TemplateNodeEditor';
import { items } from '../../lib/query';
import type { Revision, Template, TemplateNode } from '../../types';

const initialNodes: TemplateNode[] = [
  { key: 'qualification', title: '资格证明文件', locked: true, children: [] },
  { key: 'technical', title: '技术响应方案', locked: false, children: [
    { key: 'understanding', title: '项目理解', locked: false, children: [] },
    { key: 'implementation', title: '总体实施方案', locked: false, children: [] },
    { key: 'service', title: '售后服务方案', locked: false, children: [] },
  ] },
  { key: 'commercial', title: '商务响应文件', locked: true, children: [] },
];

function TemplateRevisions({ template, onPublish, publishingId }: { template: Template; onPublish: (revision: Revision) => void; publishingId?: string }) {
  const revisions = useQuery({ queryKey: ['templates', template.id, 'revisions'], queryFn: () => api.templates.revisions(template.id) });
  if (revisions.error) return <QueryError error={revisions.error as Error} retry={() => void revisions.refetch()} />;
  return <RevisionList revisions={items(revisions.data)} onPublish={onPublish} publishingId={publishingId} />;
}

export default function TemplatesPage() {
  const { message } = App.useApp();
  const query = useQuery({ queryKey: ['templates'], queryFn: api.templates.list });
  const [creating, setCreating] = useState(false);
  const [revisionTemplate, setRevisionTemplate] = useState<Template>();
  const [nodes, setNodes] = useState<TemplateNode[]>(initialNodes);
  const [publishingId, setPublishingId] = useState<string>();
  const [form] = Form.useForm();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['templates'] });

  const create = useMutation({
    mutationFn: (values: { name: string; project_type: string }) => api.templates.create({ ...values, status: 'active' }),
    onSuccess: async () => { message.success('模板身份已创建，请配置并发布章节结构'); setCreating(false); form.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const createRevision = useMutation({
    mutationFn: () => api.templates.createRevision(revisionTemplate!.id, nodes),
    onSuccess: async () => { message.success('模板修订草稿已保存'); setRevisionTemplate(undefined); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const publish = useMutation({
    mutationFn: (revision: Revision) => { setPublishingId(revision.id); return api.templates.publish(revision.id); },
    onSuccess: async () => { message.success('模板版本已发布'); await invalidate(); await queryClient.invalidateQueries({ queryKey: ['templates'] }); },
    onError: (error) => message.error(error.message),
    onSettled: () => setPublishingId(undefined),
  });

  const columns: ColumnsType<Template> = [
    { title: '模板', dataIndex: 'name', render: (value, record) => <div className="primary-cell"><ApartmentOutlined /><div><strong>{value}</strong><span>{record.project_type}</span></div></div> },
    { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value === 'active' ? '启用' : value}</Tag> },
    { title: '发布版本', key: 'published', width: 130, render: (_, record) => { const revision = record.revisions?.find((item) => item.status === 'published'); return revision ? `V${revision.revision_no}` : '查看修订'; } },
    { title: '操作', key: 'actions', width: 160, align: 'right', render: (_, record) => <Button size="small" onClick={() => { setRevisionTemplate(record); setNodes(record.revisions?.[0]?.nodes_json || initialNodes); }}>新建结构修订</Button> },
  ];

  return (
    <div className="page-container">
      <PageHeader eyebrow="CONFIGURATION" title="标书模板" description="配置稳定章节键、默认层级与锁定策略；招标明确规定的结构始终优先。" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>新增模板</Button>} />
      <div className="config-notice">锁定章节不可拖动或调整层级；企业补充章节只允许在模板允许的子树内移动。</div>
      {query.error ? <QueryError error={query.error as Error} retry={() => void query.refetch()} /> : <Table<Template> rowKey="id" loading={query.isLoading} dataSource={items(query.data)} columns={columns} pagination={false} locale={{ emptyText: <EmptyState description="尚未配置标书模板" /> }} expandable={{ expandedRowRender: (record) => <TemplateRevisions template={record} onPublish={(revision) => publish.mutate(revision)} publishingId={publishingId} /> }} />}

      <Modal title="新增标书模板" open={creating} onCancel={() => setCreating(false)} onOk={() => form.submit()} confirmLoading={create.isPending} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)}>
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="project_type" label="适用项目类型" rules={[{ required: true }]}><Input placeholder="例如：数据库采购 / 软件开发" /></Form.Item>
        </Form>
      </Modal>
      <Modal title={`新建模板修订 · ${revisionTemplate?.name || ''}`} open={Boolean(revisionTemplate)} onCancel={() => setRevisionTemplate(undefined)} onOk={() => createRevision.mutate()} confirmLoading={createRevision.isPending} width={1080} destroyOnClose>
        <div className="modal-intro">调整只保存为草稿。发布前请核验稳定键；项目中的章节引用使用 ID 和 section_key，不在正文写死编号。</div>
        <TemplateNodeEditor value={nodes} onChange={setNodes} />
      </Modal>
    </div>
  );
}
