window.SafeLease = {
  value(value, fallback = '-') {
    return value === null || value === undefined || value === '' ? fallback : value;
  },
  fmt(value, digits = 1) {
    return Number.isFinite(Number(value))
      ? Number(value).toLocaleString('ko-KR', { maximumFractionDigits: digits })
      : '-';
  },
  boolValue(value) {
    if (value === 'true') return true;
    if (value === 'false') return false;
    return null;
  },
  levelClass(level) {
    return {
      '낮음': 'level-low',
      '주의': 'level-caution',
      '높음': 'level-high',
      '매우 높음': 'level-very-high',
      '자료 부족': 'level-missing',
    }[level] || 'level-missing';
  },
  riskLevelLabel(level) {
    return {
      '낮음': '안전',
      '주의': '주의',
      '높음': '위험',
      '매우 높음': '매우 위험',
      '자료 부족': '자료 부족',
    }[level] || '자료 부족';
  },
  decisionLabel(decision) {
    return {
      STOP: '계약 중단',
      HOLD: '확인 전 보류',
      REVIEW: '조건 재검토',
      CONDITIONAL: '조건부 진행',
    }[decision] || '판정 확인';
  },
  priorityClass(priority) {
    if (priority === '계약 중단 검토' || priority === '계약 중단') return 'priority-stop';
    if (priority === '필수') return 'priority-required';
    if (priority === '주의') return 'priority-caution';
    return 'priority-recommended';
  },
};
