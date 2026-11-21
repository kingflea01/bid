import { useMemo, useState } from 'react';
import { Button, Input, Select, Tooltip } from 'antd';
import { DownOutlined, HolderOutlined, LockOutlined, RightOutlined, SearchOutlined } from '@ant-design/icons';
import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { ProjectSection, Requirement } from '../../types';
import { flattenSections, sectionStatus, type FlatSection } from '../../lib/workspace';
import { useWorkspaceStore } from '../../stores/workspaceStore';

interface ChapterTreeProps {
  sections: ProjectSection[];
  requirements: Requirement[];
  openGapCount: number;
  onMove: (section: ProjectSection, parentId: string | null, position: number) => void;
  onSelect: (id: string) => void;
}

function SortableTreeRow({ entry, hasChildren, dragDisabled, onSelect }: { entry: FlatSection; hasChildren: boolean; dragDisabled: boolean; onSelect: (id: string) => void }) {
  const { section, depth, number } = entry;
  const activeId = useWorkspaceStore((state) => state.activeSectionId);
  const collapsed = useWorkspaceStore((state) => state.collapsedTree[section.id]);
  const toggleTree = useWorkspaceStore((state) => state.toggleTree);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: section.id, disabled: section.locked || dragDisabled });
  const status = sectionStatus(section);
  return (
    <div
      ref={setNodeRef}
      className={`chapter-tree-row ${activeId === section.id ? 'active' : ''} ${isDragging ? 'dragging' : ''}`}
      style={{ transform: CSS.Transform.toString(transform), transition, paddingLeft: 5 + depth * 14 }}
      onClick={() => onSelect(section.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => { if (event.key === 'Enter') onSelect(section.id); }}
    >
      {hasChildren ? <Button className="tree-row-expander" type="text" size="small" icon={collapsed ? <RightOutlined /> : <DownOutlined />} onClick={(event) => { event.stopPropagation(); toggleTree(section.id); }} /> : <span className="tree-expander-placeholder" />}
      <Tooltip title={section.locked ? '招标固定章节，不可移动' : '拖动调整同级顺序'}>
        <span className={`tree-drag-handle ${section.locked ? 'locked' : ''}`} {...attributes} {...listeners}>{section.locked ? <LockOutlined /> : <HolderOutlined />}</span>
      </Tooltip>
      <span className={`tree-status-dot status-${status}`} />
      <span className="tree-number">{number}</span>
      <span className="tree-label">{section.title}</span>
    </div>
  );
}

export function ChapterTree({ sections, requirements, openGapCount, onMove, onSelect }: ChapterTreeProps) {
  const treeSearch = useWorkspaceStore((state) => state.treeSearch);
  const statusFilter = useWorkspaceStore((state) => state.statusFilter);
  const setTreeSearch = useWorkspaceStore((state) => state.setTreeSearch);
  const setStatusFilter = useWorkspaceStore((state) => state.setStatusFilter);
  const collapsedTree = useWorkspaceStore((state) => state.collapsedTree);
  const [dragged, setDragged] = useState<ProjectSection>();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const all = useMemo(() => flattenSections(sections), [sections]);
  const visibleIds = useMemo(() => {
    const keyword = treeSearch.trim().toLowerCase();
    if (!keyword && statusFilter === 'all') return new Set(sections.map((section) => section.id));
    const result = new Set<string>();
    all.forEach((entry) => {
      const matchesKeyword = !keyword || entry.section.title.toLowerCase().includes(keyword) || entry.section.section_key.toLowerCase().includes(keyword);
      const matchesStatus = statusFilter === 'all' || sectionStatus(entry.section) === statusFilter;
      if (matchesKeyword && matchesStatus) {
        result.add(entry.section.id);
        let parent = entry.parent;
        while (parent) {
          result.add(parent.id);
          parent = all.find((item) => item.section.id === parent?.id)?.parent;
        }
      }
    });
    return result;
  }, [all, sections, treeSearch, statusFilter]);
  const visible = all.filter((entry) => {
    if (!visibleIds.has(entry.section.id)) return false;
    if (treeSearch) return true;
    let parent = entry.parent;
    while (parent) {
      if (collapsedTree[parent.id]) return false;
      parent = all.find((item) => item.section.id === parent?.id)?.parent;
    }
    return true;
  });
  const confirmed = sections.filter((section) => section.content_mode !== 'group' && section.review_status === 'confirmed').length;
  const contentCount = sections.filter((section) => section.content_mode !== 'group').length;
  const mapped = requirements.filter((requirement) => requirement.mapping_status === 'confirmed').length;

  const dragStart = (event: DragStartEvent) => setDragged(sections.find((section) => section.id === event.active.id));
  const dragEnd = (event: DragEndEvent) => {
    setDragged(undefined);
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const source = all.find((entry) => entry.section.id === active.id);
    const target = all.find((entry) => entry.section.id === over.id);
    if (!source || !target || source.section.locked || target.section.locked || source.parent?.id !== target.parent?.id) return;
    const sorted = [...source.siblings].sort((a, b) => a.position - b.position);
    const reordered = arrayMove(sorted, sorted.findIndex((section) => section.id === active.id), sorted.findIndex((section) => section.id === over.id));
    onMove(source.section, source.parent?.id || null, reordered.findIndex((section) => section.id === active.id));
  };

  return (
    <div className="chapter-tree-panel">
      <div className="workspace-panel-heading"><div><strong>章节结构</strong><span>同级拖排 · 自动编号</span></div><LockOutlined title="锁定章节由招标结构约束" /></div>
      <div className="tree-tools">
        <Input prefix={<SearchOutlined />} value={treeSearch} onChange={(event) => setTreeSearch(event.target.value)} placeholder="搜索章节或稳定键" allowClear />
        <Select value={statusFilter} onChange={setStatusFilter} options={[{ value: 'all', label: '全部状态' }, { value: 'confirmed', label: '已确认' }, { value: 'unconfirmed', label: '待确认' }, { value: 'needs_review', label: '待复核' }, { value: 'gap', label: '有缺口' }, { value: 'empty', label: '待补内容' }]} />
      </div>
      <div className="tree-legend"><HolderOutlined /> 可拖动为企业补充章节 <LockOutlined /> 招标固定</div>
      <nav className="chapter-tree-scroll" aria-label="标书章节树">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={dragStart} onDragEnd={dragEnd} onDragCancel={() => setDragged(undefined)}>
          <SortableContext items={visible.map((entry) => entry.section.id)} strategy={verticalListSortingStrategy}>
            {visible.map((entry) => <SortableTreeRow key={entry.section.id} entry={entry} hasChildren={sections.some((section) => section.parent_id === entry.section.id)} dragDisabled={Boolean(treeSearch) || statusFilter !== 'all'} onSelect={onSelect} />)}
          </SortableContext>
          <DragOverlay>{dragged && <div className="tree-drag-overlay">{dragged.title}</div>}</DragOverlay>
        </DndContext>
        {!visible.length && <div className="inline-empty">没有匹配的章节</div>}
      </nav>
      <div className="tree-summary">
        <div><span>人工确认</span><strong>{confirmed} / {contentCount}</strong></div>
        <div className="thin-progress"><span style={{ width: `${contentCount ? confirmed / contentCount * 100 : 0}%` }} /></div>
        <div className="tree-summary-links"><span>明确关联条款 {mapped} / {requirements.length}</span><span className={openGapCount ? 'danger-text' : ''}>{openGapCount} 个未关闭缺口</span></div>
      </div>
    </div>
  );
}
