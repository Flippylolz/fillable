import { expect, test } from "@playwright/test";
import { sourceRules } from "../src/editor/SourceLayout";

test("anchored number boxes leave their label alongside and the next row below", async ({ page }, info) => {
  const positions = [165, 235, 305, 405];
  const nodes: Record<string, object> = {
    label: { position: "relative", "margin-top": "9pt", "margin-bottom": "0pt", clear: "none" },
    next: { clear: "both" },
  };
  positions.forEach((left, index) => {
    nodes[`box${index}`] = { display: "inline-table", float: "left", position: "relative", left: `${left}pt`, width: "50pt", "margin-left": "0pt", "margin-right": "-50pt", "margin-top": "10pt", "box-sizing": "border-box", "border-collapse": "collapse" };
  });
  await page.setContent(`<style>${sourceRules("test", { section: { width: "600pt", padding: "20pt" }, nodes })}
    td { border:1px solid black; height:24pt; text-align:center; } p { margin:0; }
    </style><div data-layout="test"><div class="ProseMirror"><section data-part="word/document.xml">
    ${positions.map((_, i) => `<table data-source="box${i}"><tr><td>0</td><td>${i}</td></tr></table>`).join("")}
    <p data-source="label">8. Registration number</p><p data-source="next">9. Registration date</p>
    </section></div></div>`);
  const geometry = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll("table")].map(e => e.getBoundingClientRect().toJSON());
    const label = document.querySelector('[data-source="label"]')!.getBoundingClientRect().toJSON();
    const next = document.querySelector('[data-source="next"]')!.getBoundingClientRect().toJSON();
    return { boxes, label, next };
  });
  expect(geometry.label.top).toBeLessThan(geometry.boxes[0].bottom);
  expect(geometry.label.bottom).toBeGreaterThan(geometry.boxes[0].top);
  for (const box of geometry.boxes) expect(geometry.next.top).toBeGreaterThanOrEqual(box.bottom);
  expect(geometry.boxes[1].left - geometry.boxes[0].left).toBeCloseTo(70 * 4 / 3, 0);
  await page.screenshot({ path: info.outputPath("anchored-number-row.png") });
});
