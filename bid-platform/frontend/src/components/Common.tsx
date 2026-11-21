import type { ReactNode } from 'react';
import { Alert, Button, Empty, Tag } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { reviewStatus, taskStatus } from '../lib/format';
import type { ProjectSection } from '../types';
import { sectionStatus } from '../lib/workspace';

export function PageHeader({
  eyebrow,
  title,
  description,
  extra,
  back,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  extra?: ReactNode;
  back?: boolean;
}) {
  const navigate = useNavigate();
  return (
    <header className="page-header">
      <div className="page-heading-wrap">
        {back && <Button className="page-back" type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} />}
        <div>
          {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
          <h1>{title}</h1>
          {description && <div className="page-description">{description}</div>}
        </div>
      </div>
      {extra && <div className="page-actions">{extra}</div>}
    </header>
  );
}

export function SectionStatusTag({ section }: { section: ProjectSection }) {
  const status = sectionStatus(section);
  const meta = reviewStatus[status] || { label: status, color: 'default' };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

export function TaskStatusTag({ status }: { status: string }) {
  const meta = taskStatus[status] || { label: status, color: 'default' };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

export function QueryError({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <Alert
      className="query-error"
      type="error"
      showIcon
      message="数据加载失败"
      description={error.message}
      action={retry && <Button size="small" onClick={retry}>重试</Button>}
    />
  );
}

export function EmptyState({ description, action }: { description: string; action?: ReactNode }) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description}>{action}</Empty>;
}
