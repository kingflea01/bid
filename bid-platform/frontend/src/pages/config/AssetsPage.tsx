import { useState } from 'react';
import { App, Button, DatePicker, Form, Input, Modal, Select, Space, Table, Tag, Upload } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd';
import { DatabaseOutlined, PaperClipOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import dayjs, { type Dayjs } from 'dayjs';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { EmptyState, PageHeader, QueryError } from '../../components/Common';
import { RevisionList } from '../../components/config/RevisionList';
import { items } from '../../lib/query';
import { date } from '../../lib/format';
import type { Asset, AssetVariant, ContentBlock, Revision } from '../../types';

interface AssetFormValues {
  code: string;
  title: string;
  asset_type: string;
  scope: string;
  industry?: string;
  product_id?: string;
  customer_name?: string;
  valid_range?: [Dayjs, Dayjs];
}

export default function AssetsPage() {
  const { message } = App.useApp();
  const [assetType, setAssetType] = useState<string>();
  const query = useQuery({ queryKey: ['assets', { assetType }], queryFn: () => api.assets.list({ asset_type: assetType }) });
  const products = useQuery({ queryKey: ['products'], queryFn: api.products.list });
  const [creating, setCreating] = useState(false);
  const [variantAsset, setVariantAsset] = useState<Asset>();
  const [revisionVariant, setRevisionVariant] = useState<AssetVariant>();
  const [attachmentAsset, setAttachmentAsset] = useState<Asset>();
  const [publishingId, setPublishingId] = useState<string>();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [form] = Form.useForm<AssetFormValues>();
  const [variantForm] = Form.useForm();
  const [revisionForm] = Form.useForm();
  const [attachmentForm] = Form.useForm();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['assets'] });

  const create = useMutation({
    mutationFn: (values: AssetFormValues) => {
      const { valid_range: range, ...rest } = values;
      return api.assets.create({
        ...rest,
        status: 'active',
        valid_from: range?.[0]?.format('YYYY-MM-DD'),
        valid_to: range?.[1]?.format('YYYY-MM-DD'),
      });
    },
    onSuccess: async () => { message.success('素材身份已创建，请添加内容方案与修订'); setCreating(false); form.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const createVariant = useMutation({
    mutationFn: (values: { code: string; name: string; description?: string }) => api.assets.createVariant(variantAsset!.id, values),
    onSuccess: async () => { message.success('候选方案已创建'); setVariantAsset(undefined); variantForm.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const createRevision = useMutation({
    mutationFn: (values: { content: string }) => {
      const content_json: ContentBlock[] = values.content.split(/\n\s*\n/).filter((part) => part.trim()).map((part) => ({ type: 'paragraph', text: part.trim() }));
      return api.assets.createRevision(revisionVariant!.id, content_json);
    },
    onSuccess: async () => { message.success('素材修订草稿已创建'); setRevisionVariant(undefined); revisionForm.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const publish = useMutation({
    mutationFn: (revision: Revision) => { setPublishingId(revision.id); return api.assets.publish(revision.id); },
    onSuccess: async () => { message.success('素材修订已发布'); await invalidate(); },
    onError: (error) => message.error(error.message),
    onSettled: () => setPublishingId(undefined),
  });
  const uploadAttachment = useMutation({
    mutationFn: (values: { attachment_type: string; valid_to?: Dayjs }) => {
      const file = files[0]?.originFileObj;
      if (!file) throw new Error('请选择附件');
      return api.assets.uploadAttachment(attachmentAsset!.id, file as File, values.attachment_type, values.valid_to?.format('YYYY-MM-DD'));
    },
    onSuccess: async () => { message.success('证明附件已上传'); setAttachmentAsset(undefined); setFiles([]); attachmentForm.resetFields(); await invalidate(); },
    onError: (error) => message.error(error.message),
  });

  const columns: ColumnsType<Asset> = [
    { title: '素材', dataIndex: 'title', minWidth: 240, render: (value, record) => <div className="primary-cell"><DatabaseOutlined /><div><strong>{value}</strong><span>{record.code} · {record.asset_type}</span></div></div> },
    { title: '适用范围', key: 'scope', width: 200, render: (_, record) => <div className="stacked-cell"><span>{record.scope}</span><small>{[record.industry, record.customer_name].filter(Boolean).join(' · ') || '企业通用'}</small></div> },
    { title: '有效期', key: 'valid', width: 190, render: (_, record) => `${date(record.valid_from)} — ${date(record.valid_to)}` },
    { title: '方案', key: 'variants', width: 80, render: (_, record) => record.variants?.length || 0 },
    { title: '状态', dataIndex: 'status', width: 90, render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value === 'active' ? '有效' : value}</Tag> },
    { title: '操作', key: 'actions', width: 260, align: 'right', render: (_, record) => <Space><Button size="small" onClick={() => setVariantAsset(record)}>添加方案</Button><Button size="small" icon={<PaperClipOutlined />} onClick={() => setAttachmentAsset(record)}>附件</Button></Space> },
  ];

  return (
    <div className="page-container">
      <PageHeader eyebrow="CONFIGURATION" title="知识素材" description="素材身份、内容方案与不可变修订分离管理，推荐仅依据明确元数据和发布状态。" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>新增素材</Button>} />
      <div className="list-toolbar">
        <Select allowClear placeholder="全部素材类型" value={assetType} onChange={setAssetType} className="status-select" options={['项目理解', '实施方案', '售后服务', '资质证书', '人员案例', '企业业绩', '其他'].map((value) => ({ value, label: value }))} />
        <span className="toolbar-description">候选方案用于区分标准、驻场或客户专属内容路线，不等同于修订版本。</span>
      </div>
      {query.error ? <QueryError error={query.error as Error} retry={() => void query.refetch()} /> : (
        <Table<Asset>
          rowKey="id"
          loading={query.isLoading}
          dataSource={items(query.data)}
          columns={columns}
          scroll={{ x: 1080 }}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          locale={{ emptyText: <EmptyState description="尚未录入知识素材" /> }}
          expandable={{
            expandedRowRender: (asset) => (
              <div className="asset-variants">
                {(asset.variants || []).map((variant) => (
                  <section key={variant.id} className="variant-section">
                    <div className="variant-heading"><div><strong>{variant.name}</strong><span>{variant.code} · {variant.description || '无方案说明'}</span></div><Button size="small" onClick={() => setRevisionVariant(variant)}>新建内容修订</Button></div>
                    <RevisionList revisions={variant.revisions} onPublish={(revision) => publish.mutate(revision)} publishingId={publishingId} />
                  </section>
                ))}
                {!asset.variants?.length && <div className="inline-empty">暂无候选方案，请先添加标准或客户专属方案。</div>}
              </div>
            ),
          }}
        />
      )}

      <Modal title="新增素材身份" open={creating} onCancel={() => setCreating(false)} onOk={() => form.submit()} confirmLoading={create.isPending} width={720} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)} initialValues={{ scope: '企业通用', asset_type: '实施方案' }} className="form-grid two-columns">
          <Form.Item name="title" label="素材标题" rules={[{ required: true }]} className="span-two"><Input /></Form.Item>
          <Form.Item name="code" label="素材编码" rules={[{ required: true }]}><Input placeholder="例如：ASSET-IMPL-001" /></Form.Item>
          <Form.Item name="asset_type" label="素材类型" rules={[{ required: true }]}><Select options={['项目理解', '实施方案', '售后服务', '资质证书', '人员案例', '企业业绩', '其他'].map((value) => ({ value, label: value }))} /></Form.Item>
          <Form.Item name="scope" label="适用范围" rules={[{ required: true }]}><Select options={['企业通用', '行业', '产品线', '客户专属'].map((value) => ({ value, label: value }))} /></Form.Item>
          <Form.Item name="industry" label="行业"><Input /></Form.Item>
          <Form.Item name="product_id" label="关联产品"><Select allowClear options={items(products.data).map((product) => ({ value: product.id, label: product.name }))} /></Form.Item>
          <Form.Item name="customer_name" label="客户名称（客户专属时填写）"><Input /></Form.Item>
          <Form.Item name="valid_range" label="有效期" className="span-two"><DatePicker.RangePicker className="full-width" /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`添加候选方案 · ${variantAsset?.title || ''}`} open={Boolean(variantAsset)} onCancel={() => setVariantAsset(undefined)} onOk={() => variantForm.submit()} confirmLoading={createVariant.isPending} destroyOnClose>
        <Form form={variantForm} layout="vertical" onFinish={(values) => createVariant.mutate(values)}>
          <Form.Item name="name" label="方案名称" rules={[{ required: true }]}><Input placeholder="例如：高校驻场实施方案" /></Form.Item>
          <Form.Item name="code" label="方案编码" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="方案说明"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`新建内容修订 · ${revisionVariant?.name || ''}`} open={Boolean(revisionVariant)} onCancel={() => setRevisionVariant(undefined)} onOk={() => revisionForm.submit()} confirmLoading={createRevision.isPending} width={720} destroyOnClose>
        <Form form={revisionForm} layout="vertical" onFinish={(values) => createRevision.mutate(values)}>
          <Form.Item name="content" label="结构化正文" extra="按空行拆分为段落块；保存后生成草稿，发布前可继续核验。" rules={[{ required: true }]}><Input.TextArea rows={12} placeholder="录入经人工核验的正文，平台不会调用 AI 自动整理。" /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`上传证明附件 · ${attachmentAsset?.title || ''}`} open={Boolean(attachmentAsset)} onCancel={() => { setAttachmentAsset(undefined); setFiles([]); }} onOk={() => attachmentForm.submit()} confirmLoading={uploadAttachment.isPending} destroyOnClose>
        <Form form={attachmentForm} layout="vertical" onFinish={(values) => uploadAttachment.mutate(values)}>
          <Form.Item name="attachment_type" label="附件类型" rules={[{ required: true }]}><Select options={['证书扫描件', '合同证明', '验收报告', '人员证明', '其他'].map((value) => ({ value, label: value }))} /></Form.Item>
          <Form.Item name="valid_to" label="有效期至"><DatePicker className="full-width" disabledDate={(current) => current < dayjs().startOf('day')} /></Form.Item>
          <Form.Item label="附件文件" required>
            <Upload fileList={files} maxCount={1} beforeUpload={(file) => { setFiles([file]); return false; }} onRemove={() => setFiles([])}><Button icon={<PaperClipOutlined />}>选择文件</Button></Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
