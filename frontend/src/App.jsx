import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clock3,
  Inbox,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Users,
} from "lucide-react";

const examples = [
  "我昨天充值了100元，但是余额一直没有到账，订单号是 20261008001。",
  "所有用户都无法登录，页面一直提示系统异常，请尽快处理。",
  "我的账号刚刚收到异地登录提醒，验证码也不是我操作的。",
  "申请退款，商品没有使用过，麻烦帮我看一下退款进度。",
];

const initialStats = { total: 0, auto_routed: 0, needs_review: 0, by_team: {} };

async function request(url, options) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(text || `请求失败（HTTP ${response.status}）`);
  }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `请求失败（HTTP ${response.status}）`);
  }
  return data;
}

function sourceName(source) {
  return { jev: "JEV", mock: "Mock", llm_fallback: "大模型兜底" }[source] || source;
}

function App() {
  const [content, setContent] = useState(examples[0]);
  const [result, setResult] = useState(null);
  const [stats, setStats] = useState(initialStats);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);

  const loadDashboard = async () => {
    const [nextStats, nextTickets, nextHealth] = await Promise.all([
      request("/api/stats"),
      request("/api/tickets?limit=8"),
      request("/api/health"),
    ]);
    setStats(nextStats);
    setTickets(nextTickets);
    setHealth(nextHealth);
  };

  useEffect(() => {
    loadDashboard().catch((e) => setError(e.message));
  }, []);

  const teamCards = useMemo(
    () => [
      { label: "客服团队", icon: Users, tone: "blue" },
      { label: "技术团队", icon: Bot, tone: "purple" },
      { label: "财务团队", icon: Inbox, tone: "green" },
      { label: "安全团队", icon: ShieldAlert, tone: "red" },
    ],
    [],
  );

  const analyze = async () => {
    if (!content.trim()) return;
    setLoading(true);
    setError("");
    try {
      const next = await request("/api/tickets/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setResult(next);
      await loadDashboard();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div>
            <p className="eyebrow">AI OPERATIONS CONSOLE</p>
            <h1>智能工单分流台</h1>
          </div>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />
          {health?.jev_configured ? "JEV 已配置" : "演示模式"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow accent">TICKET ROUTING / 01</p>
          <h2>让每一条工单，<em>更快找到</em>正确的人。</h2>
          <p className="hero-copy">
            JEV 负责高速判断，业务规则负责安全兜底。遇到不确定或高风险问题，自动交给人工复核。
          </p>
        </div>
        <div className="hero-orbit">
          <div className="orbit-ring ring-one" />
          <div className="orbit-ring ring-two" />
          <div className="orbit-center"><Sparkles size={27} /></div>
        </div>
      </section>

      <section className="metric-grid">
        <Metric icon={Inbox} label="已处理工单" value={stats.total} />
        <Metric icon={ArrowUpRight} label="自动分流" value={stats.auto_routed} accent />
        <Metric icon={AlertTriangle} label="待人工复核" value={stats.needs_review} warning />
        <Metric icon={Clock3} label="配置模式" value={health?.jev_configured ? "JEV" : "Mock"} text />
      </section>

      <section className="workspace-grid">
        <div className="panel compose-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">NEW TICKET</p>
              <h3>提交一条工单</h3>
            </div>
            <span className="step-tag">STEP 01</span>
          </div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="描述用户遇到的问题……"
          />
          <div className="examples">
            {examples.map((item, index) => (
              <button key={item} onClick={() => setContent(item)}>示例 {index + 1}</button>
            ))}
          </div>
          <button className="primary-button" onClick={analyze} disabled={loading}>
            {loading ? <RefreshCw className="spin" size={17} /> : <Send size={17} />}
            {loading ? "正在分析…" : "开始智能分流"}
          </button>
          {error && <div className="error-box">{error}</div>}
        </div>

        <div className="panel result-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">ROUTING RESULT</p>
              <h3>分流判断</h3>
            </div>
            {result && <span className="source-tag">{sourceName(result.source)}</span>}
          </div>
          {result ? <ResultCard result={result} /> : <EmptyResult />}
        </div>
      </section>

      <section className="bottom-grid">
        <div className="panel">
          <div className="panel-heading compact">
            <div><p className="eyebrow">QUEUE OVERVIEW</p><h3>团队队列</h3></div>
          </div>
          <div className="queue-list">
            {teamCards.map(({ label, icon: Icon, tone }) => (
              <div className="queue-item" key={label}>
                <div className={`queue-icon ${tone}`}><Icon size={17} /></div>
                <span>{label}</span>
                <strong>{stats.by_team[label] || 0}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="panel recent-panel">
          <div className="panel-heading compact">
            <div><p className="eyebrow">RECENT ACTIVITY</p><h3>最近分流</h3></div>
            <button className="icon-button" onClick={() => loadDashboard()}><RefreshCw size={16} /></button>
          </div>
          {tickets.length ? (
            <div className="recent-list">
              {tickets.map((ticket) => (
                <div className="recent-item" key={ticket.id}>
                  <div className={`mini-status ${ticket.needs_review ? "review" : "done"}`}>
                    {ticket.needs_review ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
                  </div>
                  <div className="recent-content">
                    <strong>{ticket.category}</strong>
                    <span>{ticket.content}</span>
                  </div>
                  <div className="recent-team">{ticket.team}</div>
                </div>
              ))}
            </div>
          ) : <div className="empty-small">分析一条工单后，最近记录会出现在这里。</div>}
        </div>
      </section>
    </main>
  );
}

function Metric({ icon: Icon, label, value, accent, warning, text }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${accent ? "green" : warning ? "orange" : "blue"}`}><Icon size={17} /></div>
      <div><span>{label}</span><strong className={text ? "text-value" : ""}>{value}</strong></div>
    </div>
  );
}

function ResultCard({ result }) {
  const fields = [
    ["工单类型", result.category],
    ["优先级", result.priority],
    ["负责团队", result.team],
    ["处理动作", result.action],
  ];
  return (
    <div className="result-content">
      <div className={`decision-banner ${result.needs_review ? "is-review" : "is-done"}`}>
        {result.needs_review ? <AlertTriangle size={19} /> : <CheckCircle2 size={19} />}
        <div>
          <strong>{result.needs_review ? "需要人工复核" : "已完成自动分流"}</strong>
          <span>{result.needs_review ? "模型信心不足或命中高风险规则" : "这条工单可以直接进入对应团队队列"}</span>
        </div>
      </div>
      <div className="result-fields">
        {fields.map(([label, value]) => <div className="result-field" key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      <div className="confidence-row">
        <div><span>模型置信度</span><strong>{Math.round(result.confidence * 100)}%</strong></div>
        <div className="progress"><span style={{ width: `${result.confidence * 100}%` }} /></div>
      </div>
      <div className="reason"><span>判断依据</span><p>{result.reason}</p></div>
    </div>
  );
}

function EmptyResult() {
  return <div className="empty-result"><div className="empty-icon"><Sparkles size={23} /></div><strong>等待一条工单</strong><span>输入左侧内容，JEV 会返回结构化分流结果。</span></div>;
}

export default App;

