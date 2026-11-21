import { useMemo, useState } from 'react';
import { App, Button, Descriptions, Space, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { AuditOutlined, BranchesOutlined, FileSearchOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '../app/api';
import { queryClient } from '../app/queryClient';
import { PageHeader, QueryError, TaskStatusTag } from '../components/Common';
import { RiskDispositionModal } from '../components/RiskDispositionModal';
import { SourceDialog } from '../components/SourceDialog';
import { dateTime, displayJson, projectStatus } from '../lib/format';
import { isActiveTask, items, queryKeys } from '../lib/query';
import { useProjectEvents } from '../lib/useProjectEvents';
import type { Requirement, Risk, ScoreAssessment } from '../types';

export default function AnalysisPage() {
  const { projectId = '' } = useParams();
  const { message } = App.useApp();
  useProjectEvents(projectId);
  const [source, setSource] = useState<Requirement>();
  const [risk, setRisk] = useState<Risk>();
  const [tab, setTab] = useState('requirements');
  const project = useQuery({ queryKey: queryKeys.project(projectId), queryFn: () => api.projects.get(projectId) });
  const workspace = useQuery({
    queryKey: queryKeys.workspace(projectId),
    queryFn: () => api.projects.workspace(projectId),
    refetchInterval: (query) => query.state.data?.tasks.some((task) => isActiveTask(task.status)) ? 4000 : false,
  });
  const requirements = useQuery({ queryKey: queryKeys.requirements(projectId), queryFn: () => api.projects.requirements(projectId) });
  const risks = useQuery({ queryKey: queryKeys.risks(projectId), queryFn: () => api.projects.risks(projectId) });
  const scores = useQuery({ queryKey: queryKeys.scores(projectId), queryFn: () => api.projects.scores(projectId) });

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.requirements(projectId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.risks(projectId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.scores(projectId) }),
    ]);
  };
  const analyze = useMutation({
    mutationFn: () => api.projects.analyze(projectId, project.data?.version),
    onSuccess: async (result) => {
      const failed = result.tasks?.some((task) => task.status === 'failed');
      if (failed) message.warning('AI 分析未完成，骨架与人工编辑不受影响，请在任务记录中查看原因');
      else message.success('已启动两次常规 AI 分析任务');
      await invalidate();
    },
    onError: (error) => message.error(error.message),
  });
  const resolveMapping = useMutation({
    mutationFn: () => api.projects.resolveMapping(projectId, project.data?.version),
    onSuccess: async (result) => {
      if (result.status === 'failed') message.warning('编排歧义任务未完成，现有章节结构不受影响');
      else message.success('已启动可选编排歧义任务');
      await invalidate();
    },
    onError: (error) => message.error(error.message),
  });

  const requirementRows = items(requirements.data);
  const riskRows = items(risks.data);
  const scoreRows = items(scores.data);
  const pendingRisks = riskRows.filter((item) => !item.disposition || item.disposition === 'pending').length;
  const clarificationRows = requirementRows.filter((item) => item.status === 'missing' || item.status === 'needs_review');
  const requirementColumns: ColumnsType<Requirement> = [
    { title: '编号', dataIndex: 'code', width: 130, render: (value) => <code>{value}</code> },
    { title: '类别 / 处理', key: 'category', width: 170, render: (_, record) => <div className="stacked-cell"><span>{record.category}</span><small>{record.response_type}</small></div> },
    { title: '条款内容', dataIndex: 'text', minWidth: 360 },
    { title: '强制性 / 分值', key: 'level', width: 130, render: (_, record) => <div className="stacked-cell"><span>{record.mandatory_level || '一般'}</span>{record.score_max !== undefined && <small>最高 {record.score_max} 分</small>}</div> },
    { title: '状态', dataIndex: 'status', width: 115, render: (value: string) => <Tag color={value === 'original' ? 'green' : value === 'needs_review' ? 'gold' : value === 'missing' ? 'red' : 'blue'}>{value === 'original' ? '原文明确' : value === 'inferred' ? '推断待核' : value === 'missing' ? '原文缺失' : '需要复核'}</Tag> },
    { title: '原文', key: 'source', width: 100, render: (_, record) => <Button type="link" size="small" icon={<FileSearchOutlined />} onClick={() => setSource(record)}>定位 {record.anchors?.length || 0}</Button> },
  ];
  const riskColumns: ColumnsType<Risk> = [
    { title: '等级', dataIndex: 'severity', width: 95, render: (value: string) => <Tag color={value === 'critical' || value === 'high' ? 'red' : value === 'medium' ? 'gold' : 'blue'}>{value === 'critical' ? '严重' : value === 'high' ? '高' : value === 'medium' ? '中' : '低'}</Tag> },
    { title: '类别 / 冲突', key: 'category', width: 180, render: (_, record) => <div className="stacked-cell"><span>{record.category}</span><small>{record.conflict_type}</small></div> },
    { title: 'AI 建议（非最终处置）', dataIndex: 'recommendation', minWidth: 330 },
    { title: '法务', dataIndex: 'legal_review', width: 90, render: (value: boolean) => value ? <Tag color="gold">需复核</Tag> : '—' },
    { title: '人工处置', key: 'disposition', width: 190, render: (_, record) => <div className="disposition-cell"><Tag color={!record.disposition || record.disposition === 'pending' ? 'gold' : 'green'}>{!record.disposition || record.disposition === 'pending' ? '待处置' : record.disposition}</Tag><Button size="small" onClick={() => setRisk(record)}>{record.disposition && record.disposition !== 'pending' ? '复核' : '处置'}</Button></div> },
  ];
  const scoreColumns: ColumnsType<ScoreAssessment> = [
    { title: '评分要求', dataIndex: 'requirement_text', minWidth: 340, render: (value, record) => value || record.requirement_id },
    { title: '可得分区间', key: 'score', width: 140, render: (_, record) => record.score_min === undefined || record.score_max === undefined ? <Tag>无法测算</Tag> : <strong>{record.score_min} — {record.score_max} 分</strong> },
    { title: '状态', dataIndex: 'status', width: 120, render: (value: string) => <Tag color={value === 'confirmed' ? 'green' : 'gold'}>{value}</Tag> },
  ];
  const error = project.error || workspace.error || requirements.error || risks.error || scores.error;
  const taskSummary = useMemo(() => (workspace.data?.tasks || []).slice(0, 4), [workspace.data]);

  return (
    <div className="page-container analysis-page">
      <PageHeader
        eyebrow={project.data?.code || 'ANALYSIS'}
        title={project.data?.name || '招标分析'}
        description={<Space split="·">{project.data?.customer_name}<span>{project.data?.procurement_type}</span><Tag color={projectStatus[project.data?.status || '']?.color}>{projectStatus[project.data?.status || '']?.label || project.data?.status}</Tag></Space>}
        extra={<Space><Button icon={<BranchesOutlined />} loading={resolveMapping.isPending} onClick={() => resolveMapping.mutate()}>处理编排歧义</Button><Button type="primary" icon={<ThunderboltOutlined />} loading={analyze.isPending} onClick={() => analyze.mutate()}>启动 AI 分析</Button></Space>}
      />
      <div className="analysis-boundary"><AuditOutlined /><span>AI 只负责语义提取、风险与策略分析；不生成标书正文，不自动确认风险或章节。</span></div>
      {error && <QueryError error={error as Error} retry={() => void invalidate()} />}
      <section className="analysis-status-strip">
        <div><span>已提取条款</span><strong>{requirementRows.length}</strong></div>
        <div><span>待处置风险</span><strong className={pendingRisks ? 'warning-text' : ''}>{pendingRisks}</strong></div>
        <div><span>待澄清信息</span><strong>{clarificationRows.length}</strong></div>
        <div className="task-summary"><span>最近任务</span>{taskSummary.length ? taskSummary.map((task) => <div className="task-inline" key={task.id}><span>{task.task_type}</span><TaskStatusTag status={task.status} /></div>) : <small>暂无任务</small>}</div>
      </section>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'requirements', label: `关键信息（${requirementRows.length}）`, children: <Table<Requirement> rowKey="id" columns={requirementColumns} dataSource={requirementRows} loading={requirements.isLoading} scroll={{ x: 1100 }} expandable={{ expandedRowRender: (record) => <pre className="json-detail">{displayJson(record.normalized_json)}</pre> }} pagination={{ pageSize: 20 }} /> },
          { key: 'risks', label: `风险与策略（${riskRows.length}）`, children: <Table<Risk> rowKey="id" columns={riskColumns} dataSource={riskRows} loading={risks.isLoading} scroll={{ x: 1000 }} pagination={{ pageSize: 20 }} /> },
          { key: 'scores', label: `评分证据（${scoreRows.length}）`, children: <Table<ScoreAssessment> rowKey="id" columns={scoreColumns} dataSource={scoreRows} loading={scores.isLoading} expandable={{ expandedRowRender: (record) => <Descriptions size="small" column={1} items={[{ key: 'evidence', label: '现有证据', children: <pre>{displayJson(record.evidence_json)}</pre> }, { key: 'gap', label: '证据缺口', children: <pre>{displayJson(record.gap_json)}</pre> }]} /> }} pagination={{ pageSize: 20 }} /> },
          { key: 'clarifications', label: `待澄清（${clarificationRows.length}）`, children: <Table<Requirement> rowKey="id" columns={requirementColumns} dataSource={clarificationRows} loading={requirements.isLoading} scroll={{ x: 1100 }} pagination={{ pageSize: 20 }} /> },
          { key: 'tasks', label: '任务记录', children: <Table rowKey="id" dataSource={workspace.data?.tasks || []} columns={[{ title: '任务类型', dataIndex: 'task_type' }, { title: '状态', dataIndex: 'status', render: (value) => <TaskStatusTag status={value} /> }, { title: '进度', dataIndex: 'progress', render: (value) => value === undefined ? '—' : `${value}%` }, { title: '错误码', dataIndex: 'error_code', render: (value) => value || '—' }, { title: '创建时间', dataIndex: 'created_at', render: dateTime }, { title: '完成时间', dataIndex: 'finished_at', render: dateTime }]} pagination={false} /> },
        ]}
      />
      <SourceDialog requirement={source} open={Boolean(source)} onClose={() => setSource(undefined)} />
      <RiskDispositionModal risk={risk} open={Boolean(risk)} onClose={() => setRisk(undefined)} onSuccess={invalidate} />
    </div>
  );
}
