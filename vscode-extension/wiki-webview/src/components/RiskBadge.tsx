import { h } from 'preact';

interface Props {
  risk?: 'low' | 'medium' | 'high';
}

const COLORS: Record<string, string> = {
  low:    'var(--risk-low)',
  medium: 'var(--risk-medium)',
  high:   'var(--risk-high)',
};

export function RiskBadge({ risk }: Props) {
  if (!risk) return null;
  return (
    <span class="risk-badge" style={{ background: COLORS[risk] }}>
      {risk === 'high' ? '⚠ ' : risk === 'medium' ? '● ' : '○ '}
      {risk} risk
    </span>
  );
}
