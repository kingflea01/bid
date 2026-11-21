import { useState } from 'react';
import { App, Button, Form, Input, Modal, Space, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { CameraOutlined, DownloadOutlined, ExportOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '../app/api';
import { queryClient } from '../app/queryClient';
import { PageHeader, QueryError, TaskStatusTag } from '../components/Common';
import { ExportDialog } from '../components/workspace/ExportDialog';
import { dateTime, displayJson } from '../lib/format';
import { isActiveTask, items, queryKeys } from '../lib/query';
import { useProjectEvents } from '../lib/useProjectEvents';
import type { ExportTask, Snapshot } from '../types';

export default function ExportCenterPage() {
  const { projectId = '' } = useParams();
  const { message } = App.useApp();
  useProjectEvents(projectId);
  const [exportOpen, setExportOpen] = useState(false);
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [form] = Form.useForm();
  const project = useQuery({ queryKey: queryKeys.project(projectId), queryFn: () => api.projects.get(projectId) });
  const workspace = useQuery({ queryKey: queryKeys.workspace(projectId), queryFn: () => api.projects.workspace(projectId) });
  const snapshots = useQuery({ queryKey: queryKeys.snapshots(projectId), queryFn: () => api.snapshots.list(projectId) });
  const exports = useQuery({
    queryKey: queryKeys.exports(projectId),
    queryFn: () => api.exports.list(projectId),
    refetchInterval: (query) => items(query.state.data).some((task) => isActiveTask(task.status)) ? 3500 : false,
  });
  const createSnapshot = useMutation({
    mutationFn: (values: { label?: string }) => api.snapshots.create(projectId, { ...values, version: workspace.data!.project.version }),
    onSuccess: async (snapshot) => { message.success(`快照 V${snapshot.snapshot_no} 已保存`); setSnapshotOpen(false); form.resetFields(); await Promise.all([queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(projectId) }), queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectId) })]); },
    onError: (error) => message.error(error.message),
  });
  const download = useMutation({
    mutationFn: (task: ExportTask) => api.exports.download(task.id, `${project.data?.code || 'bid'}-V${task.snapshot_no || ''}-${task.export_kind}.${task.format}`),
    onError: (error) => message.error(error.message),
  });

  const snapshotColumns: ColumnsType<Snapshot> = [
    { title: '快照', dataIndex: 'snapshot_no', width: 100, render: (value) => <strong>V{value}</strong> },
    { title: '说明', dataIndex: 'label', render: (value) => value || '项目快照' },
    { title: '创建人', dataIndex: 'created_by_name', width: 130, render: (value, record) => value || record.created_by },
    { title: '创建时间', dataIndex: 'created_at', width: 170, render: dateTime },
    { title: '正式门禁', dataIndex: 'formal_ready', width: 130, render: (value?: boolean) => value === undefined ? <Tag>以导出时 QA 为准</Tag> : <Tag color={value ? 'green' : 'red'}>{value ? '已通过' : '未通过'}</Tag> },
    { title: 'QA 摘要', dataIndex: 'qa_json', ellipsis: true, render: (value) => <span className="json-inline">{displayJson(value).replace(/\s+/g, ' ').slice(0, 180)}</span> },
  ];
  const exportColumns: ColumnsType<ExportTask> = [
    { title: '任务', dataIndex: 'id', width: 140, render: (value: string) => <code>{value.slice(0, 12)}</code> },
    { title: '快照', dataIndex: 'snapshot_no', width: 90, render: (value) => value ? `V${value}` : '—' },
    { title: '类型', dataIndex: 'export_kind', width: 110, render: (value: string) => <Tag color={value === 'formal' ? 'blue' : 'gold'}>{value === 'formal' ? '正式版' : '审阅版'}</Tag> },
    { title: '格式', dataIndex: 'format', width: 80, render: (value: string) => value.toUpperCase() },
    { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <TaskStatusTag status={value} /> },
    { title: '创建时间', dataIndex: 'created_at', width: 165, render: dateTime },
    { title: '错误码', dataIndex: 'error_code', width: 130, render: (value) => value || '—' },
    { title: '操作', key: 'actions', width: 110, fixed: 'right', render: (_, record) => <Button type="link" size="small" icon={<DownloadOutlined />} disabled={record.status !== 'succeeded'} loading={download.isPending && download.variables?.id === record.id} onClick={() => download.mutate(record)}>下载</Button> },
  ];
  const error = project.error || workspace.error || snapshots.error || exports.error;

  return (
    <div className="page-container export-center-page">
      <PageHeader eyebrow={project.data?.code || 'EXPORTS'} title="快照与导出" description="快照保存完整项目状态；正式文件只能从通过确定性 QA 的人工确认快照生成。" extra={<Space><Button icon={<CameraOutlined />} disabled={!workspace.data} onClick={() => setSnapshotOpen(true)}>保存快照</Button><Button type="primary" icon={<ExportOutlined />} disabled={!workspace.data} onClick={() => setExportOpen(true)}>新建导出</Button></Space>} />
      {error && <QueryError error={error as Error} />}
      <Tabs items={[
        { key: 'exports', label: `导出任务（${items(exports.data).length}）`, children: <Table<ExportTask> rowKey="id" columns={exportColumns} dataSource={items(exports.data)} loading={exports.isLoading} scroll={{ x: 1000 }} expandable={{ expandedRowRender: (record) => <pre className="json-detail">{displayJson(record.qa_json)}</pre> }} pagination={{ pageSize: 20 }} /> },
        { key: 'snapshots', label: `不可变快照（${items(snapshots.data).length}）`, children: <Table<Snapshot> rowKey="id" columns={snapshotColumns} dataSource={items(snapshots.data)} loading={snapshots.isLoading} scroll={{ x: 1050 }} pagination={{ pageSize: 20 }} /> },
      ]} />
      <Modal title="保存项目快照" open={snapshotOpen} onCancel={() => setSnapshotOpen(false)} onOk={() => form.submit()} confirmLoading={createSnapshot.isPending} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={(values) => createSnapshot.mutate(values)}><Form.Item name="label" label="快照说明"><Input placeholder="例如：内部审阅前 / 正式提交版" maxLength={100} /></Form.Item></Form>
        <div className="modal-footnote">快照包含章节树、当前修订、事实、风险处置、缺口状态与配置基线，创建后不可修改。</div>
      </Modal>
      {workspace.data && <ExportDialog projectId={projectId} workspace={workspace.data} open={exportOpen} onClose={() => setExportOpen(false)} onCreated={() => undefined} />}
    </div>
  );
}
