import type {
  ContentBlock,
  ExportReadiness,
  ProjectSection,
  ReviewStatus,
  WorkspaceData,
} from '../types';

export interface FlatSection {
  section: ProjectSection;
  depth: number;
  number: string;
  parent?: ProjectSection;
  siblings: ProjectSection[];
  index: number;
}

export function flattenSections(
  sections: ProjectSection[],
  parentId: string | null = null,
  depth = 0,
  prefix: number[] = [],
  parent?: ProjectSection,
): FlatSection[] {
  const siblings = sections
    .filter((section) => section.parent_id === parentId)
    .sort((a, b) => a.position - b.position);
  return siblings.flatMap((section, index) => {
    const numbers = [...prefix, index + 1];
    const entry = { section, depth, number: numbers.join('.'), parent, siblings, index };
    return [
      entry,
      ...flattenSections(sections, section.id, depth + 1, numbers, section),
    ];
  });
}

export function moveSectionInList(
  sections: ProjectSection[],
  sectionId: string,
  parentId: string | null,
  position: number,
) {
  const moving = sections.find((section) => section.id === sectionId);
  if (!moving) return sections;
  const oldParentId = moving.parent_id;
  const positions = new Map<string, number>();
  if (oldParentId !== parentId) {
    sections
      .filter((section) => section.parent_id === oldParentId && section.id !== sectionId)
      .sort((a, b) => a.position - b.position)
      .forEach((section, index) => positions.set(section.id, index));
  }
  const targetSiblings = sections
    .filter((section) => section.parent_id === parentId && section.id !== sectionId)
    .sort((a, b) => a.position - b.position);
  targetSiblings.splice(Math.max(0, Math.min(position, targetSiblings.length)), 0, moving);
  targetSiblings.forEach((section, index) => positions.set(section.id, index));
  return sections.map((section) => {
    if (section.id === sectionId) return { ...section, parent_id: parentId, position: positions.get(sectionId) ?? position };
    if (positions.has(section.id)) return { ...section, position: positions.get(section.id)! };
    return section;
  });
}

export function contentSections(sections: ProjectSection[]) {
  return sections.filter((section) => section.content_mode !== 'group');
}

export function sectionStatus(section: ProjectSection): ReviewStatus | 'gap' | 'empty' {
  if (section.content_status === 'gap') return 'gap';
  if (section.content_status === 'empty') return 'empty';
  return section.review_status;
}

export function getSelectedRevision(section: ProjectSection) {
  return section.selected_revision ?? section.current_revision ?? null;
}

export function blockText(block: ContentBlock | string | undefined): string {
  if (!block) return '';
  if (typeof block === 'string') return block;
  switch (block.type) {
    case 'paragraph':
    case 'heading':
      return block.text;
    case 'list':
      return block.items.join('\n');
    case 'table':
      return [...(block.header ? [block.header] : []), ...block.rows]
        .map((row) => row.join(' | '))
        .join('\n');
    case 'fact_ref':
      return block.label || block.fallback_text || `[[${block.fact_key}]]`;
    case 'attachment_ref':
      return block.label || `[[附件：${block.attachment_id}]]`;
    case 'placeholder':
      return `[[${block.label}]]`;
    case 'tender_ooxml_ref':
      return block.text || block.label || `[[招标格式块：${block.anchor_key}]]`;
  }
}

export function revisionText(blocks: ContentBlock[] | undefined) {
  return (blocks || []).map(blockText).join('\n\n');
}

export function deriveExportReadiness(data: WorkspaceData): ExportReadiness {
  if (data.export_readiness) return data.export_readiness;
  const contents = contentSections(data.sections);
  const unconfirmed = contents.filter(
    (section) => section.review_status !== 'confirmed' || section.content_status !== 'ready',
  ).length;
  const openGaps = data.gaps.filter(
    (gap) => gap.blocking && gap.status !== 'resolved' && gap.status !== 'closed',
  ).length;
  const pendingRisks = data.risks.filter(
    (risk) => !risk.disposition || risk.disposition === 'pending',
  ).length;
  const unconfirmedFacts = data.facts.filter((fact) => fact.status !== 'confirmed').length;
  const checks = [
    {
      key: 'sections',
      label: '内容章节已确认',
      passed: unconfirmed === 0,
      blocking: true,
      detail: unconfirmed ? `${unconfirmed} 个章节待处理` : `${contents.length} 个章节已确认`,
    },
    {
      key: 'gaps',
      label: '阻塞缺口已关闭',
      passed: openGaps === 0,
      blocking: true,
      detail: openGaps ? `${openGaps} 个未关闭缺口` : '无阻塞缺口',
    },
    {
      key: 'risks',
      label: '风险已完成人工处置',
      passed: pendingRisks === 0,
      blocking: true,
      detail: pendingRisks ? `${pendingRisks} 项风险待处置` : '风险均已处置',
    },
    {
      key: 'facts',
      label: '统一事实已确认',
      passed: unconfirmedFacts === 0,
      blocking: true,
      detail: unconfirmedFacts ? `${unconfirmedFacts} 项事实待确认` : '事实字段状态一致',
    },
  ];
  return {
    can_export_review: true,
    can_export_formal: checks.every((check) => check.passed),
    checks,
    unconfirmed_sections: unconfirmed,
    open_blocking_gaps: openGaps,
    undisposed_risks: pendingRisks,
  };
}

export function canIndent(entry: FlatSection | undefined) {
  if (!entry || entry.section.locked || entry.index === 0) return false;
  const previous = entry.siblings[entry.index - 1];
  return Boolean(previous && !previous.locked);
}

export function canOutdent(entry: FlatSection | undefined) {
  return Boolean(entry && !entry.section.locked && entry.parent);
}
