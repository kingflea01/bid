import { InfoCircleOutlined } from '@ant-design/icons';
import type { ContentBlock, ProjectFact, ProjectSection, WorkspaceData } from '../../types';
import type { FlatSection } from '../../lib/workspace';
import { ChapterCard } from './ChapterCard';

export function ChapterCardList({
  entries,
  data,
  onFactEdit,
  onSave,
  onRename,
  onOpenInspector,
}: {
  entries: FlatSection[];
  data: WorkspaceData;
  onFactEdit: (fact: ProjectFact) => void;
  onSave: (section: ProjectSection, blocks: ContentBlock[]) => Promise<void>;
  onRename: (section: ProjectSection, title: string) => Promise<void>;
  onOpenInspector: (sectionId: string, tab: 'candidates' | 'requirements' | 'issues') => void;
}) {
  return (
    <div className="chapter-card-stream">
      <div className="stream-intro"><span><InfoCircleOutlined /> 卡片是当前工作版本，导出按章节树自动组装</span><span>{entries.length} 个章节节点</span></div>
      {entries.map((entry) => <ChapterCard
        key={entry.section.id}
        entry={entry}
        requirements={data.requirements.filter((requirement) => requirement.section_id === entry.section.id)}
        facts={data.facts}
        openGapCount={data.gaps.filter((gap) => gap.section_id === entry.section.id && gap.status !== 'resolved' && gap.status !== 'closed').length}
        onFactEdit={onFactEdit}
        onSave={onSave}
        onRename={onRename}
        onOpenInspector={(tab) => onOpenInspector(entry.section.id, tab)}
      />)}
    </div>
  );
}
