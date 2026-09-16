import { CARDS } from '../miniprogram/data/cards';

const errors: string[] = [];
const allowedCategories = new Set([
  'preopen',
  'close',
  'weekend',
  'evidence',
  'risk',
  'emotion',
  'discipline',
  'information',
  'portfolio',
  'review',
  'uncertainty',
  'life'
]);
const prohibited = [
  /神谕/,
  /抽签/,
  /预测涨跌/,
  /必[涨跌]/,
  /稳赚/,
  /保本/,
  /目标价/,
  /收益(保证|承诺)/,
  /建议(买入|卖出)/,
  /[买卖](入|出)[“"'：:]?[A-Z\u4e00-\u9fff]{2,}/,
  /\b(?:SH|SZ)?[036]\d{5}\b/i
];

if (CARDS.length < 120 || CARDS.length > 200) {
  errors.push(`内容数量应为 120–200，实际为 ${CARDS.length}`);
}

const ids = new Set<string>();
const bodies = new Set<string>();
for (const card of CARDS) {
  if (!/^card-\d{3}$/.test(card.id)) errors.push(`${card.id}: ID 格式错误`);
  if (ids.has(card.id)) errors.push(`${card.id}: ID 重复`);
  ids.add(card.id);
  if (!card.title.trim()) errors.push(`${card.id}: 标题为空`);
  if (!card.shortAnswer.trim()) errors.push(`${card.id}: 短答为空`);
  if (!card.reflectionQuestion.endsWith('？')) errors.push(`${card.id}: 反思问题须以问号结尾`);
  if (
    !['不构成', '不提供', '不评价', '不替代', '不生成', '教育'].some((phrase) =>
      card.boundary.includes(phrase)
    )
  ) {
    errors.push(`${card.id}: 适用边界不明确`);
  }
  if (!allowedCategories.has(card.category)) errors.push(`${card.id}: 分类无效`);
  if (!/^\d+\.\d+\.\d+$/.test(card.version)) errors.push(`${card.id}: 版本格式错误`);
  if (card.reviewStatus !== 'approved') errors.push(`${card.id}: 首发内容未批准`);
  const body = `${card.title}|${card.shortAnswer}|${card.reflectionQuestion}`;
  if (bodies.has(body)) errors.push(`${card.id}: 正文组合重复`);
  bodies.add(body);
  for (const pattern of prohibited) {
    if (pattern.test(body)) errors.push(`${card.id}: 命中禁用模式 ${pattern}`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`内容校验通过：${CARDS.length} 条，${ids.size} 个唯一 ID，全部为 approved。`);
