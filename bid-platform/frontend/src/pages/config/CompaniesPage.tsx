import { useState } from 'react';
import { App, Button, Form, Input, Modal, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { BankOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { EmptyState, PageHeader, QueryError } from '../../components/Common';
import { RevisionList } from '../../components/config/RevisionList';
import { items } from '../../lib/query';
import type { Company, Revision } from '../../types';

export default function CompaniesPage() {
  const { message } = App.useApp();
  const query = useQuery({ queryKey: ['companies'], queryFn: api.companies.list });
  const [editing, setEditing] = useState<Company | null>();
  const [revisionCompany, setRevisionCompany] = useState<Company>();
  const [publishingId, setPublishingId] = useState<string>();
  const [form] = Form.useForm();
  const [revisionForm] = Form.useForm();

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['companies'] });
  const save = useMutation({
    mutationFn: (values: { code: string; name: string; status: string }) =>
      editing ? api.companies.update(editing.id, values) : api.companies.create(values),
    onSuccess: async () => {
      message.success(editing ? '企业信息已更新' : '企业已创建，请添加并发布配置版本');
      setEditing(undefined);
      await invalidate();
    },
    onError: (error) => message.error(error.message),
  });
  const createRevision = useMutation({
    mutationFn: (values: Record<string, unknown>) => api.companies.createRevision(revisionCompany!.id, values),
    onSuccess: async () => {
      message.success('企业修订草稿已创建');
      setRevisionCompany(undefined);
      revisionForm.resetFields();
      await invalidate();
    },
    onError: (error) => message.error(error.message),
  });
  const publish = useMutation({
    mutationFn: (revision: Revision) => {
      setPublishingId(revision.id);
      return api.companies.publish(revision.id);
    },
    onSuccess: async () => {
      message.success('企业配置版本已发布');
      await invalidate();
    },
    onError: (error) => message.error(error.message),
    onSettled: () => setPublishingId(undefined),
  });

  const columns: ColumnsType<Company> = [
    { title: '企业名称', dataIndex: 'name', render: (value, record) => <div className="primary-cell"><BankOutlined /><div><strong>{value}</strong><span>{record.code}</span></div></div> },
    { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value === 'active' ? '启用' : value === 'archived' ? '已归档' : value}</Tag> },
    { title: '发布版本', key: 'published', width: 130, render: (_, record) => { const revision = record.revisions?.find((item) => item.status === 'published'); return revision ? `V${revision.revision_no}` : '未发布'; } },
    { title: '修订数量', key: 'count', width: 110, render: (_, record) => record.revisions?.length || 0 },
    {
      title: '操作', key: 'actions', width: 250, align: 'right',
      render: (_, record) => <Space><Button size="small" onClick={() => setRevisionCompany(record)}>新建修订</Button><Button size="small" type="text" icon={<EditOutlined />} onClick={() => { setEditing(record); form.setFieldsValue(record); }}>编辑</Button></Space>,
    },
  ];

  return (
    <div className="page-container">
      <PageHeader eyebrow="CONFIGURATION" title="企业配置" description="工商、资质与联系人信息按不可变修订发布；老项目固定使用创建时版本。" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); }}>新增企业</Button>} />
      <div className="config-notice">只有已发布版本可用于新项目；修改已发布内容时，请创建新修订。</div>
      {query.error ? <QueryError error={query.error as Error} retry={() => void query.refetch()} /> : (
        <Table<Company>
          rowKey="id"
          loading={query.isLoading}
          dataSource={items(query.data)}
          columns={columns}
          pagination={false}
          locale={{ emptyText: <EmptyState description="尚未配置投标企业" /> }}
          expandable={{ expandedRowRender: (record) => <RevisionList revisions={record.revisions} onPublish={(revision) => publish.mutate(revision)} publishingId={publishingId} showContent /> }}
        />
      )}

      <Modal
        title={editing ? '编辑企业身份' : '新增企业'}
        open={editing !== undefined}
        onCancel={() => setEditing(undefined)}
        onOk={() => form.submit()}
        confirmLoading={save.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={(values) => save.mutate(values)} initialValues={{ status: 'active' }}>
          <Form.Item name="name" label="企业名称" rules={[{ required: true, message: '请输入企业名称' }]}><Input /></Form.Item>
          <Form.Item name="code" label="企业编码" rules={[{ required: true, message: '请输入唯一编码' }]}><Input disabled={Boolean(editing)} placeholder="例如：COMPANY-001" /></Form.Item>
          <Form.Item name="status" label="身份状态"><Select options={[{ value: 'active', label: '启用' }, { value: 'archived', label: '归档' }]} /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`新建企业修订 · ${revisionCompany?.name || ''}`}
        open={Boolean(revisionCompany)}
        onCancel={() => setRevisionCompany(undefined)}
        onOk={() => revisionForm.submit()}
        confirmLoading={createRevision.isPending}
        width={680}
        destroyOnClose
      >
        <Form form={revisionForm} layout="vertical" onFinish={(values) => createRevision.mutate(values)} className="form-grid two-columns">
          <Form.Item name="legal_name" label="工商登记全称" rules={[{ required: true }]} className="span-two"><Input /></Form.Item>
          <Form.Item name="unified_social_credit_code" label="统一社会信用代码" rules={[{ required: true }]}><Input maxLength={18} /></Form.Item>
          <Form.Item name="registered_address" label="注册地址"><Input /></Form.Item>
          <Form.Item name="contact_name" label="项目联系人"><Input /></Form.Item>
          <Form.Item name="contact_phone" label="联系电话"><Input /></Form.Item>
          <Form.Item name="qualification_summary" label="资质与能力摘要" className="span-two"><Input.TextArea rows={4} placeholder="由配置管理员录入并核验，平台不使用 AI 自动整理。" /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
