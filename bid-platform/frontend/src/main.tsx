import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import 'antd/dist/reset.css';
import './styles.css';
import { queryClient } from './app/queryClient';
import { AuthProvider } from './app/auth';
import { router } from './app/router';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#3158d4',
          colorInfo: '#3158d4',
          colorSuccess: '#23856d',
          colorWarning: '#b47517',
          colorError: '#bf454c',
          colorText: '#242a35',
          colorTextSecondary: '#6e7787',
          colorBorder: '#dfe3e9',
          colorBgLayout: '#f5f6f8',
          borderRadius: 7,
          fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          fontSize: 13,
          controlHeight: 34,
        },
        components: {
          Layout: { headerBg: '#ffffff', siderBg: '#f8f9fb' },
          Menu: { itemBorderRadius: 6, itemMarginInline: 10, subMenuItemBg: '#f8f9fb' },
          Table: { headerBg: '#f7f8fa', headerColor: '#687181', rowHoverBg: '#f7f9ff' },
          Card: { borderRadiusLG: 10 },
          Modal: { borderRadiusLG: 12 },
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
