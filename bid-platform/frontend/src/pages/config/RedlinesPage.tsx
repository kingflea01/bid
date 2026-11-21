import { useState } from 'react';
import { App, Button, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { EditOutlined, PlusOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { EmptyState, PageHeader, QueryError } from '../../components/Common';
import { displayJson } from '../../lib/format';
import { items } from '../../lib/query';
import type { RedlineRule } from '../../types';

interface RuleFormValues {
  scope_type: 'company' | 'product';
  scope_id?: string;
  category: string;
  position: string;
  condition_text: string;
  action: string;
  legal_review: boolean;
  revision_no: number;
  status: string;
}

export default function RedlinesPage() {
  const { message } = App.useApp();
  const query = useQuery({ queryKey: ['redlines'], queryFn: api.redlines.list });
  const companies = useQuery({ queryKey: ['companies'], queryFn: api.companies.list });
  const products = useQuery({ queryKey: ['products'], queryFn: api.products.list });
  const [editing, setEditing] = useState<RedlineRule | null>();
  const [form] = Form.useForm<RuleFormValues>();
  const scopeType = Form.useWatch('scope_type', form);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['redlines'] });

  const save = useMutation({
    mutationFn: (values: RuleFormValues) => {
      const { condition_text, ...rest } = values;
      const payload = { ...rest, condition_json: JSON.parse(condition_text) as Record<string, unknown> };
      if (editing?.status === 'published') {
        return api.redlines.create({ ...payload, revision_no: editing.revision_no + 1, status: 'draft' });
      }
      return editing ? api.redlines.update(editing.id, payload) : api.redlines.create(payload);
    },
    onSuccess: async () => { message.success(editing?.status === 'published' ? '已基于发布版创建新草稿' : editing ? '红线规则已更新' : '红线规则已创建'); setEditing(undefined); await invalidate(); },
    onError: (error) => message.error(error.message),
  });
  const publish = useMutation({
    mutationFn: (rule: RedlineRule) => api.redlines.update(rule.id, { status: rule.status === 'published' ? 'archived' : 'published' }),
    onSuccess: async () => { message.success('规则状态已更新'); await invalidate(); },
    onError: (error) => message.error(error.message),
  });

  const openEditor = (rule?: RedlineRule) => {
    setEditing(rule || null);
    if (rule) {
      form.setFieldsValue({
        scope_type: rule.scope_type,
        scope_id: rule.scope_id,
        category: rule.category,
        position: rule.position,
        condition_text: JSON.stringify(rule.condition_json, null, 2),
        action: rule.action,
        legal_review: rule.legal_review,
        revision_no: rule.revision_no,
        status: rule.status,
      });
    } else {
      form.resetFields();
    }
  };

  const columns: ColumnsType<RedlineRule> = [
    { title: '类别', dataIndex: 'category', width: 150, render: (value) => <span className="rule-category"><SafetyCertificateOutlined />{value}</span> },
    { title: '立场', dataIndex: 'position', minWidth: 220, ellipsis: true },
    { title: '适用范围', key: 'scope', width: 130, render: (_, record) => record.scope_type === 'company' ? '企业级' : '产品级' },
    { title: '触发条件', dataIndex: 'condition_json', minWidth: 200, ellipsis: true, render: (value) => <code className="json-inline">{displayJson(value).replace(/\s+/g, ' ')}</code> },
    { title: '建议动作', dataIndex: 'action', minWidth: 200, ellipsis: true },
    { title: '法务', dataIndex: 'legal_review', width: 80, render: (value: boolean) => value ? <Tag color="gold">需复核</Tag> : '—' },
    { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'published' ? 'green' : value === 'draft' ? 'blue' : 'default'}>{value === 'published' ? '已发布' : value === 'draft' ? '草稿' : '已归档'}</Tag> },
    { title: '操作', key: 'actions', width: 170, fixed: 'right', render: (_, record) => <Space><Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditor(record)}>编辑</Button><Button type="link" size="small" onClick={() => publish.mutate(record)}>{record.status === 'published' ? '归档' : '发布'}</Button></Space> },
  ];

  return (
    <div className="page-container">
      <PageHeader eyebrow="CONFIGURATION" title="红线条款" description="企业级与产品级红线同时生效，冲突时采用更严格立场；风险接受始终由人完成。" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor()}>新增红线</Button>} />
      <div className="config-notice">AI 仅提供风险与策略建议，不自动修改红线，也不自动接受或解决风险。</div>
      {query.error ? <QueryError error={query.error as Error} retry={() => void query.refetch()} /> : <Table<RedlineRule> rowKey="id" loading={query.isLoading} dataSource={items(query.data)} columns={columns} scroll={{ x: 1220 }} pagination={{ pageSize: 20 }} locale={{ emptyText: <EmptyState description="尚未配置红线条款" /> }} />}

      <Modal title={editing?.status === 'published' ? `基于 V${editing.revision_no} 新建修订` : editing ? `编辑红线 · V${editing.revision_no}` : '新增红线规则'} open={editing !== undefined} onCancel={() => setEditing(undefined)} onOk={() => form.submit()} confirmLoading={save.isPending} width={720} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(values) => save.mutate(values)} initialValues={{ scope_type: 'company', category: '合同责任', legal_review: true, revision_no: 1, status: 'draft', condition_text: '{\n  "field": "liability_cap",\n  "operator": "less_than",\n  "value": "contract_amount"\n}' }}>
          <div className="form-grid two-columns">
            <Form.Item name="scope_type" label="规则层级" rules={[{ required: true }]}><Select options={[{ value: 'company', label: '企业级' }, { value: 'product', label: '产品级' }]} /></Form.Item>
            <Form.Item name="scope_id" label="适用企业 / 产品"><Select allowClear options={(scopeType === 'product' ? items(products.data) : items(companies.data)).map((entry) => ({ value: entry.id, label: entry.name }))} /></Form.Item>
            <Form.Item name="category" label="风险类别" rules={[{ required: true }]}><Select options={['合同责任', '付款条件', '服务承诺', '知识产权', '数据安全', '违约责任', '其他'].map((value) => ({ value, label: value }))} /></Form.Item>
            <Form.Item name="revision_no" label="修订号" rules={[{ required: true }]}><InputNumber min={1} precision={0} className="full-width" /></Form.Item>
          </div>
          <Form.Item name="position" label="不可让步立场" rules={[{ required: true }]}><Input.TextArea rows={3} placeholder="明确企业可接受的边界，不填写模糊口号。" /></Form.Item>
          <Form.Item name="condition_text" label="触发条件（JSON 对象）" rules={[{ required: true }, { validator: (_, value: string) => { try { const parsed = JSON.parse(value) as unknown; return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? Promise.resolve() : Promise.reject(new Error('请输入 JSON 对象')); } catch { return Promise.reject(new Error('JSON 格式无效')); } } }]}><Input.TextArea rows={6} className="code-editor" spellCheck={false} /></Form.Item>
          <Form.Item name="action" label="建议处置动作" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <div className="form-grid two-columns align-center">
            <Form.Item name="legal_review" label="需要法务复核" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="status" label="规则状态"><Select options={[{ value: 'draft', label: '草稿' }, { value: 'published', label: '已发布' }, { value: 'archived', label: '已归档' }]} /></Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
