import { useCallback, useEffect, useState } from 'react';
import { Alert, App, Button, Dropdown, Input, Select, Space } from 'antd';
import { CheckOutlined, DeleteOutlined, DownOutlined, EditOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import type { ContentBlock, ProjectFact, SectionRevision } from '../../types';
import { ApiError } from '../../app/api';
import { FactToken } from './FactToken';

interface BlockEditorProps {
  sectionId: string;
  revision: SectionRevision | null;
  facts: ProjectFact[];
  onFactEdit: (fact: ProjectFact) => void;
  onSave: (blocks: ContentBlock[]) => Promise<void>;
  onOpenCandidates: () => void;
}

const blockNames: Record<ContentBlock['type'], string> = {
  paragraph: '段落', heading: '内部标题', list: '列表', table: '表格', fact_ref: '事实引用', attachment_ref: '附件引用', placeholder: '占位符', tender_ooxml_ref: '招标格式块',
};

function emptyBlock(type: ContentBlock['type']): ContentBlock {
  switch (type) {
    case 'paragraph': return { type, text: '' };
    case 'heading': return { type, text: '' };
    case 'list': return { type, items: [''], ordered: false };
    case 'table': return { type, rows: [['', '']], header: [] };
    case 'fact_ref': return { type, fact_key: '' };
    case 'attachment_ref': return { type, attachment_id: '', label: '' };
    case 'placeholder': return { type, label: '待补充内容' };
    case 'tender_ooxml_ref': return { type, anchor_key: '', text: '' };
  }
}

export function BlockEditor({ revision, facts, onFactEdit, onSave, onOpenCandidates }: BlockEditorProps) {
  const { message } = App.useApp();
  const [editing, setEditing] = useState(false);
  const [blocks, setBlocks] = useState<ContentBlock[]>(revision?.content_json || []);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    setBlocks(revision?.content_json || []);
    setDirty(false);
    setSaveError('');
  }, [revision?.id]);

  const save = useCallback(async () => {
    if (!dirty || saving) return true;
    setSaving(true);
    setSaveError('');
    try {
      await onSave(blocks);
      setDirty(false);
      return true;
    } catch (error) {
      const text = error instanceof ApiError && error.status === 409
        ? '章节已被其他操作更新。请刷新工作区并比较后再保存，当前内容未被覆盖。'
        : error instanceof Error ? error.message : '自动保存失败';
      setSaveError(text);
      return false;
    } finally {
      setSaving(false);
    }
  }, [blocks, dirty, onSave, saving]);

  useEffect(() => {
    if (!editing || !dirty) return;
    const timer = window.setTimeout(() => void save(), 1200);
    return () => window.clearTimeout(timer);
  }, [editing, dirty, blocks, save]);

  const update = (index: number, block: ContentBlock) => {
    setBlocks((current) => current.map((item, itemIndex) => itemIndex === index ? block : item));
    setDirty(true);
  };

  const renderReadonly = (block: ContentBlock, index: number) => {
    switch (block.type) {
      case 'paragraph': return <p key={block.id || index}>{block.text}</p>;
      case 'heading': return <h4 key={block.id || index}>{block.text}</h4>;
      case 'list': {
        const List = block.ordered ? 'ol' : 'ul';
        return <List key={block.id || index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</List>;
      }
      case 'table': return <div key={block.id || index} className="block-table-wrap"><table className="block-table">{block.header?.length ? <thead><tr>{block.header.map((cell, cellIndex) => <th key={cellIndex}>{cell}</th>)}</tr></thead> : null}<tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>;
      case 'fact_ref': return <div key={block.id || index} className="fact-block"><FactToken factKey={block.fact_key} label={block.label} facts={facts} onEdit={onFactEdit} /></div>;
      case 'attachment_ref': return <div key={block.id || index} className="attachment-block"><span>附件</span><strong>{block.label || block.attachment_id}</strong><small>{block.status || '由附件库提供'}</small></div>;
      case 'placeholder': return <button key={block.id || index} type="button" className="placeholder-block" onClick={onOpenCandidates}>[[{block.label}]]<span>选择素材或编辑正文补齐</span></button>;
      case 'tender_ooxml_ref': return <div key={block.id || index} className="tender-block"><span>招标原始格式块</span><p>{block.text || block.label || block.anchor_key}</p><code>{block.anchor_key}</code></div>;
    }
  };

  const renderEditor = (block: ContentBlock, index: number) => {
    const common = { autoSize: { minRows: 2, maxRows: 8 } };
    switch (block.type) {
      case 'paragraph':
      case 'heading':
        return <Input.TextArea {...common} value={block.text} onChange={(event) => update(index, { ...block, text: event.target.value })} />;
      case 'list':
        return <Input.TextArea {...common} value={block.items.join('\n')} onChange={(event) => update(index, { ...block, items: event.target.value.split('\n') })} placeholder="每行一个列表项" />;
      case 'table':
        return <Input.TextArea {...common} value={block.rows.map((row) => row.join(' | ')).join('\n')} onChange={(event) => update(index, { ...block, rows: event.target.value.split('\n').map((row) => row.split('|').map((cell) => cell.trim())) })} placeholder="每行一行，使用 | 分隔单元格" />;
      case 'fact_ref':
        return <Select showSearch value={block.fact_key || undefined} placeholder="选择统一事实字段" options={facts.map((fact) => ({ value: fact.fact_key, label: fact.fact_key }))} onChange={(fact_key) => update(index, { ...block, fact_key })} className="full-width" />;
      case 'attachment_ref':
        return <Space.Compact className="full-width"><Input value={block.attachment_id} placeholder="附件 ID" onChange={(event) => update(index, { ...block, attachment_id: event.target.value })} /><Input value={block.label} placeholder="显示名称" onChange={(event) => update(index, { ...block, label: event.target.value })} /></Space.Compact>;
      case 'placeholder':
        return <Input value={block.label} onChange={(event) => update(index, { ...block, label: event.target.value })} />;
      case 'tender_ooxml_ref':
        return <Space.Compact className="full-width"><Input value={block.anchor_key} placeholder="原文 anchor_key" onChange={(event) => update(index, { ...block, anchor_key: event.target.value })} /><Input value={block.text} placeholder="格式块说明" onChange={(event) => update(index, { ...block, text: event.target.value })} /></Space.Compact>;
    }
  };

  return (
    <div className="block-editor">
      <div className="block-editor-toolbar">
        <span>{saving ? '正在保存新修订…' : saveError ? '保存未完成' : dirty ? '停止输入后自动保存' : revision ? `当前 Revision V${revision.revision_no}` : '尚未选择内容版本'}</span>
        <Space size={4}>
          {editing && <Dropdown menu={{ items: (Object.keys(blockNames) as ContentBlock['type'][]).map((type) => ({ key: type, label: blockNames[type] })), onClick: ({ key }) => { setBlocks((current) => [...current, emptyBlock(key as ContentBlock['type'])]); setDirty(true); } }}><Button size="small" icon={<PlusOutlined />}>添加内容块 <DownOutlined /></Button></Dropdown>}
          {editing && <Button size="small" icon={<SaveOutlined />} loading={saving} disabled={!dirty} onClick={() => void save()}>保存</Button>}
          <Button size="small" type={editing ? 'primary' : 'text'} icon={editing ? <CheckOutlined /> : <EditOutlined />} onClick={async () => { if (!editing) { setEditing(true); return; } if (dirty) { const saved = await save(); if (!saved) { message.warning('请先处理保存失败或版本冲突'); return; } } setEditing(false); }}>{editing ? '完成' : '编辑正文'}</Button>
        </Space>
      </div>
      {saveError && <Alert type="error" showIcon message={saveError} />}
      {!editing ? (
        <div className="document-blocks">{blocks.length ? blocks.map(renderReadonly) : <div className="empty-document"><p>当前章节没有正文内容。</p><Button onClick={onOpenCandidates}>查看候选版本</Button><Button type="text" onClick={() => setEditing(true)}>直接编辑</Button></div>}</div>
      ) : (
        <div className="editable-blocks">
          {blocks.map((block, index) => <div className="editable-block" key={block.id || index}><div className="editable-block-label"><span>{blockNames[block.type]}</span><Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => { setBlocks((current) => current.filter((_, itemIndex) => itemIndex !== index)); setDirty(true); }} /></div>{renderEditor(block, index)}</div>)}
          {!blocks.length && <div className="inline-empty">从“添加内容块”开始编写，不允许插入任意 HTML 或外部资源。</div>}
        </div>
      )}
    </div>
  );
}
