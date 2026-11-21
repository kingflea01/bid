import { useState } from 'react';
import { App, Button, Tabs, Tag, Timeline } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../app/api';
import { dateTime } from '../../lib/format';
import { useWorkspaceStore, type InspectorTab } from '../../stores/workspaceStore';
import type { Activity, Candidate, Gap, ProjectSection, Requirement, Risk } from '../../types';
import { SectionStatusTag } from '../Common';
import { RiskDispositionModal } from '../RiskDispositionModal';
import { CandidateList } from './CandidateList';
import { DiffDialog } from './DiffDialog';
import { GapList } from './GapList';
import { RequirementList } from './RequirementList';

export function VersionInspector({
  section,
  projectVersion,
  requirements,
  gaps,
  risks,
  activities,
  onChanged,
}: {
  section: ProjectSection;
  projectVersion: number;
  requirements: Requirement[];
  gaps: Gap[];
  risks: Risk[];
  activities: Activity[];
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const tab = useWorkspaceStore((state) => state.inspectorTab);
  const setTab = useWorkspaceStore((state) => state.setInspectorTab);
  const setInspectorOpen = useWorkspaceStore((state) => state.setInspectorOpen);
  const setImpactedSections = useWorkspaceStore((state) => state.setImpactedSections);
  const [candidate, setCandidate] = useState<Candidate>();
  const [risk, setRisk] = useState<Risk>();
  const isGroup = section.content_mode === 'group';
  const openBlockingGap = gaps.some((gap) => gap.blocking && gap.status !== 'resolved' && gap.status !== 'closed');
  const confirm = useMutation({
    mutationFn: () => api.sections.confirm(section.id, { selected_revision_id: section.selected_revision_id, version: section.version }),
    onSuccess: async () => { message.success(`“${section.title}”当前修订已确认`); await onChanged(); },
    onError: (error) => message.error(error.message),
  });
  const sectionActivities = activities.filter((activity) => activity.section_id === section.id || activity.entity_id === section.id);

  return (
    <div className="version-inspector">
      <div className="inspector-heading"><div className="inspector-kicker"><span>当前章节</span><Button className="inspector-close" type="text" size="small" icon={<CloseOutlined />} onClick={() => setInspectorOpen(false)} /></div><div><strong>{section.title}</strong>{!isGroup && <SectionStatusTag section={section} />}</div><code>{section.section_key}</code></div>
      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as InspectorTab)}
        items={[
          { key: 'candidates', label: '候选版本' },
          { key: 'requirements', label: `条款 ${requirements.length}` },
          { key: 'issues', label: `问题 ${gaps.length + risks.length}` },
          { key: 'activity', label: '记录' },
        ]}
      />
      <div className="inspector-scroll">
        {tab === 'candidates' && (isGroup ? <div className="empty-inspector">这是结构分组，不直接承载正文。<br />请选择子章节查看候选内容。</div> : <CandidateList section={section} onCompare={setCandidate} />)}
        {tab === 'requirements' && <RequirementList requirements={requirements} />}
        {tab === 'issues' && <div className="issues-panel"><section><div className="inspector-section-heading"><strong>内容与附件缺口</strong><span>{gaps.length}</span></div><GapList gaps={gaps} onResolved={onChanged} /></section><section><div className="inspector-section-heading"><strong>关联风险</strong><span>{risks.length}</span></div>{risks.length ? risks.map((item) => <article className="inspector-risk" key={item.id}><div><Tag color={item.severity === 'high' || item.severity === 'critical' ? 'red' : 'gold'}>{item.severity}</Tag><span>{item.category}</span></div><p>{item.recommendation}</p><Button size="small" onClick={() => setRisk(item)}>{!item.disposition || item.disposition === 'pending' ? '人工处置' : '查看 / 复核处置'}</Button></article>) : <div className="inline-empty">无关联风险</div>}</section></div>}
        {tab === 'activity' && (sectionActivities.length ? <Timeline items={sectionActivities.map((activity) => ({ key: activity.id, children: <div className="activity-entry"><strong>{activity.detail_json && typeof activity.detail_json.message === 'string' ? activity.detail_json.message : activity.action}</strong><span>{activity.actor_name || activity.actor_id || '系统'} · {dateTime(activity.created_at)}</span></div> }))} /> : <div className="empty-inspector">版本切换、结构调整与确认记录将在这里显示。</div>)}
      </div>
      <footer className="inspector-footer">
        {isGroup ? <span>分组状态由后代内容章节汇总。</span> : <><Button block type={section.review_status === 'confirmed' ? 'default' : 'primary'} icon={<CheckOutlined />} disabled={section.review_status === 'confirmed' || openBlockingGap || !section.selected_revision_id} loading={confirm.isPending} onClick={() => confirm.mutate()}>{section.review_status === 'confirmed' ? '当前修订已确认' : openBlockingGap ? '请先关闭阻塞缺口' : !section.selected_revision_id ? '请先选择内容版本' : '确认当前章节版本'}</Button><small>切换版本、编辑正文或修改引用事实后，需要重新确认。</small></>}
      </footer>
      <DiffDialog section={section} candidate={candidate} projectVersion={projectVersion} open={Boolean(candidate)} onClose={() => setCandidate(undefined)} onSelected={(ids) => { setImpactedSections(ids); void onChanged(); }} />
      <RiskDispositionModal risk={risk} open={Boolean(risk)} onClose={() => setRisk(undefined)} onSuccess={onChanged} />
    </div>
  );
}
