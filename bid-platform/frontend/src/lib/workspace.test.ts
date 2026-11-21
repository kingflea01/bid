import { describe, expect, it } from 'vitest';
import type { ProjectSection, WorkspaceData } from '../types';
import {
  blockText,
  canIndent,
  canOutdent,
  deriveExportReadiness,
  flattenSections,
  moveSectionInList,
} from './workspace';

const section = (id: string, parent_id: string | null = null, position = 0, overrides: Partial<ProjectSection> = {}): ProjectSection => ({
  id,
  project_id: 'project-1',
  parent_id,
  position,
  title: id,
  section_key: id,
  source_type: 'template',
  locked: false,
  content_mode: 'asset',
  selected_revision_id: `revision-${id}`,
  content_status: 'ready',
  review_status: 'confirmed',
  version: 1,
  ...overrides,
});

const workspace = (overrides: Partial<WorkspaceData> = {}): WorkspaceData => ({
  project: {
    id: 'project-1', name: '测试项目', code: 'P-1', customer_name: '客户', procurement_type: '公开招标',
    status: 'workspace', owner_id: 'user-1', version: 1, created_at: '2026-01-01',
  },
  sections: [section('a')],
  requirements: [], gaps: [], risks: [], facts: [], tasks: [],
  ...overrides,
});

describe('章节树', () => {
  it('按父级与 position 生成稳定层级和显示编号', () => {
    const flat = flattenSections([
      section('b', null, 1),
      section('a', null, 0, { content_mode: 'group' }),
      section('a-2', 'a', 1),
      section('a-1', 'a', 0),
    ]);
    expect(flat.map((entry) => [entry.section.id, entry.number])).toEqual([
      ['a', '1'], ['a-1', '1.1'], ['a-2', '1.2'], ['b', '2'],
    ]);
  });

  it('同级重排会重新计算所有受影响位置', () => {
    const moved = moveSectionInList([section('a', null, 0), section('b', null, 1), section('c', null, 2)], 'c', null, 0);
    expect(flattenSections(moved).map((entry) => entry.section.id)).toEqual(['c', 'a', 'b']);
    expect(moved.find((item) => item.id === 'c')?.position).toBe(0);
    expect(moved.find((item) => item.id === 'a')?.position).toBe(1);
  });

  it('跨级移动会压缩旧父级并插入目标父级', () => {
    const moved = moveSectionInList([
      section('root', null, 0, { content_mode: 'group' }),
      section('child', 'root', 0),
      section('other', null, 1),
    ], 'child', null, 1);
    expect(moved.find((item) => item.id === 'child')?.parent_id).toBeNull();
    expect(flattenSections(moved).map((entry) => entry.section.id)).toEqual(['root', 'child', 'other']);
  });

  it('锁定章节和没有上一节点的章节不能降级', () => {
    const entries = flattenSections([section('first', null, 0, { locked: true }), section('second', null, 1)]);
    expect(canIndent(entries[0])).toBe(false);
    expect(canIndent(entries[1])).toBe(false);
    expect(canOutdent(entries[1])).toBe(false);
  });
});

describe('内容块与导出门禁', () => {
  it('事实引用只显示事实标签，不复制事实值', () => {
    expect(blockText({ type: 'fact_ref', fact_key: 'implementation.days', fallback_text: '20 个工作日' })).toBe('20 个工作日');
    expect(blockText({ type: 'placeholder', label: '待编写：实施方案' })).toBe('[[待编写：实施方案]]');
  });

  it('所有人工确认、缺口、风险与事实条件满足后才允许正式导出', () => {
    const ready = deriveExportReadiness(workspace());
    expect(ready.can_export_formal).toBe(true);
    expect(ready.can_export_review).toBe(true);
  });

  it('任一阻断条件存在都禁止正式导出但仍允许审阅版', () => {
    const data = workspace({
      sections: [section('a', null, 0, { review_status: 'unconfirmed' })],
      gaps: [{ id: 'gap', project_id: 'project-1', gap_type: 'content', title: '缺内容', blocking: true, status: 'open' }],
      risks: [{ id: 'risk', project_id: 'project-1', category: '合同', conflict_type: '责任', severity: 'high', recommendation: '复核', legal_review: true, disposition: 'pending' }],
      facts: [{ id: 'fact', fact_key: 'days', value_json: 20, value_type: 'number', source_type: 'manual', status: 'unconfirmed' }],
    });
    const readiness = deriveExportReadiness(data);
    expect(readiness.can_export_formal).toBe(false);
    expect(readiness.can_export_review).toBe(true);
    expect(readiness.checks.filter((check) => !check.passed)).toHaveLength(4);
  });

  it('服务端门禁结果优先于前端推导', () => {
    const readiness = deriveExportReadiness(workspace({
      export_readiness: { can_export_review: false, can_export_formal: false, checks: [{ key: 'snapshot', label: '快照过期', passed: false, blocking: true }] },
    }));
    expect(readiness.can_export_review).toBe(false);
    expect(readiness.checks[0].key).toBe('snapshot');
  });
});
