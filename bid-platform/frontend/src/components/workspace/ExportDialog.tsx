import { useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Modal, Radio, Select, Space, Tag } from 'antd';
import { CameraOutlined, CheckCircleFilled, CloseCircleFilled, DownloadOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { items, queryKeys } from '../../lib/query';
import { deriveExportReadiness } from '../../lib/workspace';
import type { ExportTask, WorkspaceData } from '../../types';
import { QueryError } from '../Common';

export function ExportDialog({ projectId, workspace, open, onClose, onCreated }: { projectId: string; workspace: WorkspaceData; open: boolean; onClose: () => void; onCreated: (task: ExportTask) => void }) {
  const { message } = App.useApp();
  const snapshots = useQuery({ queryKey: queryKeys.snapshots(projectId), queryFn: () => api.snapshots.list(projectId), enabled: open });
  const [snapshotId, setSnapshotId] = useState<string>();
  const [kind, setKind] = useState<'review' | 'formal'>('review');
  const [format, setFormat] = useState<'docx' | 'pdf'>('docx');
  const readiness = deriveExportReadiness(workspace);
  const snapshotItems = useMemo(() => items(snapshots.data), [snapshots.data]);
  const selectedSnapshot = snapshotItems.find((snapshot) => snapshot.id === snapshotId);
  useEffect(() => { if (open) setSnapshotId(readiness.current_snapshot_id || snapshotItems[0]?.id); }, [open, readiness.current_snapshot_id, snapshotItems]);
  const createSnapshot = useMutation({
    mutationFn: () => api.snapshots.create(projectId, { label: '导出前快照', version: workspace.project.version }),
    onSuccess: async (snapshot) => { message.success(`快照 V${snapshot.snapshot_no} 已保存`); await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(projectId) }); setSnapshotId(snapshot.id); },
    onError: (error) => message.error(error.message),
  });
  const createExport = useMutation({
    mutationFn: () => api.exports.create(projectId, { snapshot_id: snapshotId!, export_kind: kind, format }),
    onSuccess: async (task) => { message.success('导出任务已创建'); onCreated(task); await queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectId) }); onClose(); },
    onError: (error) => message.error(error.message),
  });
  const canReview = readiness.can_export_review && Boolean(snapshotId);
  const canFormal = readiness.can_export_formal && Boolean(snapshotId) && selectedSnapshot?.formal_ready !== false;
  const allowed = kind === 'formal' ? canFormal : canReview;

  return (
    <Modal title="从不可变快照导出" open={open} onCancel={onClose} width={680} footer={<><div className="modal-footer-note">导出期间继续编辑，不影响已创建任务。</div><Space><Button onClick={onClose}>取消</Button><Button type="primary" icon={<DownloadOutlined />} disabled={!allowed} loading={createExport.isPending} onClick={() => createExport.mutate()}>创建{kind === 'formal' ? '正式版' : '审阅版'}导出</Button></Space></>} destroyOnClose>
      <div className="export-form-row"><label>项目快照</label><Select value={snapshotId} onChange={setSnapshotId} placeholder="请先保存快照" options={snapshotItems.map((snapshot) => ({ value: snapshot.id, label: `V${snapshot.snapshot_no} · ${snapshot.label || '项目快照'}${snapshot.formal_ready === false ? ' · 未通过正式门禁' : ''}` }))} /><Button icon={<CameraOutlined />} loading={createSnapshot.isPending} onClick={() => createSnapshot.mutate()}>保存当前快照</Button></div>
      {!snapshotItems.length && <Alert type="info" showIcon message="尚无快照，请先保存当前章节树、版本、事实与风险状态。" />}
      <div className="export-options"><div><label>导出类型</label><Radio.Group value={kind} onChange={(event) => setKind(event.target.value)} optionType="button" buttonStyle="solid" options={[{ value: 'review', label: '审阅版（含水印）' }, { value: 'formal', label: '正式版' }]} /></div><div><label>文件格式</label><Radio.Group value={format} onChange={(event) => setFormat(event.target.value)} optionType="button" buttonStyle="solid" options={[{ value: 'docx', label: 'DOCX' }, { value: 'pdf', label: 'PDF' }]} /></div></div>
      {kind === 'review' && <Alert type="warning" showIcon message="审阅版允许保留占位符与待确认章节，文件会带水印、缺口统计与快照号。" />}
      {kind === 'formal' && !canFormal && <Alert type="error" showIcon message="当前快照不满足正式版导出条件" description="请选择通过全部确定性 QA 的人工确认快照；前端禁用时，后端仍必须再次校验。" />}
      <div className="export-check-list">{readiness.checks.map((check) => <div key={check.key}>{check.passed ? <CheckCircleFilled className="success-text" /> : <CloseCircleFilled className={check.blocking ? 'danger-text' : 'warning-text'} />}<span>{check.label}</span><small>{check.detail}</small>{check.blocking && <Tag color={check.passed ? 'green' : 'red'}>{check.passed ? '通过' : '阻断'}</Tag>}</div>)}</div>
      {snapshots.error && <QueryError error={snapshots.error as Error} retry={() => void snapshots.refetch()} />}
    </Modal>
  );
}
