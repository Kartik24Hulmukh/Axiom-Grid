# UX/redteam journey matrix — 120 distinct scenarios

Baseline `4f3a822`; frontend-only scoped review. Each row has a distinct action, state boundary, failure, or accessibility requirement. These are scenario designs, not recruited humans, not script personas, and not an assertion all combinations were tested. Evidence statuses are assigned in the scoped review; absent an explicit test reference a row is **planned/unverified**.

**Coverage labels:** 54 rows have cited direct or explicitly limited/partial observations; 66 are planned/unverified. A row reference is not a whole-journey pass: pre-edit results, constrained subcases and fabricated oracles are labelled. The 19 focused tests are not 120 executions.
| ID | Area | Journey / trigger | Expected outcome | Evidence status |
| --- | --- | --- | --- | --- |
| UX-001 | Connection | Enter correct deployment key | Successful verification; password input cleared | Real backend — connect helper in UX01–UX19 |
| UX-002 | Connection | Enter incorrect deployment key | Readable rejection; old owned content removed | Planned/unverified |
| UX-003 | Connection | Submit blank key to auth-required server | 401 rejection; never implies authenticated | Planned/unverified |
| UX-004 | Connection | Forget idle authenticated key | Owned document, review draft and statuses cleared | Real backend/session clear — UX01, UX02, UX12 |
| UX-005 | Connection | Forget while auth response delayed | Late response cannot reassert connection | Planned/unverified |
| UX-006 | Connection | Reconnect with a different scoped key | Prior tenant content cannot remain visible | Planned/unverified |
| UX-007 | Connection | Reload authenticated page | No key restored from browser storage | Planned/unverified |
| UX-008 | Connection | Inspect localStorage and sessionStorage after connect | Neither receives deployment key | Planned/unverified |
| UX-009 | Connection | Connect outside loopback without HTTPS | Key never sent over insecure transport | Planned/unverified |
| UX-010 | Connection | Press Enter twice in connection form | Only one verification request while busy | Planned/unverified |
| UX-011 | Processing | Doubleclick Process Document | One request and one current result | Real backend — baseline rapid-click test (pre-edit) |
| UX-012 | Processing | Hundred synchronous process clicks | Exactly one request; controls recover | Real backend — baseline 100-click test (pre-edit) |
| UX-013 | Processing | Forget during delayed successful processing | Cleared document cannot become stale error or content | Real backend, delayed transport — UX01 |
| UX-014 | Processing | Forget during delayed failed processing | Forgotten state not overwritten by old failure | Planned/unverified |
| UX-015 | Processing | Reconnect then process before old response settles | New operation owns controls and results | Real backend, delayed transport — UX10 (same key; not two tenants) |
| UX-016 | Processing | Change fixture while processing | Selection locked until result; heading not ambiguous | Real browser control lock — UX09 (upload-inflight lock; processing lock code-reviewed only) |
| UX-017 | Processing | Upload while processing fixture | Upload cannot replace selected document midflight | Planned/unverified |
| UX-018 | Processing | Process nonexistent fixture from query string | 404 explained; controls recover; no suggestions | Real backend — baseline missing-document test (pre-edit) |
| UX-019 | Processing | Process arbitrary filesystem path | Denied; no host file text displayed | Real backend — baseline denied-host-path test (pre-edit) |
| UX-020 | Processing | Process same document twice | Prior cards cleared; current trace and cards replace them | Planned/unverified |
| UX-021 | Uploads | Click Upload with no selected file | Actionable local selection error; no request | Browser guard/no request — UX16 |
| UX-022 | Uploads | Choose zero-byte text file | Backend verdict explained; no invented extraction | Planned/unverified |
| UX-023 | Uploads | Choose file exactly at 2 MiB | Boundary governed by backend; UI does not off-by-one reject | Planned/unverified |
| UX-024 | Uploads | Choose file greater than 2 MiB | Local size rejection without request | Browser guard/no request — UX16 |
| UX-025 | Uploads | Doubleclick owned upload | One binary request; one owned option | Real backend, delayed transport — UX09 |
| UX-026 | Uploads | Forget during delayed successful upload | No stale owned locator/status restored | Real backend, delayed transport — UX02 |
| UX-027 | Uploads | Forget during delayed failed upload | No stale failure attached to new session | Planned/unverified |
| UX-028 | Uploads | Choose filename containing markup | Filename renders as text in option | Real backend — UX16 |
| UX-029 | Uploads | Choose filename with Unicode and spaces | URL encoding preserves intended filename | Real backend — UX16 |
| UX-030 | Uploads | Upload same filename twice | Opaque references stay distinct; correct latest selection | Planned/unverified |
| UX-031 | Abandonment | Close page during pipeline request | Next fresh session still usable | Real backend — baseline abandonment test (pre-edit) |
| UX-032 | Abandonment | Close page during owned upload | No client success claim; orphan cleanup is server responsibility | Planned/unverified |
| UX-033 | Abandonment | Navigate away during correction | No proof of save merely from navigation | Planned/unverified |
| UX-034 | Abandonment | Escape editor before saving | Draft discarded and focus returns to Edit | Real browser — UX05 |
| UX-035 | Abandonment | Escape editor during delayed save | Pending save may complete; not falsely called cancelled | Real backend, delayed transport — UX07, UX12 (no cancellation assertion) |
| UX-036 | Abandonment | Open another editor before prior save returns | New draft stays open and unchanged | Real backend, delayed transport — UX07 |
| UX-037 | Abandonment | Forget while correction is pending | Modal draft wiped; late result cannot repopulate it | Real backend, delayed transport — UX12 (Escape before Forget) |
| UX-038 | Abandonment | Forget after upload before processing | Owned option removed; server copy is not claimed deleted | Planned/unverified |
| UX-039 | Abandonment | Browser back after page reload | Deployment-key restoration must not be promised | Planned/unverified |
| UX-040 | Abandonment | Lose connection after upload body sent | Outcome ambiguity shown; automatic duplicate upload avoided | Planned/unverified |
| UX-041 | Reviews | Save first correction | Revision and card value update; source confidence not reused as review confidence | Real backend — UX07, baseline review test (pre-edit) |
| UX-042 | Reviews | Save second correction on same field | CAS uses latest revision; repeat edit remains available | Real backend — baseline repeated-review test (pre-edit) |
| UX-043 | Reviews | Doubleclick Save Correction | One correction request while field busy | Planned/unverified |
| UX-044 | Reviews | Reject suggestion twice rapidly | One rejection request; no duplicate revision increment | Planned/unverified |
| UX-045 | Reviews | Accept unsupported native desktop write | Fails closed; no fake applied success | Real backend — baseline native-writer refusal test (pre-edit) |
| UX-046 | Reviews | Edit value containing HTML | Literal text only; no DOM injection | Real backend — baseline literal-markup correction test (pre-edit) |
| UX-047 | Reviews | Submit empty corrected value | Backend decides; UI must not invent nonempty value | Planned/unverified |
| UX-048 | Reviews | Correct multibyte long value beyond review quota | Backend quota failure visible; draft retained | Planned/unverified |
| UX-049 | Reviews | Press Save while another field save pending | No accidental save of stale active field | Real backend, delayed transport — UX07 (new editor draft isolation) |
| UX-050 | Reviews | Source lookup after correction | Original observation unchanged; human review not re-grounding | Planned/unverified |
| UX-051 | Conflicts | Second reviewer wins before first save | 409 visible; current revision loaded; explicit retry only | Real backend — UX06 |
| UX-052 | Conflicts | Conflict reload updates displayed Original Value | Original input matches current stored value | Real backend — UX06 |
| UX-053 | Conflicts | Conflict reload retains corrected draft | User draft not silently replaced by another review | Real backend — UX06 |
| UX-054 | Conflicts | Retry after conflict with latest revision | Explicit retry succeeds if no newer review intervenes | Real backend — baseline conflict/retry test (pre-edit) |
| UX-055 | Conflicts | A second conflict before explicit retry | Reload again; no automatic overwrite loop | Planned/unverified |
| UX-056 | Conflicts | Conflict reload returns 404 expiry | Clear reload failure; no speculative revision increment | Planned/unverified |
| UX-057 | Conflicts | Conflict reload transport fails | Draft retained and actionable error shown | Planned/unverified |
| UX-058 | Conflicts | Cancel after conflict then reopen | Old error cleared; current value is baseline | Real backend — UX06 |
| UX-059 | Conflicts | Conflict arrives after editor closed | No error inserted into a different open editor | Planned/unverified |
| UX-060 | Conflicts | Reject conflicts with remote review | Failure visible; Edit permits an explicit reload/retry journey | Planned/unverified |
| UX-061 | Sources | Open first suggestion source | Actual retained source JSON; no invented PDF overlay | Real backend — UX11, baseline source test (pre-edit) |
| UX-062 | Sources | Rapid source-chip clicks | One lookup per chip while busy | Planned/unverified |
| UX-063 | Sources | Source lookup returns 404 expiry | Unavailable state explained; chip re-enabled | Real unknown-ID backend response — UX15 (not actual expiry) |
| UX-064 | Sources | Forget during delayed source lookup | Detached source result cannot restore owned content | Real backend, delayed transport — UX11 |
| UX-065 | Sources | Source JSON includes markup | Text nodes only; no rendered injection | Planned/unverified |
| UX-066 | Sources | Source JSON has very long unbroken string | Evidence scrolls within card; page stays bounded | Planned/unverified |
| UX-067 | Sources | Reviewed value differs from source | Source still reports original observation | Planned/unverified |
| UX-068 | Sources | Source request forbidden under another key | No fallback to global/legacy evidence | Planned/unverified |
| UX-069 | Sources | Source evidence has zero coordinate values | Coordinates shown honestly; no fictional highlight | Planned/unverified |
| UX-070 | Sources | Trace includes internal refusal reason | Visible factual reason; no success implication | Planned/unverified |
| UX-071 | Empty/refused | Document has no grounded fields | Explicit no-grounded-suggestions message | Real backend — UX13 (short low-information note, not all documents) |
| UX-072 | Empty/refused | Document text is empty | Explicit empty-text notice; no silent blank page | Isolated rendering oracle — UX14 |
| UX-073 | Empty/refused | Trace stages are empty | Explicit no-stages notice | Isolated rendering oracle — UX14 |
| UX-074 | Empty/refused | Trace halted with no suggestions | Halt reason visible; no acceptance buttons | Isolated rendering oracle — UX14 (not an actual BLOCK verdict) |
| UX-075 | Empty/refused | BLOCK extraction omitted by actual backend | No actionable fact fabricated for blocked field | Planned/unverified |
| UX-076 | Empty/refused | All suggestions refused but text exists | Text remains inspectable; no fake field values | Planned/unverified |
| UX-077 | Empty/refused | Some fields grounded and others refused | Only grounded suggestions actionable; trace available | Planned/unverified |
| UX-078 | Empty/refused | Pipeline returns success false | Error state; no stale previous cards | Planned/unverified |
| UX-079 | Empty/refused | Malformed response JSON | Readable failure; controls recover | Planned/unverified |
| UX-080 | Empty/refused | Backend returns HTML proxy error | HTTP-aware error instead of raw JSON parse confusion | Isolated proxy-error rendering oracle — UX17 |
| UX-081 | Keyboard | Tab through connection controls | Logical order; visible focus outlines | Planned/unverified |
| UX-082 | Keyboard | Reach fixture selector without pointer | Accessible document label identifies purpose | Planned/unverified |
| UX-083 | Keyboard | Activate Suggestions tab with keyboard | Native button activation and selected state | Real browser — UX04 |
| UX-084 | Keyboard | ArrowRight from Suggestions tab | Trace selected and focus moved | Real browser — UX04 |
| UX-085 | Keyboard | ArrowLeft from Trace tab | Suggestions selected and focus moved | Planned/unverified |
| UX-086 | Keyboard | Home/End in tablist | First/last tab selected with focus | Planned/unverified |
| UX-087 | Keyboard | Hidden editor receives Tab traversal | Hidden controls absent from focus order | Real browser — UX03 |
| UX-088 | Keyboard | Tab from final modal control | Focus wraps to first modal control | Real browser — UX05 |
| UX-089 | Keyboard | ShiftTab from first modal control | Focus wraps to final modal control | Planned/unverified |
| UX-090 | Keyboard | Escape open modal | Closes dialog and returns focus to triggering Edit | Real browser — UX05 |
| UX-091 | Accessibility | Correction dialog has accessible name | Role dialog with labelled title and modal state | Real browser and axe-core — UX05, UX19 |
| UX-092 | Accessibility | Corrected Value label activation | Focuses correct input via explicit association | Planned/unverified |
| UX-093 | Accessibility | Reason label activation | Focuses textarea via explicit association | Planned/unverified |
| UX-094 | Accessibility | Modal open while background focus attempted | Background inert; cannot activate Process behind dialog | Planned/unverified |
| UX-095 | Accessibility | Async correction error notification | Live error announced without destroying draft | Real browser live error + conflict — UX06 (announcement perception untested) |
| UX-096 | Accessibility | Document processing result notification | Polite status update available to assistive tech | Planned/unverified |
| UX-097 | Accessibility | Tab selected semantics inspected | One selected tab; panels linked to controlling tabs | Real browser tab semantics — UX04 |
| UX-098 | Accessibility | Inactive trace panel inspected | Not visible/focusable while Suggestions selected | Real browser tab switching — UX04 |
| UX-099 | Accessibility | Reduced motion preference enabled | Nonessential transitions suppressed | Planned/unverified |
| UX-100 | Accessibility | Visible focus on source/action buttons | Outline remains discernible on dark background | Planned/unverified |
| UX-101 | Mobile | 320px viewport before processing | Upload and Process controls fully reachable | Real browser — baseline mobile-layout test (pre-edit), UX19 (current 320px) |
| UX-102 | Mobile | 768px viewport before processing | No document horizontal overflow | Real browser — baseline mobile-layout test (pre-edit) |
| UX-103 | Mobile | 1280px desktop viewport | Both panels reachable; controls not clipped | Real browser — baseline mobile-layout test (pre-edit) |
| UX-104 | Mobile | 320x480 correction dialog | Dialog bounded to viewport; inner content scrolls | Real browser — UX08 (bounded geometry, scroll-to-Save reachability) |
| UX-105 | Mobile | Small viewport with long correction error | Save/Cancel reachable by scrolling inside dialog | Planned/unverified |
| UX-106 | Mobile | Long unbroken corrected field | Card wraps; no horizontal document overflow | Planned/unverified |
| UX-107 | Mobile | Long source JSON at 320px | Local evidence scroll, not page-wide overflow | Planned/unverified |
| UX-108 | Mobile | Rotate while modal open | Dialog remains centered and usable | Planned/unverified |
| UX-109 | Mobile | 200 percent browser zoom | Content reflows; hidden overflow not mistaken for accessibility | Planned/unverified |
| UX-110 | Mobile | Virtual keyboard shrinks visual viewport | Dialog scroll provides access; actual device trial still required | Planned/unverified |
| UX-111 | Recovery/trust | API request exceeds 30-second timeout | Timeout says outcome may be unknown; controls recover | Clock/transport timeout oracle — UX18 |
| UX-112 | Recovery/trust | Offline request fails before response | Network failure explained; no fake success | Planned/unverified |
| UX-113 | Recovery/trust | Backend overloaded 503 during processing | Failure visible; no automatic retry storm | Planned/unverified |
| UX-114 | Recovery/trust | Rate limited 429 during correction | Draft retained; no automatic repeated save | Planned/unverified |
| UX-115 | Recovery/trust | HTTP 401 after key expires | Authentication failure exposed; no silently reused content | Planned/unverified |
| UX-116 | Recovery/trust | Forget clears upload status wording | No stale successful-upload assurance | Real browser/session reset — UX02 |
| UX-117 | Recovery/trust | Initial health response after Forget | Health-only badge cannot imply deployment authentication | Planned/unverified |
| UX-118 | Recovery/trust | Uploaded access expires after one hour | No assertion local file instantly deleted or encrypted | Planned/unverified |
| UX-119 | Recovery/trust | Human correction recorded | Explicitly not re-grounded; not execution proof | Real backend review — UX07, baseline review test (pre-edit) |
| UX-120 | Recovery/trust | Reload after uncertain save outcome | Inspect current review before duplicate save; key is not restored | Planned/unverified |
