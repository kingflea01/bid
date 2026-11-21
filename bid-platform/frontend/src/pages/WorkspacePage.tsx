import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Progress, Space, Tooltip } from 'antd';
import {
  CameraOutlined,
  DownloadOutlined,
  ExpandOutlined,
  MenuOutlined,
  SlidersOutlined,
  ColumnWidthOutlined,
  PicLeftOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../app/api';
import { queryClient } from '../app/queryClient';
import { EmptyState, QueryError } from '../components/Common';
import { ChapterCardList } from '../components/workspace/ChapterCardList';
import { ChapterTree } from '../components/workspace/ChapterTree';
import { ExportDialog } from '../components/workspace/ExportDialog';
import { FactEditorDialog } from '../components/workspace/FactEditorDialog';
import { VersionInspector } from '../components/workspace/VersionInspector';
import { isActiveTask, queryKeys } from '../lib/query';
import { useProjectEvents } from '../lib/useProjectEvents';
import { canIndent, canOutdent, contentSections, deriveExportReadiness, flattenSections, moveSectionInList } from '../lib/workspace';
import { useWorkspaceStore, type InspectorTab } from '../stores/workspaceStore';
import type { ContentBlock, ProjectFact, ProjectSection, WorkspaceData } from '../types';

export default function WorkspacePage() {
  const { projectId = '' } = useParams();
  const { message } = App.useApp();
  useProjectEvents(projectId);
  const workspace = useQuery({
    queryKey: queryKeys.workspace(projectId),
    queryFn: () => api.projects.workspace(projectId),
    refetchInterval: (query) => query.state.data?.tasks.some((task) => isActiveTask(task.status)) ? 4000 : false,
  });
  const activeId = useWorkspaceStore((state) => state.activeSectionId);
  const setActive = useWorkspaceStore((state) => state.setActiveSection);
  const setInspectorTab = useWorkspaceStore((state) => state.setInspectorTab);
  const expandAllCards = useWorkspaceStore((state) => state.expandAllCards);
  const impactedIds = useWorkspaceStore((state) => state.impactedSectionIds);
  const clearImpacts = useWorkspaceStore((state) => state.clearImpactedSections);
  const treeOpen = useWorkspaceStore((state) => state.treeOpen);
  const inspectorOpen = useWorkspaceStore((state) => state.inspectorOpen);
  const setTreeOpen = useWorkspaceStore((state) => state.setTreeOpen);
  const setInspectorOpen = useWorkspaceStore((state) => state.setInspectorOpen);
  const reset = useWorkspaceStore((state) => state.reset);
  const [exportOpen, setExportOpen] = useState(false);
  const [fact, setFact] = useState<ProjectFact>();
  const [lastSaved, setLastSaved] = useState<string>();

  useEffect(() => { reset(); return () => reset(); }, [projectId, reset]);
  useEffect(() => {
    if (!activeId && workspace.data?.sections.length) {
      const first = workspace.data.sections.find((section) => section.content_mode !== 'group') || workspace.data.sections[0];
      setActive(first.id);
    }
  }, [activeId, workspace.data, setActive]);

  const invalidate = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
    ]);
    setLastSaved(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }));
  }, [projectId]);

  const move = useMutation({
    mutationFn: ({ section, parentId, position }: { section: ProjectSection; parentId: string | null; position: number }) =>
      api.sections.move(section.id, { parent_id: parentId, position, version: section.version, project_version: workspace.data!.project.version }),
    onMutate: async ({ section, parentId, position }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.workspace(projectId) });
      const previous = queryClient.getQueryData<WorkspaceData>(queryKeys.workspace(projectId));
      queryClient.setQueryData<WorkspaceData>(queryKeys.workspace(projectId), (data) => data ? { ...data, sections: moveSectionInList(data.sections, section.id, parentId, position) } : data);
      return { previous };
    },
    onError: (error, _, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.workspace(projectId), context.previous);
      message.error(error instanceof ApiError && error.status === 409 ? '项目结构已更新，请刷新后重试' : error.message);
    },
    onSuccess: () => message.success('章节结构已保存，显示编号已更新'),
    onSettled: invalidate,
  });
  const saveRevision = useMutation({
    mutationFn: ({ section, blocks }: { section: ProjectSection; blocks: ContentBlock[] }) =>
      api.sections.saveRevision(section.id, { content_json: blocks, base_version: section.version, version: section.version }),
    onSuccess: invalidate,
  });
  const rename = useMutation({
    mutationFn: ({ section, title }: { section: ProjectSection; title: string }) => api.sections.update(section.id, { title, version: section.version }),
    onSuccess: invalidate,
  });
  const snapshot = useMutation({
    mutationFn: () => api.snapshots.create(projectId, { version: workspace.data!.project.version }),
    onSuccess: async (created) => {
      message.success(`快照 V${created.snapshot_no} 已保存`);
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(projectId) });
      await invalidate();
    },
    onError: (error) => message.error(error.message),
  });

  const flat = useMemo(() => flattenSections(workspace.data?.sections || []), [workspace.data]);
  const activeEntry = flat.find((entry) => entry.section.id === activeId);
  const activeSection = activeEntry?.section;
  const selectSection = useCallback((id: string) => {
    setActive(id);
    setTreeOpen(false);
    window.requestAnimationFrame(() => document.getElementById(`chapter-card-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }, [setActive, setTreeOpen]);
  const openInspector = useCallback((sectionId: string, tab: InspectorTab) => {
    setActive(sectionId);
    setInspectorTab(tab);
    setInspectorOpen(true);
  }, [setActive, setInspectorTab, setInspectorOpen]);
  const handleSave = useCallback(async (section: ProjectSection, blocks: ContentBlock[]) => {
    await saveRevision.mutateAsync({ section, blocks });
  }, [saveRevision]);
  const handleRename = useCallback(async (section: ProjectSection, title: string) => {
    await rename.mutateAsync({ section, title });
  }, [rename]);
  const indent = () => {
    if (!activeEntry || !canIndent(activeEntry)) return;
    const previous = activeEntry.siblings[activeEntry.index - 1];
    const position = (workspace.data?.sections || []).filter((section) => section.parent_id === previous.id).length;
    move.mutate({ section: activeEntry.section, parentId: previous.id, position });
  };
  const outdent = () => {
    if (!activeEntry?.parent || !canOutdent(activeEntry)) return;
    move.mutate({ section: activeEntry.section, parentId: activeEntry.parent.parent_id, position: activeEntry.parent.position + 1 });
  };

  if (workspace.isLoading) return <div className="workspace-loading"><EmptyState description="正在读取章节工作区…" /></div>;
  if (workspace.error || !workspace.data) return <div className="page-container"><QueryError error={(workspace.error as Error) || new Error('工作区为空')} retry={() => void workspace.refetch()} /></div>;
  const data = workspace.data;
  const contents = contentSections(data.sections);
  const confirmed = contents.filter((section) => section.review_status === 'confirmed').length;
  const openGaps = data.gaps.filter((gap) => gap.status !== 'resolved' && gap.status !== 'closed');
  const readiness = deriveExportReadiness(data);
  const activeRequirements = activeSection ? data.requirements.filter((requirement) => requirement.section_id === activeSection.id) : [];
  const activeGaps = activeSection ? data.gaps.filter((gap) => gap.section_id === activeSection.id) : [];
  const activeRisks = activeSection ? data.risks.filter((risk) => activeRequirements.some((requirement) => requirement.id === risk.requirement_id)) : [];

  return (
    <div className="workspace-page">
      <header className="workspace-project-strip">
        <div className="workspace-project-title"><div><Link to="/projects">应标项目</Link><span>/</span><code>{data.project.code}</code></div><h1>{data.project.name}{(data.project.package_name || data.project.package) && <span>{data.project.package_name || data.project.package}</span>}</h1></div>
        <div className="workspace-project-metrics"><div><span>内容章节</span><strong>{contents.length}</strong></div><div><span>待处理缺口</span><strong className={openGaps.length ? 'warning-text' : ''}>{openGaps.length}</strong></div><div className="confirmation-metric"><span>人工确认 <strong>{confirmed} / {contents.length}</strong></span><Progress percent={contents.length ? Math.round(confirmed / contents.length * 100) : 0} showInfo={false} size="small" /></div></div>
        <Space><Button icon={<CameraOutlined />} loading={snapshot.isPending} onClick={() => snapshot.mutate()}>保存快照</Button><Button type="primary" icon={<DownloadOutlined />} onClick={() => setExportOpen(true)}>导出</Button></Space>
      </header>
      <div className="workspace-grid">
        <aside className={`workspace-left ${treeOpen ? 'mobile-open' : ''}`}>
          <ChapterTree sections={data.sections} requirements={data.requirements} openGapCount={openGaps.length} onMove={(section, parentId, position) => move.mutate({ section, parentId, position })} onSelect={selectSection} />
        </aside>
        <main className="workspace-main">
          <div className="workspace-toolbar">
            <div><Button className="workspace-mobile-toggle" type="text" icon={<MenuOutlined />} onClick={() => setTreeOpen(true)} /><strong>卡片式初稿</strong><span>{saveRevision.isPending || move.isPending ? '正在保存…' : `所有更改已保存${lastSaved ? ` · ${lastSaved}` : ''}`}</span></div>
            <Space size={2}>
              <Tooltip title="减少层级"><Button type="text" icon={<PicLeftOutlined />} disabled={!canOutdent(activeEntry) || move.isPending} onClick={outdent} /></Tooltip>
              <Tooltip title="成为上一章节的子章节"><Button type="text" icon={<ColumnWidthOutlined />} disabled={!canIndent(activeEntry) || move.isPending} onClick={indent} /></Tooltip>
              <span className="toolbar-divider" />
              <Button type="text" icon={<ExpandOutlined />} onClick={expandAllCards}>全部展开</Button>
              <Button className="workspace-mobile-toggle" type="text" icon={<SlidersOutlined />} onClick={() => setInspectorOpen(true)} />
            </Space>
          </div>
          {impactedIds.length > 0 && <Alert className="impact-alert" type="warning" showIcon closable onClose={clearImpacts} message={`版本切换影响了 ${impactedIds.length} 个章节`} description="当前及关联章节已标记为待确认或待复核，请逐项检查。" action={<Button size="small" onClick={() => { const id = impactedIds.find((item) => item !== activeId) || impactedIds[0]; if (id) selectSection(id); }}>查看影响</Button>} />}
          <ChapterCardList entries={flat} data={data} onFactEdit={setFact} onSave={handleSave} onRename={handleRename} onOpenInspector={openInspector} />
        </main>
        <aside className={`workspace-right ${inspectorOpen ? 'mobile-open' : ''}`}>
          {activeSection ? <VersionInspector key={activeSection.id} section={activeSection} projectVersion={data.project.version} requirements={activeRequirements} gaps={activeGaps} risks={activeRisks} activities={data.activities || []} onChanged={invalidate} /> : <EmptyState description="请选择一个章节" />}
        </aside>
      </div>
      {(treeOpen || inspectorOpen) && <button className="workspace-mobile-backdrop" aria-label="关闭侧栏" onClick={() => { setTreeOpen(false); setInspectorOpen(false); }} />}
      <ExportDialog projectId={projectId} workspace={data} open={exportOpen} onClose={() => setExportOpen(false)} onCreated={() => setLastSaved(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))} />
      <FactEditorDialog fact={fact} projectId={projectId} open={Boolean(fact)} onClose={() => setFact(undefined)} onUpdated={invalidate} />
      {!readiness.can_export_review && <div className="export-unavailable-note">当前快照状态由服务端复核后才能导出。</div>}
    </div>
  );
}
