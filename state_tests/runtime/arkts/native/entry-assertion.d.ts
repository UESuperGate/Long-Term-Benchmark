export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Role = 'base' | 'final' | 'agent';
export interface CaseSpec {
  taskId: string; caseId: string; traceDigest: string;
  given: { [field: string]: Json }; event: { name: string }; invariants: string[];
}
export interface GivenBinding {
  kind: 'rendered_surface' | 'anchor_attributes'; value: Json;
  attributes?: { [attribute: string]: Json };
}
export interface EntryPolicy {
  id: string; approval: 'pending' | 'approved'; selectorCoverage: 'pending_review' | 'reviewed_complete';
  taskId: string; caseId: string; traceDigest: string; eventName: string;
  sourceSha256: string; route: string; anchorId: string; anchorType: string;
  entryIds: string[]; givenBindings: { [field: string]: GivenBinding };
}
export interface ExecutionBinding {
  taskId: string; role: Role; sourceSha256: string; policySha256: string;
}
export interface Selector { kind: 'arkui_id'; value: string; }
export interface NodeObservation {
  type: string; nativeId: number; bounds: string; visible: boolean;
  enabled?: boolean; text?: string; label?: string; focused?: boolean; placeholder?: string;
}
export interface ControlObservation {
  selector: Selector; present: boolean | null; node: NodeObservation | null;
}
export interface Frame {
  capturedAt: number; available: boolean; candidateRouteVerified: boolean;
  route: { path: string; name: string; index: number };
  viewport: { width: number; height: number }; anchor: ControlObservation; target: ControlObservation;
}
export interface ProofReference { observationId: string; pointer: string; }
export interface PrerequisiteCheck {
  id: string; expected: true; observed: boolean | null; passed: boolean | null; evidence: ProofReference[];
}
export interface EntryProbe {
  schemaVersion: 1; kind: 'native_ui_entry_probe'; backend: 'native_previewer_arkui';
  caseId: string; instanceId: string; observationId: string; candidateRoute: string;
  before: Frame; after: Frame;
  action: { api: 'sendEventByKey'; selector: Selector; action: 10; params: object;
    attempted: boolean; attemptedAt?: number; delivered: boolean | null; error?: string };
  prerequisiteChecks: PrerequisiteCheck[];
}
export interface GivenCheck {
  field: string; expected: Json; established: boolean; observed: Json;
  evidence: ProofReference[]; reason: string;
}
export interface EntryAssertion {
  schemaVersion: 1; kind: 'runtime_entry_assertion'; failPhase: 'entry';
  taskId: string; role: Role; caseId: string; traceDigest: string;
  policyId: string; policySha256: string; sourceSha256: string;
  probes: EntryProbe[]; givenChecks: GivenCheck[]; prerequisiteChecks: PrerequisiteCheck[];
  postState: null; transitionExecuted: false;
  invariants: { evaluated: false; unobserved: string[] };
}
export interface EntryAssessment {
  status: 'fail' | 'not_scored'; failPhase: 'entry' | null; errors: string[]; reason: string;
}
export function assessEntryAssertion(assertion: EntryAssertion, spec: CaseSpec, policy: EntryPolicy,
  binding: ExecutionBinding, usedObservationIds?: string[]): EntryAssessment;
export function createEntryAssertion(spec: CaseSpec, policy: EntryPolicy, binding: ExecutionBinding,
  probes: EntryProbe[]): { assertion: EntryAssertion; assessment: EntryAssessment };
