import { Button, Tag, Tooltip } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, HistoryOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { date } from '../../lib/format';
import { items, queryKeys } from '../../lib/query';
import type { Candidate, ProjectSection } from '../../types';
import { EmptyState, QueryError } from '../Common';

export function CandidateList({ section, onCompare }: { section: ProjectSection; onCompare: (candidate: Candidate) => void }) {
  const query = useQuery({ queryKey: queryKeys.candidates(section.id), queryFn: () => api.sections.candidates(section.id) });
  if (query.error) return <QueryError error={query.error as Error} retry={() => void query.refetch()} />;
  const candidates = items(query.data);
  if (!query.isLoading && !candidates.length) return <EmptyState description="当前没有可复用候选，可直接编辑正文" />;
  return (
    <div className="candidate-list" aria-busy={query.isLoading}>
      <div className="inspector-section-heading"><strong>可复用内容</strong><span>{candidates.length} 个候选</span></div>
      {candidates.map((candidate) => {
        const current = candidate.current || candidate.status === 'selected';
        return (
          <article className={`candidate-item ${current ? 'current' : ''}`} key={candidate.id}>
            <div className="candidate-title-row">
              <span className="candidate-radio">{current && <CheckCircleOutlined />}</span>
              <div><strong>{candidate.name || candidate.title || candidate.candidate_type}</strong><small>{candidate.revision_label || (candidate.revision_no ? `V${candidate.revision_no}` : candidate.candidate_id || candidate.id)}</small></div>
              {current ? <Tag color="blue">当前</Tag> : candidate.recommended ? <Tag color="green">优先推荐</Tag> : null}
            </div>
            <div className="candidate-source">{candidate.candidate_type === 'history' ? <HistoryOutlined /> : <SafetyCertificateOutlined />}<span>{candidate.source_label || candidate.candidate_type}</span></div>
            <div className="candidate-meta">
              {candidate.valid_to && <span className={candidate.valid_to < new Date().toISOString().slice(0, 10) ? 'danger-text' : ''}><ClockCircleOutlined /> 有效期至 {date(candidate.valid_to)}</span>}
              {candidate.note && <Tooltip title={candidate.note}><span className="warning-text">{candidate.note}</span></Tooltip>}
            </div>
            {candidate.rank_reasons.length > 0 && <ul className="candidate-reasons">{candidate.rank_reasons.slice(0, 3).map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
            <div className="candidate-actions"><span>排序分仅表示推荐顺序</span>{current ? <small>正在使用</small> : <Button type="link" size="small" onClick={() => onCompare(candidate)}>查看差异并切换</Button>}</div>
          </article>
        );
      })}
      <div className="inspector-note">候选来自已发布素材、历史最终确认版本或当前项目人工修订。切换不会自动改写其他章节。</div>
    </div>
  );
}
