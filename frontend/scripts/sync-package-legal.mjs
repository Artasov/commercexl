import {copyFileSync} from "node:fs";
import {fileURLToPath} from "node:url";

const root = new URL("../../", import.meta.url);
const packageRoot = new URL("../packages/ui/", import.meta.url);
for (const file of ["LICENSE", "NOTICE", "TRADEMARKS.md"]) {
  copyFileSync(fileURLToPath(new URL(file, root)), fileURLToPath(new URL(file, packageRoot)));
}
