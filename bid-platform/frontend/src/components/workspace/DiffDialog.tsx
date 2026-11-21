import { Alert, App, Button, Modal, Space, Tag } from 'antd';
import { ArrowRightOutlined, CopyOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../app/api';
import { queryClient } from '../../app/queryClient';
import { blockText } from '../../lib/workspace';
import { queryKeys } from '../../lib/query';
import type { Candidate, ProjectSection } from '../../types';
import { QueryError } from '../Common';

export function DiffDialog({
  section,
  candidate,
  projectVersion,
  open,
  onClose,
  onSelected,
}: {
  section: ProjectSection;
  candidate?: Candidate;
  projectVersion: number;
  open: boolean;
  onClose: () => void;
  onSelected: (impactedIds: string[]) => void;
}) {
  const { message } = App.useApp();
  const candidateId = candidate?.candidate_id || candidate?.id || '';
  const diff = useQuery({
    queryKey: ['sections', section.id, 'diff', candidateId],
    queryFn: () => api.sections.diff(section.id, candidateId),
    enabled: open && Boolean(candidateId),
  });
  const select = useMutation({
    mutationFn: () => api.sections.selectVersion(section.id, { candidate_id: candidateId, version: section.version, project_version: projectVersion }),
    onSuccess: async () => {
      message.success('候选内容已复制为新修订，当前章节需重新确认');
      const impacted = diff.data?.impacted_sections?.map((item) => item.id) || [];
      onSelected([...new Set([section.id, ...impacted])]);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workspace(section.project_id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.candidates(section.id) }),
      ]);
      onClose();
    },
    onError: (error) => message.error(error.message),
  });

  return (
    <Modal
      title="候选版本差异"
      open={open}
      onCancel={onClose}
      width={940}
      destroyOnClose
      footer={<><div className="modal-footer-note">切换生成新修订，不覆盖原版本；关联章节将进入待复核。</div><Space><Button onClick={onClose}>取消</Button><Button type="primary" icon={<CopyOutlined />} loading={select.isPending} disabled={!diff.data} onClick={() => select.mutate()}>使用此版本</Button></Space></>}
    >
      {candidate && <div className="diff-version-heading"><Tag>{diff.data?.current_label || '当前工作版本'}</Tag><ArrowRightOutlined /><Tag color="blue">{diff.data?.candidate_label || candidate.name || candidate.title}</Tag>{candidate.recommended && <Tag color="green">优先推荐</Tag>}</div>}
      {diff.error ? <QueryError error={diff.error as Error} retry={() => void diff.refetch()} /> : (
        <>
          {(diff.data?.impacted_sections?.length || diff.data?.fact_changes?.length) ? <Alert type="warning" showIcon message="切换后的连锁影响" description={<>{diff.data.impacted_sections?.length ? <div>待复核章节：{diff.data.impacted_sections.map((item) => item.title).join('、')}</div> : null}{diff.data.fact_changes?.length ? <div>统一事实变化：{diff.data.fact_changes.map((item) => item.fact_key).join('、')}</div> : null}</>} /> : <Alert type="info" showIcon message="后端未发现关联章节影响，仍请人工复核内容差异。" />}
          <div className="diff-grid diff-grid-head"><span>当前版本</span><span>候选版本</span></div>
          <div className="diff-table" aria-busy={diff.isLoading}>
            {diff.isLoading && <div className="inline-empty">正在计算结构化差异…</div>}
            {diff.data?.changes.map((change, index) => {
              const before = change.before_text ?? blockText(change.before);
              const after = change.after_text ?? blockText(change.after);
              return <div className={`diff-grid diff-${change.type}`} key={index}><div className={change.type === 'removed' || change.type === 'modified' ? 'removed-text' : ''}>{before || '—'}</div><div className={change.type === 'added' || change.type === 'modified' ? 'added-text' : ''}>{after || '—'}</div></div>;
            })}
            {diff.data && !diff.data.changes.length && <div className="inline-empty">两个版本没有文本差异。</div>}
          </div>
        </>
      )}
    </Modal>
  );
}
