import { readFileSync } from 'node:fs';

const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const expectedVersion = packageJson.engines?.npm;
const userAgent = process.env.npm_config_user_agent;
const actualVersion = userAgent?.match(/^npm\/([^\s]+)/)?.[1];

if (!actualVersion) {
  console.error('Could not determine the npm version. Run this command through npm.');
  process.exit(1);
}

if (actualVersion !== expectedVersion) {
  console.error(`Unsupported npm version ${actualVersion}; this project requires npm ${expectedVersion}.\nRun "nvm use" to switch to the correct Node.js and npm versions.\n`);
  process.exit(1);
}
