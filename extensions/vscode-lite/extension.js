'use strict';
const vscode = require('vscode');
const client = require('./client');
const {PreviewSession, sameSnapshot, makePrompt, stripFence} = require('./state');
const {planComment, renderComment} = require('./comment');
const SECRET_KEY = 'axiomLite.runtimeToken';
function activate(context) {
  const session = new PreviewSession(client);
  let trackedEditor = null;
  let pairingBusy = false;
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 50);
  status.command = 'axiomLite.complete'; status.text = '$(sparkle) Axiom';
  status.tooltip = 'Axiom: explicitly request a local code suggestion. Suggestions are untested; review and verify before use. No automatic inference.'; status.show();
  function invalidate() {
    const owned = session.pending || session.candidate !== null;
    session.invalidate();
    if (owned) {
      status.text = '$(sparkle) Axiom: discarded';
      Promise.resolve(vscode.commands.executeCommand('editor.action.inlineSuggest.hide')).catch(() => {});
    }
  }
  function allowed(editor) {
    return vscode.workspace.isTrusted && !vscode.env.remoteName && vscode.env.uiKind !== vscode.UIKind.Web && editor
      && editor.document.uri.scheme === 'file' && editor.selections.length === 1 && editor.selection.isEmpty
      && !editor.document.isClosed;
  }
  function snapshot(editor) {
    return {uri: editor.document.uri.toString(), version: editor.document.version,
      line: editor.selection.active.line, character: editor.selection.active.character};
  }
  function current(editor, expected) {
    return allowed(editor) && vscode.window.activeTextEditor === editor && sameSnapshot(snapshot(editor), expected);
  }
  const provider = vscode.languages.registerInlineCompletionItemProvider({scheme: 'file'}, {
    provideInlineCompletionItems(document, position) {
      const editor = vscode.window.activeTextEditor;
      if (!allowed(editor) || editor.document !== document || !position.isEqual(editor.selection.active)) return [];
      const expected = snapshot(editor);
      const text = session.peek(expected);
      if (!text || editor !== trackedEditor) return [];
      return [new vscode.InlineCompletionItem(text, new vscode.Range(position, position))];
    }
  });
  const complete = vscode.commands.registerCommand('axiomLite.complete', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!allowed(editor)) { vscode.window.showWarningMessage('Axiom requires a trusted local file, an empty selection and a local VS Code window. Remote and virtual workspaces are not supported.'); return; }
    if (pairingBusy) { vscode.window.showInformationMessage('Axiom pairing is being updated. Wait before requesting a suggestion.'); return; }
    if (session.pending) { vscode.window.showInformationMessage('Axiom is still settling the previous request. Discarding does not prove backend inference stopped.'); return; }
    const expected = snapshot(editor);
    const offset = editor.document.offsetAt(editor.selection.active);
    const lineEnd = editor.document.offsetAt(editor.document.lineAt(editor.selection.active.line).range.end);
    const lineStart = offset - editor.selection.active.character;
    // Inspect a bounded initial slice, not an unbounded line/document.
    const lineHead = editor.document.getText(new vscode.Range(editor.document.positionAt(lineStart),
      editor.document.positionAt(Math.min(lineEnd, lineStart + 1025))));
    let comment;
    try {
      if (lineEnd - lineStart > 1024 && /^[ \t]*\/?$/.test(lineHead)) throw Error('COMMENT_TOO_LARGE');
      comment = planComment(lineHead, editor.selection.active.character, editor.document.languageId);
    }
    catch {
      vscode.window.showInformationMessage('For comment prompts, use // followed by a nonblank instruction in a JavaScript/TypeScript file. Keep the entire line within 1,024 characters and put the cursor at its end. Legacy slash modes are not supported.');
      return;
    }
    const eol = editor.document.eol === 2 ? '\r\n' : '\n';
    const end = editor.document.offsetAt(editor.document.lineAt(editor.document.lineCount - 1).range.end);
    // Only bounded text around the cursor; never read or index the workspace.
    const edgeSafe = text => text.replace(/^[\uDC00-\uDFFF]|[\uD800-\uDBFF]$/g, '');
    const prefix = edgeSafe(editor.document.getText(new vscode.Range(editor.document.positionAt(Math.max(0, offset - 6000)), editor.selection.active)));
    const suffix = edgeSafe(editor.document.getText(new vscode.Range(editor.selection.active, editor.document.positionAt(Math.min(end, offset + 2000)))));
    if (!`${prefix}${suffix}`.trim()) { vscode.window.showInformationMessage('Type some code before requesting a continuation.'); return; }
    try {
      trackedEditor = editor;
      // Reserve admission before SecretStorage can suspend; capture failures without
      // an unhandled rejection while the progress UI is being created.
      const work = session.run(expected, () => context.secrets.get(SECRET_KEY),
        makePrompt(comment ? prefix.slice(0, -lineHead.length) : prefix, suffix, editor.document.languageId, comment?.instruction, comment ? lineHead : undefined),
        () => current(editor, expected), text => comment ? renderComment(stripFence(text), comment.indentation, eol) : stripFence(text))
        .then(value => ({value}), error => ({error}));
      status.text = '$(sync~spin) Axiom: generating';
      await vscode.window.withProgress({location: vscode.ProgressLocation.Notification, title: 'Axiom: local suggestion (cancel discards locally)', cancellable: true}, async (_progress, cancellation) => {
        const subscription = cancellation.onCancellationRequested(invalidate);
        if (cancellation.isCancellationRequested) invalidate();
        try {
          const outcome = await work;
          if (outcome.error) throw outcome.error;
          const text = outcome.value;
          if (text !== null && current(editor, expected)) {
            status.text = '$(sparkle) Axiom: preview (untested)';
            await vscode.commands.executeCommand('editor.action.inlineSuggest.trigger');
          }
        } finally { subscription.dispose(); }
      });
    } catch (error) {
      status.text = '$(warning) Axiom: recheck required';
      const known = error instanceof client.ClientError ? error.code : 'CLIENT_FAILURE';
      if (known === 'INVALID_TOKEN') { vscode.window.showWarningMessage('Use Axiom: Set Runtime Token with the local runtime pairing token, not a GitHub or model-service key.'); return; }
      const guidance = {
        HTTP_UNAUTHORIZED: 'The runtime returned 401. Verify the stored runtime pairing token.',
        HTTP_BUSY: 'The runtime returned 429. It may still be processing a request; wait before retrying.',
        HTTP_BACKEND_ERROR: 'The runtime returned 502. The local model request may have failed or timed out; inspect local runtime logs.',
        HTTP_UNAVAILABLE: 'The runtime returned 503. Check the local model service and approved model identity.',
        NOT_READY: 'The runtime reports the configured model is not ready. Check the local model service and approved model identity.',
        TIMEOUT: 'The client deadline expired. Check the runtime and local model; inference may still be running.'
      };
      const detail = Object.prototype.hasOwnProperty.call(guidance, known) ? guidance[known] : 'Verify the local runtime, pairing and approved model; then request again.';
      vscode.window.showWarningMessage(`Axiom ${known}: no suggestion was inserted. ${detail}`);
    }
  });
  const setToken = vscode.commands.registerCommand('axiomLite.setToken', async () => {
    if (!vscode.workspace.isTrusted || vscode.env.remoteName || vscode.env.uiKind === vscode.UIKind.Web) { vscode.window.showWarningMessage('Configure pairing in a trusted local VS Code window.'); return; }
    if (pairingBusy) { vscode.window.showInformationMessage('Axiom pairing is already being updated.'); return; }
    const token = await vscode.window.showInputBox({title: 'Axiom runtime pairing', prompt: 'Enter the existing runtime\u2019s 64-hex pairing token. Do not enter a GitHub PAT.', password: true, ignoreFocusOut: true,
      validateInput: value => client.validateToken(value) ? undefined : 'Require exactly 64 hexadecimal characters, without spaces.'});
    if (token === undefined) return;
    if (!client.validateToken(token)) { vscode.window.showWarningMessage('Invalid Axiom runtime token.'); return; }
    if (pairingBusy) { vscode.window.showInformationMessage('Axiom pairing is already being updated.'); return; }
    pairingBusy = true;
    invalidate();
    try { await context.secrets.store(SECRET_KEY, token); vscode.window.showInformationMessage('Axiom runtime token stored in VS Code SecretStorage.'); }
    catch { vscode.window.showWarningMessage('Axiom could not store the runtime token.'); }
    finally { pairingBusy = false; }
  });
  const clearToken = vscode.commands.registerCommand('axiomLite.clearToken', async () => {
    if (pairingBusy) { vscode.window.showInformationMessage('Axiom pairing is already being updated.'); return; }
    pairingBusy = true;
    invalidate();
    try { await context.secrets.delete(SECRET_KEY); vscode.window.showInformationMessage('Axiom runtime token removed from this extension\u2019s SecretStorage. This does not revoke the runtime credential.'); }
    catch { vscode.window.showWarningMessage('Axiom could not remove the stored token.'); }
    finally { pairingBusy = false; }
  });
  context.subscriptions.push(status, provider, complete, setToken, clearToken,
    vscode.commands.registerCommand('axiomLite.discard', invalidate),
    vscode.workspace.onDidChangeTextDocument(event => { if (trackedEditor && event.document === trackedEditor.document) invalidate(); }),
    vscode.window.onDidChangeTextEditorSelection(event => { if (event.textEditor === trackedEditor) invalidate(); }),
    vscode.window.onDidChangeActiveTextEditor(invalidate),
    context.secrets.onDidChange(event => { if (event.key === SECRET_KEY) invalidate(); }),
    {dispose: () => session.invalidate()});
}
function deactivate() {}
module.exports = {activate, deactivate};
