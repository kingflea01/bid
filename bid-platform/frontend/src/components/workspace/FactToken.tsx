import { Tooltip } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import type { ProjectFact } from '../../types';
import { displayJson } from '../../lib/format';

export function FactToken({ factKey, label, facts, onEdit }: { factKey: string; label?: string; facts: ProjectFact[]; onEdit: (fact: ProjectFact) => void }) {
  const fact = facts.find((item) => item.fact_key === factKey);
  if (!fact) return <button className="fact-token missing" type="button">[[{label || factKey}]]</button>;
  return (
    <Tooltip title={`统一事实：${factKey} · ${fact.status === 'confirmed' ? '已确认' : '待确认'}；点击编辑`}>
      <button className={`fact-token ${fact.status}`} type="button" onClick={() => onEdit(fact)}>
        <LinkOutlined />{displayJson(fact.value_json)}<span>{factKey}</span>
      </button>
    </Tooltip>
  );
}
