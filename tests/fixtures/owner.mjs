// TC-SEED-001: use the built public ESM entry in a real independent process.
import { createSnowflake } from '../../packages/maia-snowflake/dist/index.js';
const generator = await createSnowflake({
  workerId: 9, statePath: process.argv[2], initialize: true, now: () => 1767225600200,
});
process.stdout.write(`${await generator.next()}\n`);
// Keep the process alive until the test sends SIGKILL. Do not release ownership.
setInterval(() => {}, 1000);
