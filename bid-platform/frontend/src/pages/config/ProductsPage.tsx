import { useState } from 'react';
import { App, Button, Form, Input, Modal, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { EditOutlined, PlusOutlined, ProductOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { EmptyState, PageHeader, QueryError } from '../../components/Common';
import { RevisionList } from '../../components/config/RevisionList';
import { items } from '../../lib/query';
import type { Product, Revision } from '../../types';

export default function ProductsPage() {
  const { message } = App.useApp();
  const query = useQuery({ queryKey: ['products'], queryFn: api.products.list });
  const [editing, setEditing] = useState<Product | null>();
  const [revisionProduct, setRevisionProduct] = useState<Product>();
  const [publishingId, setPublishingId] = useState<string>();
  const [form] = Form.useForm();
  const [revisionForm] = Form.useForm();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['products'] });

  const save = useMutation({
    mutationFn: (values: { code: string; name: string; status: string }) => editing ? api.products.update(editing.id, values) : api.products.create(values),
    onSuccess: async () => { message.success(editing ? '产品信息已更新' : '产品已创建'); setEditing(undefined); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const createRevision = useMutation({
    mutationFn: (values: Record<string, unknown>) => api.products.createRevision(revisionProduct!.id, {
      fields_json: {
        description: values.description,
        deployment: values.deployment,
        service: values.service,
      },
      technical_fields_json: { parameters: values.parameters, proof_materials: values.proof_materials },
    }),
    onSuccess: async () => { message.success('产品修订草稿已创建'); setRevisionProduct(undefined); revisionForm.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const publish = useMutation({
    mutationFn: (revision: Revision) => { setPublishingId(revision.id); return api.products.publish(revision.id); },
    onSuccess: async () => { message.success('产品配置版本已发布'); await invalidate(); },
    onError: (error) => message.error(error.message),
    onSettled: () => setPublishingId(undefined),
  });

  const columns: ColumnsType<Product> = [
    { title: '产品', dataIndex: 'name', render: (value, record) => <div className="primary-cell"><ProductOutlined /><div><strong>{value}</strong><span>{record.code}</span></div></div> },
    { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value === 'active' ? '启用' : value === 'archived' ? '已归档' : value}</Tag> },
    { title: '发布版本', key: 'published', width: 130, render: (_, record) => { const revision = record.revisions?.find((item) => item.status === 'published'); return revision ? `V${revision.revision_no}` : '未发布'; } },
    { title: '修订数量', key: 'count', width: 110, render: (_, record) => record.revisions?.length || 0 },
    { title: '操作', key: 'actions', width: 250, align: 'right', render: (_, record) => <Space><Button size="small" onClick={() => setRevisionProduct(record)}>新建修订</Button><Button size="small" type="text" icon={<EditOutlined />} onClick={() => { setEditing(record); form.setFieldsValue(record); }}>编辑</Button></Space> },
  ];

  return (
    <div className="page-container">
      <PageHeader eyebrow="CONFIGURATION" title="产品配置" description="维护产品参数、部署方式、服务承诺及证明材料，发布后方可作为项目基线。" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); }}>新增产品</Button>} />
      <div className="config-notice">技术字段与商务服务字段分开维护，导出时仅注入已确认的项目事实。</div>
      {query.error ? <QueryError error={query.error as Error} retry={() => void query.refetch()} /> : (
        <Table<Product> rowKey="id" loading={query.isLoading} dataSource={items(query.data)} columns={columns} pagination={false} locale={{ emptyText: <EmptyState description="尚未配置产品" /> }} expandable={{ expandedRowRender: (record) => <RevisionList revisions={record.revisions} onPublish={(revision) => publish.mutate(revision)} publishingId={publishingId} showContent /> }} />
      )}
      <Modal title={editing ? '编辑产品身份' : '新增产品'} open={editing !== undefined} onCancel={() => setEditing(undefined)} onOk={() => form.submit()} confirmLoading={save.isPending} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(values) => save.mutate(values)} initialValues={{ status: 'active' }}>
          <Form.Item name="name" label="产品名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="code" label="产品编码" rules={[{ required: true }]}><Input disabled={Boolean(editing)} /></Form.Item>
          <Form.Item name="status" label="身份状态"><Select options={[{ value: 'active', label: '启用' }, { value: 'archived', label: '归档' }]} /></Form.Item>
        </Form>
      </Modal>
      <Modal title={`新建产品修订 · ${revisionProduct?.name || ''}`} open={Boolean(revisionProduct)} onCancel={() => setRevisionProduct(undefined)} onOk={() => revisionForm.submit()} confirmLoading={createRevision.isPending} width={720} destroyOnClose>
        <Form form={revisionForm} layout="vertical" onFinish={(values) => createRevision.mutate(values)}>
          <Form.Item name="description" label="产品说明" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <div className="form-grid two-columns">
            <Form.Item name="deployment" label="部署方式"><Input placeholder="例如：本地化部署 / 云端服务" /></Form.Item>
            <Form.Item name="service" label="标准服务承诺"><Input placeholder="例如：7×24 小时受理" /></Form.Item>
          </div>
          <Form.Item name="parameters" label="技术参数" extra="每行一条，由发布人对内容准确性负责。"><Input.TextArea rows={5} placeholder="参数名：参数值" /></Form.Item>
          <Form.Item name="proof_materials" label="证明材料清单"><Input.TextArea rows={3} placeholder="证书、检测报告、功能截图等" /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
