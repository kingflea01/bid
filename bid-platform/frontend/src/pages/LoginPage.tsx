import { useState } from 'react';
import { Alert, Button, Form, Input } from 'antd';
import { ArrowRightOutlined, FileTextOutlined, LockOutlined, UserOutlined } from '@ant-design/icons';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../app/auth';

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (user) return <Navigate to="/projects" replace />;

  const submit = async (values: { username: string; password: string }) => {
    setSubmitting(true);
    setError('');
    try {
      await login(values.username, values.password);
      const from = (location.state as { from?: string } | null)?.from || '/projects';
      navigate(from, { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败，请检查账号和密码');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-brand-pane" aria-label="标书工坊">
        <div className="login-brand">
          <span className="login-brand-mark"><FileTextOutlined /></span>
          <span>标书工坊</span>
        </div>
        <div className="login-brand-copy">
          <span className="login-kicker">BID STUDIO · 企业内网</span>
          <h1>把每一次响应，<br />落实到可追溯的章节。</h1>
          <p>招标解析、内容版本、人工确认与快照导出，在同一个受控工作流中完成。</p>
        </div>
        <div className="login-brand-foot">结构化内容 · 确定性门禁 · 全程留痕</div>
      </section>
      <section className="login-form-pane">
        <div className="login-form-wrap">
          <div className="login-form-heading">
            <span>工作台登录</span>
            <h2>继续您的应标工作</h2>
            <p>使用平台分配的账号登录。</p>
          </div>
          {error && <Alert className="login-error" type="error" showIcon message={error} />}
          <Form layout="vertical" onFinish={(values) => void submit(values)} requiredMark={false} size="large">
            <Form.Item name="username" label="账号" rules={[{ required: true, message: '请输入账号' }]}>
              <Input prefix={<UserOutlined />} placeholder="请输入账号" autoComplete="username" autoFocus />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting} icon={<ArrowRightOutlined />} iconPosition="end">
              登录工作台
            </Button>
          </Form>
          <div className="login-security">会话由安全 Cookie 维护，请勿在公用设备上保存密码。</div>
        </div>
      </section>
    </main>
  );
}
