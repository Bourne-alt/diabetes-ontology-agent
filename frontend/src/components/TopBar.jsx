import { Mark } from './Icons.jsx';

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="brand">
        <Mark />
        <div>
          <h1>本体智能体</h1>
          <div className="lbl sub">Ontology Evidence Console</div>
        </div>
      </div>
    </header>
  );
}
