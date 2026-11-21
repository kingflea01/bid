import { useEffect, useState } from 'react';
import { App, Button, Form, Input, Modal, Select, Tag, Upload } from 'antd';
import type { UploadFile } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { api, type GapResolutionInput } from '../../app/api';
import type { Gap } from '../../types';
import { EmptyState } from '../Common';

export function GapList({ gaps, onResolved }: { gaps: Gap[]; onResolved: () => void | Promise<void> }) {
  const { message } = App.useApp();
  const [resolving, setResolving] = useState<Gap>();
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [form] = Form.useForm<GapResolutionInput>();
  const resolutionType = Form.useWatch('resolution_type', form);
  useEffect(() => { if (!resolving) { setFiles([]); form.resetFields(); } }, [resolving, form]);
  const resolve = useMutation({
    mutationFn: (values: GapResolutionInput) => api.gaps.resolve(resolving!.id, values, files[0]?.originFileObj as File | undefined),
    onSuccess: async () => { message.success('缺口已依据实际解决材料关闭'); await onResolved(); setResolving(undefined); },
    onError: (error) => message.error(error.message),
  });
  if (!gaps.length) return <EmptyState description="当前章节没有缺口" />;
  return (
    <div className="gap-list">
      {gaps.map((gap) => <article className="gap-item" key={gap.id}><div><Tag color={gap.blocking ? 'red' : 'gold'}>{gap.blocking ? '导出阻断' : '一般缺口'}</Tag><Tag>{gap.gap_type}</Tag></div><strong>{gap.title}</strong><p>{gap.status === 'resolved' || gap.status === 'closed' ? '已依据人工提交的解决材料关闭。' : '需选择素材、上传附件或填写实际解决依据。'}</p>{gap.status !== 'resolved' && gap.status !== 'closed' && <Button size="small" onClick={() => setResolving(gap)}>提交解决依据</Button>}</article>)}
      <Modal title="关闭内容缺口" open={Boolean(resolving)} onCancel={() => setResolving(undefined)} onOk={() => form.submit()} confirmLoading={resolve.isPending} destroyOnClose>
        <div className="risk-modal-summary"><strong>{resolving?.title}</strong><p>不能只点击“已解决”；必须提供可追溯的实际依据。</p></div>
        <Form form={form} layout="vertical" initialValues={{ resolution_type: 'text' }} onFinish={(values) => {
          if (values.resolution_type === 'attachment' && !files.length && !values.attachment_id) { message.warning('请选择或填写附件'); return; }
          if (values.resolution_type === 'asset' && !values.asset_revision_id) { message.warning('请填写已发布素材修订 ID'); return; }
          resolve.mutate(values);
        }}>
          <Form.Item name="resolution_type" label="解决方式" rules={[{ required: true }]}><Select options={[{ value: 'text', label: '实际说明 / 澄清依据' }, { value: 'asset', label: '选择已发布素材修订' }, { value: 'attachment', label: '上传或引用附件' }]} /></Form.Item>
          {resolutionType === 'asset' && <Form.Item name="asset_revision_id" label="已发布素材修订 ID" rules={[{ required: true }]}><Input placeholder="输入经核验的 asset_revision_id" /></Form.Item>}
          {resolutionType === 'attachment' && <><Form.Item name="attachment_id" label="已有附件 ID（可选）"><Input placeholder="上传新文件时无需填写" /></Form.Item><Form.Item label="解决附件"><Upload maxCount={1} fileList={files} beforeUpload={(file) => { setFiles([file]); return false; }} onRemove={() => setFiles([])}><Button icon={<PaperClipOutlined />}>选择附件</Button></Upload></Form.Item></>}
          <Form.Item name="note" label="实际解决依据" rules={[{ required: true, min: 5, message: '请填写至少 5 个字的解决依据' }]}><Input.TextArea rows={4} placeholder="说明材料来源、适用范围与复核结果" /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
