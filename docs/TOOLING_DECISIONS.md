# Tooling decisions for the authorized preview

The supplied `repos.md` is a discovery list, not an approval or installation manifest. No listed skill, agent framework or plugin was executed, and no new dependency was added merely to increase agent count. Repository code, licenses and model assets need independent review before integration.

| Candidate | Concrete use | Decision / boundary |
| --- | --- | --- |
| [Microsoft Playwright](https://github.com/microsoft/playwright) | Real-browser explicit-input UI regressions, protocol mismatch and failure-state checks | Useful next test layer. DOM/IPC mocks are not compiled Tauri or real-model E2E. This workspace's attempted browser smoke could not load Playwright; no browser pass is claimed. Existing Node UI contracts remain separate evidence. |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | Supplementary staged/history secret scanning before publication | Do not treat as complete DLP or credential revocation. Its README as reviewed on 2026-10-28 describes maintenance/security-only status and a maintainer successor; evaluate maintenance, pinning and workflow trust before adding. Existing connected secret scanning is not replaced. |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | Candidate hardware-specific local inference benchmark | Defer until target OS/RAM/GPU/model are specified. It is not a drop-in implementation of the current Ollama endpoints. A future adapter must preserve preflight, identity/error contracts, bounded output and cancellation limitations. MIT code does not license every model asset. |

Mass multi-agent simulation is not independent customer validation. The highest-value work here is evidence quality: meaningful negative cases, strict corpus accounting, fail-closed model report checks, real-device qualification and consent-based task pilots. Measure task completion, incorrect suggestions, recovery, repeat use and willingness to pay before expanding features. No tool choice establishes demand, a valuation or a “100×” improvement.
