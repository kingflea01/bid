import { useMemo, useState } from 'react';
import { Avatar, Button, Drawer, Dropdown, Layout, Menu } from 'antd';
import {
  ApartmentOutlined,
  AuditOutlined,
  BankOutlined,
  DatabaseOutlined,
  DownOutlined,
  FileDoneOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MenuOutlined,
  ProductOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './auth';

const { Header, Sider, Content } = Layout;

export default function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const projectId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];

  const items = useMemo(() => {
    const base = [
      { key: '/projects', icon: <FolderOpenOutlined />, label: <Link to="/projects">应标项目</Link> },
      ...(projectId
        ? [
            { key: `/projects/${projectId}/analysis`, icon: <AuditOutlined />, label: <Link to={`/projects/${projectId}/analysis`}>招标分析</Link> },
            { key: `/projects/${projectId}/workspace`, icon: <FileTextOutlined />, label: <Link to={`/projects/${projectId}/workspace`}>章节工作区</Link> },
            { key: `/projects/${projectId}/exports`, icon: <FileDoneOutlined />, label: <Link to={`/projects/${projectId}/exports`}>快照与导出</Link> },
          ]
        : []),
      {
        key: 'config',
        icon: <SettingOutlined />,
        label: '配置中心',
        children: [
          { key: '/config/companies', icon: <BankOutlined />, label: <Link to="/config/companies">企业配置</Link> },
          { key: '/config/products', icon: <ProductOutlined />, label: <Link to="/config/products">产品配置</Link> },
          { key: '/config/assets', icon: <DatabaseOutlined />, label: <Link to="/config/assets">知识素材</Link> },
          { key: '/config/redlines', icon: <SafetyCertificateOutlined />, label: <Link to="/config/redlines">红线条款</Link> },
          { key: '/config/templates', icon: <ApartmentOutlined />, label: <Link to="/config/templates">标书模板</Link> },
        ],
      },
    ];
    return base;
  }, [projectId]);

  const selectedKey = location.pathname === '/projects/new'
    ? '/projects'
    : items.flatMap((item) => ('children' in item && item.children ? item.children : [item]))
        .filter((item) => item && 'key' in item)
        .sort((a, b) => String(b.key).length - String(a.key).length)
        .find((item) => location.pathname.startsWith(String(item.key)))?.key as string | undefined;

  const menu = (
    <Menu
      mode="inline"
      items={items}
      selectedKeys={selectedKey ? [selectedKey] : []}
      defaultOpenKeys={['config']}
      onClick={() => setMobileOpen(false)}
    />
  );

  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider" breakpoint="lg" collapsedWidth={0} trigger={null}>
        <Link to="/projects" className="brand">
          <span className="brand-mark"><FileTextOutlined /></span>
          <span><strong>标书工坊</strong><small>BID STUDIO</small></span>
        </Link>
        <div className="nav-caption">工作空间</div>
        {menu}
        <div className="sider-foot">
          <span className="system-dot" />
          <span>企业内网工作区</span>
        </div>
      </Sider>
      <Drawer className="mobile-nav-drawer" open={mobileOpen} onClose={() => setMobileOpen(false)} placement="left" width={260}>
        <Link to="/projects" className="brand" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark"><FileTextOutlined /></span>
          <span><strong>标书工坊</strong><small>BID STUDIO</small></span>
        </Link>
        {menu}
      </Drawer>
      <Layout>
        <Header className="app-topbar">
          <Button className="mobile-menu-button" type="text" icon={<MenuOutlined />} onClick={() => setMobileOpen(true)} aria-label="打开导航" />
          <div className="topbar-context">
            {projectId ? <><span>当前项目</span><strong>{projectId.slice(0, 8).toUpperCase()}</strong></> : <strong>投标内容管理平台</strong>}
          </div>
          <div className="topbar-spacer" />
          <Dropdown
            menu={{
              items: [{ key: 'logout', label: '退出登录' }],
              onClick: async ({ key }) => {
                if (key === 'logout') {
                  await logout();
                  navigate('/login', { replace: true });
                }
              },
            }}
          >
            <Button type="text" className="user-menu">
              <Avatar size={30}>{user?.display_name.slice(0, 1)}</Avatar>
              <span>{user?.display_name}</span>
              <DownOutlined className="user-menu-caret" />
            </Button>
          </Dropdown>
        </Header>
        <Content className={location.pathname.endsWith('/workspace') ? 'app-content workspace-content' : 'app-content'}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
