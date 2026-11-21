import { useState } from 'react';
import { App, Button, Dropdown, Form, Input, Modal, Tag } from 'antd';
import { CopyOutlined, DownOutlined, EditOutlined, LinkOutlined, LockOutlined, MoreOutlined, RightOutlined } from '@ant-design/icons';
import type { ContentBlock } from '../../types';
import type { FlatSection } from '../../lib/workspace';
import { getSelectedRevision } from '../../lib/workspace';
import { useWorkspaceStore } from '../../stores/workspaceStore';
import type { ProjectFact, ProjectSection, Requirement } from '../../types';
import { SectionStatusTag } from '../Common';
import { BlockEditor } from './BlockEditor';

interface ChapterCardProps {
  entry: FlatSection;
  requirements: Requirement[];
  facts: ProjectFact[];
  openGapCount: number;
  onFactEdit: (fact: ProjectFact) => void;
  onSave: (section: ProjectSection, blocks: ContentBlock[]) => Promise<void>;
  onRename: (section: ProjectSection, title: string) => Promise<void>;
  onOpenInspector: (tab: 'candidates' | 'requirements' | 'issues') => void;
}

export function ChapterCard({ entry, requirements, facts, openGapCount, onFactEdit, onSave, onRename, onOpenInspector }: ChapterCardProps) {
  const { section, depth, number } = entry;
  const { message } = App.useApp();
  const activeId = useWorkspaceStore((state) => state.activeSectionId);
  const setActive = useWorkspaceStore((state) => state.setActiveSection);
  const collapsed = useWorkspaceStore((state) => state.collapsedCards[section.id]);
  const toggleCard = useWorkspaceStore((state) => state.toggleCard);
  const [renaming, setRenaming] = useState(false);
  const [form] = Form.useForm<{ title: string }>();
  const [savingTitle, setSavingTitle] = useState(false);
  const revision = getSelectedRevision(section);
  const isGroup = section.content_mode === 'group';
  const active = activeId === section.id;

  return (
    <article id={`chapter-card-${section.id}`} className={`chapter-card ${active ? 'active' : ''} ${isGroup ? 'group-card' : ''}`} style={{ marginLeft: Math.min(depth * 14, 42) }}>
      <span className="chapter-active-line" />
      <header className="chapter-card-header" onClick={() => setActive(section.id)}>
        <Button type="text" size="small" className="chapter-collapse" icon={collapsed ? <RightOutlined /> : <DownOutlined />} onClick={(event) => { event.stopPropagation(); toggleCard(section.id); }} aria-label={collapsed ? '展开章节' : '收起章节'} />
        <div className="chapter-card-title">
          <div><span className="chapter-number">{number}</span><strong>{section.title}</strong>{section.locked ? <Tag icon={<LockOutlined />}>招标固定</Tag> : <Tag>{isGroup ? '章节分组' : section.content_mode === 'attachment' ? '附件单元' : section.content_mode === 'tender' ? '招标格式' : '素材章节'}</Tag>}</div>
          <span>{isGroup ? '结构分组 · 状态由后代章节汇总' : revision ? `Revision V${revision.revision_no} · ${revision.source_type}` : '未选择内容版本'}{openGapCount > 0 && <em> · {openGapCount} 个缺口</em>}</span>
        </div>
        {!isGroup && <SectionStatusTag section={section} />}
        <Dropdown menu={{ items: [{ key: 'rename', icon: <EditOutlined />, label: '修改章节标题', disabled: section.locked }, { key: 'requirements', icon: <LinkOutlined />, label: '查看关联条款' }, { key: 'candidates', icon: <CopyOutlined />, label: '查看候选版本', disabled: isGroup }], onClick: ({ key, domEvent }) => { domEvent.stopPropagation(); if (key === 'rename') { form.setFieldValue('title', section.title); setRenaming(true); } if (key === 'requirements' || key === 'candidates') onOpenInspector(key); } }}>
          <Button type="text" size="small" icon={<MoreOutlined />} onClick={(event) => event.stopPropagation()} />
        </Dropdown>
      </header>
      {!collapsed && !isGroup && (
        <div className="chapter-card-body">
          <BlockEditor
            sectionId={section.id}
            revision={revision}
            facts={facts}
            onFactEdit={onFactEdit}
            onSave={(blocks) => onSave(section, blocks)}
            onOpenCandidates={() => onOpenInspector('candidates')}
          />
          <footer className="chapter-card-footer">
            <span className="chapter-origin">{revision?.source_label || revision?.source_type || '尚无内容来源'}</span>
            <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => onOpenInspector('candidates')}>候选版本</Button>
            <Button type="text" size="small" icon={<LinkOutlined />} onClick={() => onOpenInspector('requirements')}>{requirements.length} 条关联条款</Button>
            {openGapCount > 0 && <Button type="text" size="small" danger onClick={() => onOpenInspector('issues')}>{openGapCount} 个待处理缺口</Button>}
          </footer>
        </div>
      )}
      <Modal title="修改章节标题" open={renaming} onCancel={() => setRenaming(false)} confirmLoading={savingTitle} onOk={() => form.submit()} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={async (values) => { setSavingTitle(true); try { await onRename(section, values.title); setRenaming(false); } catch (error) { message.error(error instanceof Error ? error.message : '标题保存失败'); } finally { setSavingTitle(false); } }}>
          <Form.Item name="title" label="章节标题" rules={[{ required: true, message: '请输入章节标题' }]}><Input maxLength={160} /></Form.Item>
          <div className="modal-footnote">招标锁定章节不可修改；章节稳定键与 ID 保持不变。</div>
        </Form>
      </Modal>
    </article>
  );
}
