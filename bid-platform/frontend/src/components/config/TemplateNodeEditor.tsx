import { Button, Input, Space, Switch } from 'antd';
import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { TemplateNode } from '../../types';

const nodeKey = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

export function TemplateNodeEditor({ value, onChange }: { value: TemplateNode[]; onChange: (nodes: TemplateNode[]) => void }) {
  const renderNodes = (nodes: TemplateNode[], depth: number, commit: (nodes: TemplateNode[]) => void): React.ReactNode => nodes.map((node, index) => {
    const patch = (input: Partial<TemplateNode>) => commit(nodes.map((item, itemIndex) => itemIndex === index ? { ...item, ...input } : item));
    const move = (direction: -1 | 1) => {
      const target = index + direction;
      if (target < 0 || target >= nodes.length) return;
      const next = [...nodes];
      [next[index], next[target]] = [next[target], next[index]];
      commit(next);
    };
    return (
      <div key={node.id || `${depth}-${index}`} className="template-node" style={{ marginLeft: depth * 20 }}>
        <div className="template-node-row">
          <span className="template-node-index">{depth + 1}.{index + 1}</span>
          <Input value={node.title} placeholder="章节名称" onChange={(event) => patch({ title: event.target.value })} />
          <Input value={node.key} placeholder="section_key" className="template-key-input" onChange={(event) => patch({ key: event.target.value })} />
          <Space className="template-node-lock"><span>锁定</span><Switch size="small" checked={node.locked} onChange={(locked) => patch({ locked })} /></Space>
          <Space size={0}>
            <Button type="text" size="small" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={() => move(-1)} />
            <Button type="text" size="small" icon={<ArrowDownOutlined />} disabled={index === nodes.length - 1} onClick={() => move(1)} />
            <Button type="text" size="small" icon={<PlusOutlined />} title="添加子章节" onClick={() => patch({ children: [...(node.children || []), { key: nodeKey(), title: '新建子章节', locked: false, children: [] }] })} />
            <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => commit(nodes.filter((_, itemIndex) => itemIndex !== index))} />
          </Space>
        </div>
        {node.children && renderNodes(node.children, depth + 1, (children) => patch({ children }))}
      </div>
    );
  });

  return (
    <div className="template-node-editor">
      <div className="template-node-head"><span>章节结构</span><span>章节名称 / 稳定键 / 锁定策略</span></div>
      {renderNodes(value, 0, onChange)}
      <Button block type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...value, { key: nodeKey(), title: '新建章节', locked: false, children: [] }])}>添加一级章节</Button>
    </div>
  );
}
