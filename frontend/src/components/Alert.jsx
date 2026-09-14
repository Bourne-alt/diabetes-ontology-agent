export default function Alert({ alert }) {
  if (!alert) return null;
  return (
    <section className={`alert alert--${alert.kind}`}>
      <span className="alert__bar" />
      <div>
        <h2>{alert.title}</h2>
        <p>{alert.text}</p>
      </div>
    </section>
  );
}
