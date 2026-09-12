const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Use the installed TypeScript compiler and Node test runner; no added packages.
const sourceRoot = path.resolve(__dirname, "../..");
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...args) {
  return originalResolve.call(this, request.startsWith("@/") ? path.join(sourceRoot, request.slice(2)) : request, ...args);
};
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(`${sourceRoot}${path.sep}`));
    const { outputText } = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      fileName: filename,
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    });
    module._compile(outputText, filename);
  };
}

const { SaleOwnerSelector } = require("./components/sale-owner-selector.tsx");
const { getOwners } = require("../../services/owners.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");

test("editing retains the saved owner label without loading the first page", () => {
  const html = renderToStaticMarkup(React.createElement(SaleOwnerSelector, {
    ownerId: "beyond-page-one", ownerName: "Zulema Juanita Torres", onSelect() {},
  }));
  assert.ok(html.includes("Zulema Juanita Torres"));
  assert.ok(html.includes('aria-expanded="false"'));
  assert.ok(!html.includes("Venta de mostrador"));
});

test("new sales preserve the optional storefront selection", () => {
  const html = renderToStaticMarkup(React.createElement(SaleOwnerSelector, {
    ownerId: "", ownerName: "", onSelect() {},
  }));
  assert.ok(html.includes("Venta de mostrador"));
  assert.ok(html.includes('type="button"'));
});

test("owner API sends server search, page and opt-in name order with authentication", async () => {
  const previousFetch = global.fetch;
  setAuthTokenProvider(async () => "test-token");
  setActingTenantId(null);
  const requests = [];
  global.fetch = async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/api/v1/owners");
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    assert.equal(init.headers.has("X-Tenant-Id"), false);
    assert.equal(init.headers.has("X-Acting-Tenant-Id"), false);
    requests.push(Object.fromEntries(parsed.searchParams));
    return new Response(JSON.stringify({ data: [], meta: { page: 1, page_size: 30, total: 0 } }), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    await getOwners({ search: "Juanita Torres", page: 1, pageSize: 30, sortBy: "full_name" });
    await getOwners({ page: 7, pageSize: 30, sortBy: "full_name" });
    await getOwners();
    assert.deepEqual(requests, [
      { search: "Juanita Torres", page: "1", page_size: "30", sort_by: "full_name" },
      { page: "7", page_size: "30", sort_by: "full_name" },
      {},
    ]);
  } finally {
    global.fetch = previousFetch;
    setAuthTokenProvider(null);
  }
});
