const { Anthropic } = require('@anthropic-ai/sdk');
const fs = require('fs');
const path = require('path');

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const ISSUE_NUMBER = process.env.ISSUE_NUMBER || process.argv[2];

async function main() {
  // خواندن اطلاعات issue
  const issue = await fetchIssue(ISSUE_NUMBER);
  
  // خواندن تاریخچه قبلی
  const history = await readHistory(ISSUE_NUMBER);
  
  // اجرای agent
  const response = await runAgent(issue, history);
  
  // ذخیره پاسخ
  await saveResponse(ISSUE_NUMBER, response);
}

async function fetchIssue(number) {
  const res = await fetch(`https://api.github.com/repos/${process.env.GITHUB_REPOSITORY}/issues/${number}`, {
    headers: { Authorization: `token ${GITHUB_TOKEN}` }
  });
  return res.json();
}

async function readHistory(issueNumber) {
  const sessionPath = path.join('state', 'sessions', `${issueNumber}.jsonl`);
  if (!fs.existsSync(sessionPath)) return [];
  
  const lines = fs.readFileSync(sessionPath, 'utf8').trim().split('\n');
  return lines.map(line => JSON.parse(line));
}

async function runAgent(issue, history) {
  // ابزارها: خواندن کانفیگ V2Ray
  const tools = [
    {
      name: 'read_configs',
      description: 'خواندن کانفیگ‌های V2Ray از پوشه configs/',
      input_schema: {
        type: 'object',
        properties: {
          filter_isp: { type: 'string', description: 'نام ISP (مثلاً Irancell, MCI)' },
          max_ping: { type: 'number', description: 'حداکثر پینگ مجاز' },
          limit: { type: 'number', default: 5 }
        }
      }
    },
    {
      name: 'trigger_collector',
      description: 'اجرای دستی collector برای آپدیت کانفیگ‌ها',
      input_schema: { type: 'object', properties: {} }
    }
  ];

  const messages = [
    ...history.flatMap(h => [
      { role: 'user', content: h.user },
      { role: 'assistant', content: h.assistant }
    ]),
    { role: 'user', content: issue.body }
  ];

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 4096,
    tools,
    messages
  });

  return response;
}

async function saveResponse(issueNumber, response) {
  // ذخیره در issue
  await fetch(`https://api.github.com/repos/${process.env.GITHUB_REPOSITORY}/issues/${issueNumber}/comments`, {
    method: 'POST',
    headers: {
      Authorization: `token ${GITHUB_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ body: response.content[0].text })
  });

  // ذخیره در state
  const stateDir = path.join('state', 'sessions');
  if (!fs.existsSync(stateDir)) fs.mkdirSync(stateDir, { recursive: true });
  
  const sessionPath = path.join(stateDir, `${issueNumber}.jsonl`);
  fs.appendFileSync(sessionPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    user: process.env.ISSUE_BODY,
    assistant: response.content[0].text
  }) + '\n');
}

main().catch(console.error);
