import { Button, Space, Table, Tag } from 'antd';
import { CloudUploadOutlined } from '@ant-design/icons';
import type { Revision } from '../../types';
import { dateTime, displayJson } from '../../lib/format';

export function RevisionList({
  revisions,
  onPublish,
  publishingId,
  showContent,
}: {
  revisions?: Revision[];
  onPublish: (revision: Revision) => void;
  publishingId?: string;
  showContent?: boolean;
}) {
  return (
    <Table<Revision>
      className="revision-table"
      rowKey="id"
      size="small"
      pagination={false}
      dataSource={[...(revisions || [])].sort((a, b) => b.revision_no - a.revision_no)}
      columns={[
        { title: '版本', dataIndex: 'revision_no', width: 90, render: (value) => <strong>V{value}</strong> },
        {
          title: '状态', dataIndex: 'status', width: 100,
          render: (value: string) => <Tag color={value === 'published' ? 'green' : value === 'draft' ? 'blue' : 'default'}>{value === 'published' ? '已发布' : value === 'draft' ? '草稿' : '已归档'}</Tag>,
        },
        { title: '创建时间', dataIndex: 'created_at', width: 160, render: dateTime },
        ...(showContent ? [{
          title: '内容摘要', key: 'content', ellipsis: true,
          render: (_: unknown, revision: Revision) => <span className="revision-summary">{displayJson(revision.fields_json || revision.technical_fields_json || revision.nodes_json || revision.content_json).slice(0, 160)}</span>,
        }] : []),
        {
          title: '操作', key: 'actions', width: 110, align: 'right' as const,
          render: (_: unknown, revision: Revision) => revision.status === 'draft' ? (
            <Button size="small" type="link" icon={<CloudUploadOutlined />} loading={publishingId === revision.id} onClick={() => onPublish(revision)}>发布</Button>
          ) : <Space><span className="muted">不可变</span></Space>,
        },
      ]}
    />
  );
}
