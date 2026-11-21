import { useState } from 'react';
import { Button, Input, Select, Space, Table, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { FileAddOutlined, HistoryOutlined, SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../app/api';
import { EmptyState, PageHeader, QueryError } from '../components/Common';
import { dateTime, projectStatus } from '../lib/format';
import { items, queryKeys, total } from '../lib/query';
import type { Project } from '../types';

export default function ProjectListPage() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>();
  const [page, setPage] = useState(1);
  const projects = useQuery({
    queryKey: [...queryKeys.projects, { search, status, page }],
    queryFn: () => api.projects.list({ keyword: search, status, page, page_size: 20 }),
    placeholderData: (previous) => previous,
  });

  const columns: ColumnsType<Project> = [
    {
      title: '项目',
      dataIndex: 'name',
      minWidth: 280,
      render: (_, record) => (
        <div className="project-cell">
          <Link to={`/projects/${record.id}/workspace`}>{record.name}</Link>
          <div><span>{record.code}</span>{record.package_name && <span> · {record.package_name}</span>}</div>
        </div>
      ),
    },
    { title: '客户', dataIndex: 'customer_name', width: 190, ellipsis: true },
    { title: '采购方式', dataIndex: 'procurement_type', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => {
        const meta = projectStatus[value] || { label: value, color: 'default' };
        return <Tag color={meta.color}>{meta.label}</Tag>;
      },
    },
    {
      title: '历史复用',
      dataIndex: 'source_project_id',
      width: 110,
      render: (value?: string) => value ? <span className="history-indicator"><HistoryOutlined /> 续约项目</span> : <span className="muted">—</span>,
    },
    { title: '创建时间', dataIndex: 'created_at', width: 155, render: dateTime },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => navigate(`/projects/${record.id}/workspace`)}>工作区</Button>
          <Button type="link" size="small" onClick={() => navigate(`/projects/${record.id}/analysis`)}>分析</Button>
          <Tooltip title="以此项目的最终确认章节作为续约候选">
            <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => navigate(`/projects/new?source_project_id=${record.id}`)}>续约</Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="PROJECTS"
        title="应标项目"
        description="从招标原件到确认快照，所有内容版本均保留来源与审阅状态。"
        extra={<Button type="primary" icon={<FileAddOutlined />} onClick={() => navigate('/projects/new')}>新建项目</Button>}
      />
      <div className="list-toolbar">
        <Input
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          onPressEnter={() => { setSearch(keyword); setPage(1); }}
          prefix={<SearchOutlined />}
          placeholder="搜索项目名称、编号或客户"
          allowClear
          className="project-search"
        />
        <Button onClick={() => { setSearch(keyword); setPage(1); }}>查询</Button>
        <Select
          value={status}
          onChange={(value) => { setStatus(value); setPage(1); }}
          allowClear
          placeholder="全部状态"
          className="status-select"
          options={Object.entries(projectStatus).map(([value, meta]) => ({ value, label: meta.label }))}
        />
        <div className="toolbar-spacer" />
        <Button icon={<HistoryOutlined />} onClick={() => navigate('/projects/new?renewal=1')}>从历史项目续约</Button>
      </div>
      <div className="list-meta">共 {total(projects.data)} 个项目<span>历史项目内容只作为候选，不自动覆盖新章节。</span></div>
      {projects.error ? (
        <QueryError error={projects.error as Error} retry={() => void projects.refetch()} />
      ) : (
        <Table<Project>
          rowKey="id"
          columns={columns}
          dataSource={items(projects.data)}
          loading={projects.isLoading || projects.isPlaceholderData}
          scroll={{ x: 1160 }}
          locale={{ emptyText: <EmptyState description="暂无项目，创建项目并上传招标文件即可开始" /> }}
          pagination={{
            current: page,
            pageSize: 20,
            total: total(projects.data),
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      )}
    </div>
  );
}
