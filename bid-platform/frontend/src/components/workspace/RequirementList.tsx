import { useState } from 'react';
import { Button, Progress, Tag } from 'antd';
import { CheckCircleFilled, ExclamationCircleFilled, LinkOutlined } from '@ant-design/icons';
import type { Requirement } from '../../types';
import { EmptyState } from '../Common';
import { SourceDialog } from '../SourceDialog';

export function RequirementList({ requirements }: { requirements: Requirement[] }) {
  const [source, setSource] = useState<Requirement>();
  if (!requirements.length) return <EmptyState description="该章节暂无明确关联条款" />;
  const confirmed = requirements.filter((item) => item.mapping_status === 'confirmed').length;
  return (
    <div className="requirement-list">
      <div className="requirement-summary"><div><span>人工确认关联</span><strong>{confirmed} / {requirements.length}</strong></div><Progress percent={requirements.length ? Math.round(confirmed / requirements.length * 100) : 0} showInfo={false} size="small" /><small>这里仅表示条款与章节的明确关联，不代表 AI 内容满足率。</small></div>
      {requirements.map((requirement) => {
        const satisfied = requirement.mapping_status === 'confirmed';
        return <article className="requirement-item" key={requirement.id}><div className="requirement-status">{satisfied ? <CheckCircleFilled /> : <ExclamationCircleFilled />}</div><div className="requirement-copy"><strong>{requirement.text}</strong><div><code>{requirement.code}</code><Tag color={satisfied ? 'green' : requirement.mapping_status === 'missing' ? 'red' : 'gold'}>{satisfied ? '关联已确认' : requirement.mapping_status === 'partial' ? '部分关联' : requirement.mapping_status === 'missing' ? '待补关联' : '待人工确认'}</Tag></div><Button type="link" size="small" icon={<LinkOutlined />} onClick={() => setSource(requirement)}>定位招标原文（{requirement.anchors?.length || 0}）</Button></div></article>;
      })}
      <SourceDialog requirement={source} open={Boolean(source)} onClose={() => setSource(undefined)} />
    </div>
  );
}
