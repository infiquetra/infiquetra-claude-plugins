#!/usr/bin/env node
/**
 * Headless mermaid.parse helper. Reads JSON [{path, line, text}, ...] on stdin
 * and writes JSON [{path, line, message}, ...] of parse failures to stdout.
 *
 * DOM globals are installed before mermaid is imported so the parser sees a
 * document; mermaid.parse() is syntax-only and does not render.
 */
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://example.test/",
});
const { window } = dom;

function assign(name, value) {
  try {
    globalThis[name] = value;
  } catch {
    Object.defineProperty(globalThis, name, {
      configurable: true,
      writable: true,
      value,
    });
  }
}

assign("window", window);
assign("document", window.document);
assign("DOMParser", window.DOMParser);
assign("XMLSerializer", window.XMLSerializer);
assign("HTMLElement", window.HTMLElement);
assign("SVGElement", window.SVGElement);
assign("Element", window.Element);
assign("Node", window.Node);
assign("getComputedStyle", window.getComputedStyle);

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });

const raw = await new Promise((resolve, reject) => {
  const chunks = [];
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => chunks.push(c));
  process.stdin.on("end", () => resolve(chunks.join("")));
  process.stdin.on("error", reject);
});

let items;
try {
  items = JSON.parse(raw);
} catch (err) {
  console.error(`HALT: helper stdin is not JSON: ${err}`);
  process.exit(3);
}
if (!Array.isArray(items)) {
  console.error("HALT: helper stdin must be a JSON array");
  process.exit(3);
}

const errors = [];
for (const item of items) {
  try {
    await mermaid.parse(item.text);
  } catch (err) {
    const message = err && err.message ? String(err.message) : String(err);
    errors.push({ path: item.path, line: item.line, message });
  }
}
process.stdout.write(JSON.stringify(errors));
