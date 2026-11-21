import { useEffect, useMemo, useState } from 'react';
import { Button, Descriptions, Modal, Space, Tag } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { api } from '../app/api';
import { QueryError } from './Common';
import type { Requirement } from '../types';

export function SourceDialog({ requirement, open, onClose }: { requirement?: Requirement; open: boolean; onClose: () => void }) {
  const anchors = useMemo(() => requirement?.anchors || [], [requirement]);
  const [anchorKey, setAnchorKey] = useState<string>();
  useEffect(() => setAnchorKey(anchors[0]?.anchor_key), [anchors]);
  const anchor = anchors.find((item) => item.anchor_key === anchorKey) || anchors[0];
  const source = useQuery({
    queryKey: ['source', requirement?.document_id, anchor?.anchor_key],
    queryFn: () => api.sources.get(requirement!.document_id, anchor!.anchor_key),
    enabled: open && Boolean(requirement?.document_id && anchor?.anchor_key),
  });

  const highlightedText = () => {
    const data = source.data;
    if (!data) return null;
    const quote = anchor?.quote || data.quote;
    if (!quote || !data.text.includes(quote)) return data.text;
    const [before, ...rest] = data.text.split(quote);
    return <>{before}<mark>{quote}</mark>{rest.join(quote)}</>;
  };

  return (
    <Modal title="招标原文定位" open={open} onCancel={onClose} footer={<Button onClick={onClose}>关闭</Button>} width={760} destroyOnClose>
      {requirement && <div className="source-dialog-meta"><Tag>{requirement.code}</Tag><span>{requirement.text}</span></div>}
      {anchors.length > 1 && <Space wrap className="anchor-switcher">{anchors.map((item, index) => <Button key={item.anchor_key} size="small" type={item.anchor_key === anchor?.anchor_key ? 'primary' : 'default'} onClick={() => setAnchorKey(item.anchor_key)}>原文锚点 {index + 1}</Button>)}</Space>}
      {!anchor ? <div className="inline-empty">此条款尚未绑定原文锚点，需人工复核。</div> : source.error ? <QueryError error={source.error as Error} retry={() => void source.refetch()} /> : (
        <div className="source-document" aria-busy={source.isLoading}>
          <div className="source-location"><FileTextOutlined />{source.data?.document_name || '招标文件'}<span>·</span><span>{source.data?.outline_title || '原文块'}</span>{source.data?.page_no && <Tag>第 {source.data.page_no} 页</Tag>}<code>{anchor.anchor_key}</code></div>
          <blockquote>{source.isLoading ? '正在读取原文…' : highlightedText()}</blockquote>
          <Descriptions size="small" column={2} items={[
            { key: 'type', label: '处理类型', children: requirement?.response_type },
            { key: 'status', label: '提取状态', children: requirement?.status },
            { key: 'mandatory', label: '强制性', children: requirement?.mandatory_level || '—' },
            { key: 'confidence', label: '置信度', children: requirement?.confidence === undefined ? '—' : `${Math.round(requirement.confidence * 100)}%` },
          ]} />
        </div>
      )}
      <div className="modal-footnote">页码与位置来自解析锚点，不使用模型生成的页码。</div>
    </Modal>
  );
}
