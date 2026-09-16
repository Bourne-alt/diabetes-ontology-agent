import { Component } from 'react';

/* 界面渲染的是任意工具返回，字段形状随后端与数据而变。
 * 单个字段渲染失败不该让整页白屏 —— 出错就地降级成一条可读提示，其余内容照常。 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // 留在控制台供排查：这里通常是某个字段的真实形状与预期不符。
    console.error('[本体智能体] 渲染失败', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <section className="alert alert--bad">
        <span className="alert__bar" />
        <div>
          <h2>{this.props.label ?? '这部分内容渲染失败'}</h2>
          <p>
            本轮数据里有界面没预料到的字段形状，这一块已跳过，其余内容不受影响。
            原始事件仍在右侧「执行轨迹」里完整可见。
            <br />
            <code>{String(this.state.error?.message ?? this.state.error)}</code>
          </p>
        </div>
      </section>
    );
  }
}
