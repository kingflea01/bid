import { Alert, App, Form, Input, Modal, Select } from 'antd';
import { useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../app/api';
import type { Risk } from '../types';

export function RiskDispositionModal({ risk, open, onClose, onSuccess }: { risk?: Risk; open: boolean; onClose: () => void; onSuccess: () => void | Promise<void> }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  useEffect(() => {
    if (open) form.setFieldsValue({ disposition: risk?.disposition === 'pending' ? undefined : risk?.disposition, disposition_note: risk?.disposition_note });
  }, [open, risk, form]);
  const mutation = useMutation({
    mutationFn: (values: { disposition: string; disposition_note: string }) => api.risks.dispose(risk!.id, values),
    onSuccess: async () => { message.success('人工风险处置已保存'); await onSuccess(); onClose(); },
    onError: (error) => message.error(error.message),
  });
  return (
    <Modal title="人工风险处置" open={open} onCancel={onClose} onOk={() => form.submit()} confirmLoading={mutation.isPending} destroyOnClose>
      {risk && <div className="risk-modal-summary"><strong>{risk.category} · {risk.conflict_type}</strong><p>{risk.recommendation}</p></div>}
      <Alert type="warning" showIcon message="此处记录人工决定。AI 建议不会被自动视为已接受或已解决。" />
      <Form form={form} layout="vertical" onFinish={(values) => mutation.mutate(values)} className="risk-disposition-form">
        <Form.Item name="disposition" label="处置结论" rules={[{ required: true, message: '请选择处置结论' }]}>
          <Select options={[{ value: 'mitigated', label: '已缓解 / 已解决' }, { value: 'accepted', label: '审阅人接受风险' }, { value: 'rejected', label: '不采纳该风险建议' }, { value: 'resolved', label: '已澄清关闭' }]} />
        </Form.Item>
        <Form.Item name="disposition_note" label="处置依据与说明" rules={[{ required: true, min: 5, message: '请填写至少 5 个字的实际处置依据' }]}>
          <Input.TextArea rows={5} placeholder="记录澄清文件、合同修改、内部审批或不采纳理由。接受风险时必须具备相应权限。" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
