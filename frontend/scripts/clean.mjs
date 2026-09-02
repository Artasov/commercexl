import {rmSync} from "node:fs";
import {fileURLToPath} from "node:url";

for (const path of ["../packages/ui/dist", "../packages/ui/tsconfig.tsbuildinfo"]) {
  rmSync(fileURLToPath(new URL(path, import.meta.url)), {force: true, recursive: true});
}
