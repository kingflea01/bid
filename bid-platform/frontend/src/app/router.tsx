import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import AppShell from './AppShell';
import { ProtectedRoute } from './auth';

const LoginPage = lazy(() => import('../pages/LoginPage'));
const ProjectListPage = lazy(() => import('../pages/ProjectListPage'));
const ProjectCreatePage = lazy(() => import('../pages/ProjectCreatePage'));
const AnalysisPage = lazy(() => import('../pages/AnalysisPage'));
const WorkspacePage = lazy(() => import('../pages/WorkspacePage'));
const ExportCenterPage = lazy(() => import('../pages/ExportCenterPage'));
const CompaniesPage = lazy(() => import('../pages/config/CompaniesPage'));
const ProductsPage = lazy(() => import('../pages/config/ProductsPage'));
const AssetsPage = lazy(() => import('../pages/config/AssetsPage'));
const RedlinesPage = lazy(() => import('../pages/config/RedlinesPage'));
const TemplatesPage = lazy(() => import('../pages/config/TemplatesPage'));

const load = (node: React.ReactNode) => <Suspense fallback={<div className="page-loading"><Spin /></div>}>{node}</Suspense>;

export const router = createBrowserRouter([
  { path: '/login', element: load(<LoginPage />) },
  {
    path: '/',
    element: <ProtectedRoute><AppShell /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="/projects" replace /> },
      { path: 'projects', element: load(<ProjectListPage />) },
      { path: 'projects/new', element: load(<ProjectCreatePage />) },
      { path: 'projects/:projectId/analysis', element: load(<AnalysisPage />) },
      { path: 'projects/:projectId/workspace', element: load(<WorkspacePage />) },
      { path: 'projects/:projectId/exports', element: load(<ExportCenterPage />) },
      { path: 'config/companies', element: load(<CompaniesPage />) },
      { path: 'config/products', element: load(<ProductsPage />) },
      { path: 'config/assets', element: load(<AssetsPage />) },
      { path: 'config/redlines', element: load(<RedlinesPage />) },
      { path: 'config/templates', element: load(<TemplatesPage />) },
    ],
  },
  { path: '*', element: <Navigate to="/projects" replace /> },
]);
