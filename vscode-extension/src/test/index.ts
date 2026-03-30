import * as path from "path";
import * as fs from "fs";
import Mocha from "mocha";

export function run(): Promise<void> {
  const mocha = new Mocha({ ui: "tdd", color: true, timeout: 30_000 });
  const testsRoot = path.resolve(__dirname, ".");

  return new Promise((resolve, reject) => {
    try {
      const files = fs
        .readdirSync(testsRoot)
        .filter((f) => f.endsWith(".test.js"));
      files.forEach((f) => mocha.addFile(path.resolve(testsRoot, f)));
      mocha.run((failures) => {
        if (failures > 0) {
          reject(new Error(`${failures} test(s) failed.`));
        } else {
          resolve();
        }
      });
    } catch (err) {
      reject(err);
    }
  });
}
