export function Mark({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#34477a" strokeWidth="1.2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="4.6" r="2.3" />
      <circle cx="4.6" cy="17.6" r="2.3" />
      <circle cx="19.4" cy="17.6" r="2.3" />
      <circle cx="12" cy="11.6" r="1.4" fill="#a3562a" stroke="none" />
      <path d="M12 6.9v3.3M10.8 12.6 6.2 16.1M13.2 12.6l4.6 3.5M6.9 17.6h10.2" />
    </svg>
  );
}

export function Warning({ size = 16, color = '#a3562a' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <path d="M12 3.5 2.8 20h18.4L12 3.5ZM12 10.2v4.1M12 17.2v.01" />
    </svg>
  );
}

export function Check({ size = 9 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 12.5 9.5 18 20 6.5" />
    </svg>
  );
}
