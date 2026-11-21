import { useEffect, useState } from 'react';
import { Alert, App, Form, Input, Modal, Select, Switch } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../app/api';
import { displayJson } from '../../lib/format';
import type { ProjectFact } from '../../types';

export function FactEditorDialog({ fact, projectId, open, onClose, onUpdated }: { fact?: ProjectFact; projectId: string; open: boolean; onClose: () => void; onUpdated: () => void | Promise<void> }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [valueType, setValueType] = useState('string');
  useEffect(() => {
    if (fact && open) {
      setValueType(fact.value_type);
      form.setFieldsValue({ value: typeof fact.value_json === 'string' ? fact.value_json : displayJson(fact.value_json), value_type: fact.value_type, confirmed: fact.status === 'confirmed' });
    }
  }, [fact, open, form]);
  const mutation = useMutation({
    mutationFn: (values: { value: string; value_type: string; confirmed: boolean }) => {
      let value_json: unknown = values.value;
      if (values.value_type === 'number') value_json = Number(values.value);
      if (values.value_type === 'boolean') value_json = values.value === 'true';
      if (values.value_type === 'json') value_json = JSON.parse(values.value);
      return api.projects.updateFact(projectId, fact!.fact_key, { value_json, value_type: values.value_type, version: fact!.version, status: values.confirmed ? 'confirmed' : 'unconfirmed' });
    },
    onSuccess: async () => { message.success('统一事实已更新，引用章节已交由后端标记待复核'); await onUpdated(); onClose(); },
    onError: (error) => message.error(error.message),
  });
  return (
    <Modal title={`统一事实 · ${fact?.fact_key || ''}`} open={open} onCancel={onClose} onOk={() => form.submit()} confirmLoading={mutation.isPending} destroyOnClose>
      <Alert type="warning" showIcon message="修改或确认状态变化会影响所有引用此事实的章节，不会只更新当前卡片。" />
      <Form form={form} layout="vertical" onFinish={(values) => {
        if (values.value_type === 'number' && !Number.isFinite(Number(values.value))) { message.error('请输入有效数字'); return; }
        if (values.value_type === 'json') { try { JSON.parse(values.value); } catch { message.error('JSON 格式无效'); return; } }
        mutation.mutate(values);
      }} className="fact-editor-form">
        <Form.Item name="value_type" label="值类型" rules={[{ required: true }]}><Select onChange={setValueType} options={['string', 'number', 'boolean', 'date', 'json'].map((value) => ({ value, label: value }))} /></Form.Item>
        <Form.Item name="value" label="事实值" rules={[{ required: true }]}>{valueType === 'boolean' ? <Select options={[{ value: 'true', label: '是' }, { value: 'false', label: '否' }]} /> : valueType === 'json' ? <Input.TextArea rows={5} className="code-editor" /> : <Input />}</Form.Item>
        <Form.Item name="confirmed" label="已核验并确认此事实" valuePropName="checked"><Switch /></Form.Item>
      </Form>
      <div className="modal-footnote">来源：{fact?.source_type}{fact?.source_id ? ` · ${fact.source_id}` : ''}</div>
    </Modal>
  );
}
