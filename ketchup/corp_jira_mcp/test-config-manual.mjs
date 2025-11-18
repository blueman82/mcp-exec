// Manual test to verify config loads PAT fields correctly
process.env.JIRA_EMAIL = 'test@adobe.com';
process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
process.env.USE_IPAAS = 'false';
process.env.JIRA_PAT = 'test_pat_12345';
process.env.JIRA_PAT_BACKUP = 'backup_pat_67890';
process.env.JIRA_USE_PAT_AUTH = 'true';
process.env.JIRA_USERNAME = 'testuser';
process.env.JIRA_PASSWORD = 'testpass';

import { config } from './dist/common/config.js';

console.log('PAT Config Test Results:');
console.log('========================');
console.log('pat:', config.auth.pat);
console.log('patBackup:', config.auth.patBackup);
console.log('usePat:', config.auth.usePat);
console.log('username:', config.auth.username);
console.log('password:', config.auth.password);
console.log('========================');

// Verify values
const tests = [
  { name: 'PAT is set', actual: config.auth.pat, expected: 'test_pat_12345' },
  { name: 'PAT Backup is set', actual: config.auth.patBackup, expected: 'backup_pat_67890' },
  { name: 'usePat is true', actual: config.auth.usePat, expected: true },
  { name: 'username preserved', actual: config.auth.username, expected: 'testuser' },
  { name: 'password preserved', actual: config.auth.password, expected: 'testpass' }
];

let passed = 0;
let failed = 0;

tests.forEach(test => {
  if (test.actual === test.expected) {
    console.log(`✓ ${test.name}`);
    passed++;
  } else {
    console.log(`✗ ${test.name}: expected ${test.expected}, got ${test.actual}`);
    failed++;
  }
});

console.log(`\nResults: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
