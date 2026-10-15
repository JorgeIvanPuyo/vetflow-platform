const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

// Render the actual nested modal without mounting the unrelated patient screens.
const filename = path.join(__dirname, 'components/patient-detail.tsx');
const source = ts.createSourceFile(
  filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX,
);
let modal;
function findModal(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'renderPatientDeleteModal') {
    modal = node;
  }
  ts.forEachChild(node, findModal);
}
findModal(source);
assert.ok(modal, 'Patient deletion modal exists');
const compiled = ts.transpileModule(modal.getText(source), {
  compilerOptions: { jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2020 },
}).outputText;
const renderModal = new Function(
  'React', 'state', 'closePatientDeleteModal', 'handleDeletePatient',
  'deleteConfirmation', 'setDeleteConfirmation', 'X',
  `${compiled}\nreturn renderPatientDeleteModal('Luna');`,
);

function render({ confirmation = '', deleting = false, error = null } = {}) {
  return renderToStaticMarkup(renderModal(
    React, { isPatientDeleting: deleting, errorMessage: error }, () => {}, () => {},
    confirmation, () => {}, () => null,
  ));
}

test('patient deletion warning includes appointments and clinical records', () => {
  const html = render();
  assert.match(html, /role="dialog"/);
  assert.match(html, /Luna/);
  assert.match(html, /incluyendo citas, consultas, exámenes, vacunas\/desparasitación y referencias de\s+archivos/);
  assert.match(html, /Esta acción no se puede deshacer/);
});

test('modal requires explicit confirmation, disables deletion while pending and shows errors', () => {
  assert.match(render(), /<button[^>]*disabled=""[^>]*>Confirmar eliminación<\/button>/);
  assert.doesNotMatch(render({ confirmation: 'ELIMINAR' }), /disabled=""/);
  assert.match(render({ confirmation: 'ELIMINAR', deleting: true }), /<button[^>]*disabled=""[^>]*>Eliminando\.\.\.<\/button>/);
  assert.match(render({ error: 'No se pudo eliminar' }), /class="error-state">No se pudo eliminar/);
});
