const fs = require("node:fs");
const { bnUnicode2ANSI } = require("bnunicode2ansi");

const input = fs.readFileSync(0, "utf8");
const values = JSON.parse(input);
const originalLog = console.log;
console.log = () => {};

try {
  const converted = values.map((value) => bnUnicode2ANSI(String(value)));
  console.log = originalLog;
  process.stdout.write(JSON.stringify({ converted }));
} catch (error) {
  console.log = originalLog;
  process.stdout.write(JSON.stringify({ error: error.message || String(error) }));
  process.exitCode = 1;
}
