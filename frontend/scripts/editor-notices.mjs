import fs from "node:fs";
const names = fs
  .readdirSync("node_modules")
  .filter(
    (name) =>
      name.startsWith("prosemirror-") ||
      ["orderedmap", "rope-sequence", "w3c-keyname"].includes(name),
  )
  .sort();
if (names.length !== 10)
  throw new Error("Review editor dependency license inventory");
let notices =
  "Editor dependency notices. These licenses apply to the named dependencies, not to Fillable itself.\n";
for (const name of names) {
  const root = `node_modules/${name}`;
  const pkg = JSON.parse(fs.readFileSync(`${root}/package.json`));
  if (pkg.license !== "MIT") throw new Error(`Review license: ${name}`);
  notices += `\n${name} ${pkg.version}\n${fs.readFileSync(`${root}/LICENSE`, "utf8")}\n`;
}
fs.mkdirSync("public", { recursive: true });
fs.writeFileSync("public/editor-notices.txt", notices.trimEnd() + "\n");
