const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Compile only repository modules with the existing TypeScript dependency.
const sourceRoot = path.resolve(__dirname, "../..");
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(`${sourceRoot}${path.sep}`));
    const result = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
      fileName: filename,
    });
    module._compile(result.outputText, filename);
  };
}

const { helpGuides, frequentGuideSlugs } = require("./content/index.ts");
const { helpCategories } = require("./types.ts");
const { searchHelpGuides, normalizeHelpSearch, getRelatedGuides, isYouTubeUrl } = require("./helpers.ts");
const { navigationItems, filterNavigationByRole } = require("../../components/layout/navigation-items.ts");
const { HelpArticle } = require("./components/help-article.tsx");
const { HelpHome } = require("./components/help-home.tsx");

test("search finds user vocabulary, ignores accents/case/spacing and combines terms", () => {
  const slugs = (query, category) => searchHelpGuides(helpGuides, query, category).map((guide) => guide.slug);
  assert.ok(slugs("excel").includes("importar-inventario"));
  assert.ok(slugs("PÁGO").includes("registrar-pagos"));
  assert.ok(slugs("pago").includes("formas-pago"));
  assert.ok(slugs("mascota").includes("registrar-paciente"));
  assert.ok(slugs("proveedor").includes("registrar-compra"));
  assert.ok(slugs("  IMPORTAR   ÍNVENTARIO ").includes("importar-inventario"));
  assert.ok(slugs("usuarios y permisos").includes("entender-roles"));
  assert.equal(slugs("", "inventario").length, helpGuides.filter((guide) => guide.category === "inventario").length);
  assert.deepEqual(slugs("excel", "ventas"), []);
  assert.deepEqual(slugs("palabrainexistente"), []);
  assert.equal(slugs("   ").length, helpGuides.length);
  assert.equal(normalizeHelpSearch("  ÁGENDA\t Clínica  "), "agenda clinica");
});

test("guides have unique slugs, canonical routes, valid references and complete metadata", () => {
  const slugs = new Set(helpGuides.map((guide) => guide.slug));
  assert.equal(slugs.size, helpGuides.length);
  assert.equal(frequentGuideSlugs.length, 6);
  assert.equal(new Set(frequentGuideSlugs).size, 6);
  for (const slug of frequentGuideSlugs) assert.ok(slugs.has(slug));
  for (const category of Object.keys(helpCategories)) assert.ok(helpGuides.some((guide) => guide.category === category));
  for (const guide of helpGuides) {
    assert.match(guide.slug, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    assert.ok(guide.title && guide.description && guide.keywords.length);
    assert.ok(helpCategories[guide.category]);
    assert.match(guide.updatedAt, /^\d{4}-\d{2}-\d{2}$/);
    assert.equal(new Date(guide.updatedAt).toISOString().slice(0, 10), guide.updatedAt);
    assert.ok(guide.steps.length >= 3 && guide.steps.length <= 8, guide.slug);
    assert.ok(guide.relatedGuides.length >= 2 && guide.relatedGuides.length <= 4);
    assert.equal(new Set(guide.relatedGuides).size, guide.relatedGuides.length);
    for (const related of guide.relatedGuides) {
      assert.ok(slugs.has(related), `${guide.slug}: ${related}`);
      assert.notEqual(related, guide.slug);
    }
    for (const item of [guide, ...guide.steps]) {
      if (item.appRoute) {
        assert.ok(item.appRouteLabel);
        assert.match(item.appRoute, /^\/(?!\/)/);
        const route = item.appRoute.split(/[?#]/)[0];
        assert.ok(!["/inventario", "/ajustes", "/sales/fiscal-issuers"].includes(route));
        assert.ok(fs.existsSync(path.join(sourceRoot, "app", route, "page.tsx")), `${guide.slug}: ${route}`);
      }
      if (item.imageSrc) {
        assert.ok(item.imageAlt);
        assert.ok(item.imageSrc.startsWith("/help/"));
        assert.ok(fs.existsSync(path.join(sourceRoot, "../public", item.imageSrc)));
      }
    }
    assert.doesNotMatch(JSON.stringify([guide.title, guide.description, guide.steps, guide.tips]), /\b(endpoint|payload|UUID|API|FK|tenant_id|mutation|schema|backend|tax_id)\b/i);
    if (guide.youtubeUrl) assert.ok(isYouTubeUrl(guide.youtubeUrl));
  }
});

test("help is available in sidebar navigation for every authenticated role", () => {
  for (const role of ["clinic_admin", "medico_veterinario", "contador", "superadmin"]) {
    assert.ok(filterNavigationByRole(navigationItems, role).some((item) => item.href === "/help"));
  }
  assert.deepEqual(filterNavigationByRole(navigationItems, "contador").map((item) => item.href), ["/accounting", "/help"]);
});

test("home renders a search control, categories, frequent tasks and guide links", () => {
  const html = renderToStaticMarkup(React.createElement(HelpHome));
  for (const text of ["Centro de ayuda", "Tareas frecuentes", "Explorar por módulo", "Todas las guías", 'type="search"', 'aria-controls="help-results"']) assert.ok(html.includes(text));
  for (const guide of helpGuides) assert.ok(html.includes(`/help/${guide.slug}`));
  const filtered = renderToStaticMarkup(React.createElement(HelpHome, { initialCategory: "inventario" }));
  assert.ok(filtered.includes('/help/importar-inventario'));
  assert.ok(!filtered.includes('/help/registrar-paciente'));
});

test("every article renders numbered steps and related guides without multimedia placeholders", () => {
  for (const guide of helpGuides) {
    const html = renderToStaticMarkup(React.createElement(HelpArticle, { guide }));
    assert.ok(html.includes('<ol class="help-steps">'));
    assert.ok(html.includes("Guías relacionadas"));
    assert.ok(html.includes("Volver al Centro de ayuda"));
    assert.ok(!html.includes("<img"));
    assert.ok(!html.includes("<iframe"));
    assert.ok(!html.includes("Ver tutorial en video"));
    for (const related of getRelatedGuides(guide, helpGuides)) assert.ok(html.includes(`/help/${related.slug}`));
  }
});

test("optional screenshots and YouTube links render accessibly; invalid video URLs are rejected", () => {
  const guide = { ...helpGuides[0], youtubeUrl: "https://www.youtube.com/watch?v=test-fixture", steps: [{ title: "Captura de prueba", description: "Solo para la prueba", imageSrc: "/help/test-fixture.png", imageAlt: "Pantalla de prueba" }] };
  const html = renderToStaticMarkup(React.createElement(HelpArticle, { guide }));
  assert.ok(html.includes('alt="Pantalla de prueba"'));
  assert.ok(html.includes('src="/help/test-fixture.png"'));
  assert.ok(html.includes('target="_blank" rel="noreferrer"'));
  assert.ok(html.includes("Ver tutorial en video"));
  assert.ok(isYouTubeUrl("https://youtu.be/test-fixture"));
  for (const url of ["javascript:alert(1)", "https://youtube.com.evil.test/video", "http://youtube.com/watch?v=x", "not-a-url", "https://user:pass@youtube.com/watch?v=x"]) assert.equal(isYouTubeUrl(url), false);
});
