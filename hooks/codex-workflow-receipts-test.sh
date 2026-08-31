#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOK="$SCRIPT_DIR/codex-workflow-receipts.py"
TEST_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

legacy='WORKFLOW_APPROVAL {"work_item":"PILOT-1","decision":"specification_approved","revision":"REV-SPEC","role":"ticket_owner"}'
jq -cn --arg prompt "$legacy" '{hook_event_name:"UserPromptSubmit",session_id:"session-human",turn_id:"turn-human",cwd:"/workspace",prompt:$prompt}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

proposal="$TEST_ROOT/proposal.json"
printf '%s' '{"work_item":"PILOT-1","id":"E-APPROVAL"}' > "$proposal"
prepare_command="python3 $REPO_ROOT/skills/agentic-development-workflow/scripts/adw.py prepare-approval PILOT-1 --delivery-root $TEST_ROOT/delivery --role ticket_owner --expected-sequence 1 --expected-head sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
preflight_blocked="$(
  jq -cn --arg command "$prepare_command" '{hook_event_name:"PreToolUse",session_id:"session-lead",turn_id:"turn-prepare",cwd:"/workspace",tool_name:"Bash",tool_use_id:"tool-prepare",tool_input:{command:$command}}' |
    PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK"
)"
test "$(printf '%s' "$preflight_blocked" | jq -r '.hookSpecificOutput.permissionDecision')" = "deny"

command="python3 $REPO_ROOT/skills/agentic-development-workflow/scripts/adw.py record-evidence PILOT-1 --delivery-root $TEST_ROOT/delivery --record-file $proposal --expected-sequence 1 --expected-head sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
jq -cn --arg command "$command" '{hook_event_name:"PreToolUse",session_id:"session-lead",turn_id:"turn-lead",cwd:"/workspace",tool_name:"Bash",tool_use_id:"tool-lead",tool_input:{command:$command}}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

record_approval_command="python3 $REPO_ROOT/skills/agentic-development-workflow/scripts/adw.py record-approval PILOT-1 --delivery-root $TEST_ROOT/delivery --role ticket_owner --expected-sequence 1 --expected-head sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
jq -cn --arg command "$record_approval_command" '{hook_event_name:"PreToolUse",session_id:"session-lead",turn_id:"turn-record-approval",cwd:"/workspace",tool_name:"Bash",tool_use_id:"tool-record-approval",tool_input:{command:$command}}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

lead_decision_command="python3 $REPO_ROOT/skills/agentic-development-workflow/scripts/adw.py record-lead-decision PILOT-1 --delivery-root $TEST_ROOT/delivery --id E-TEST-DESIGN-PASS --gate test_design_pass --expected-sequence 1 --expected-head sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
jq -cn --arg command "$lead_decision_command" '{hook_event_name:"PreToolUse",session_id:"session-lead",turn_id:"turn-decision",cwd:"/workspace",tool_name:"Bash",tool_use_id:"tool-decision",tool_input:{command:$command}}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

jq -cn --arg command "echo $command" '{hook_event_name:"PreToolUse",session_id:"session-lead",turn_id:"turn-fake",cwd:"/workspace",tool_name:"Bash",tool_use_id:"tool-fake",tool_input:{command:$command}}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

judge='WORKFLOW_JUDGE_RESULT {"work_item":"PILOT-1","decision":"continue_to_local_qa","state":"CODE_QUALITY_GATE","result_status":"pass","supports":["E-TDD"],"input_revisions":{"specification":"REV-SPEC","test_design":"REV-TEST","change":"REV-CHANGE","configuration":"REV-CONFIG"},"findings":[]}'
jq -cn --arg message "$judge" '{hook_event_name:"SubagentStop",session_id:"session-lead",turn_id:"turn-judge",cwd:"/workspace",agent_id:"judge-1",agent_type:"development-workflow-judge",last_assistant_message:$message}' |
  PYTHONDONTWRITEBYTECODE=1 AGENTIC_WORKFLOW_RECEIPT_ROOT="$TEST_ROOT/receipts" PLUGIN_ROOT="$REPO_ROOT" python3 "$HOOK" >/dev/null

test "$(find "$TEST_ROOT/receipts/records" -name 'human_approval-*.json' | wc -l | tr -d ' ')" = "0"
test "$(find "$TEST_ROOT/receipts/records" -name 'lead_call-*.json' | wc -l | tr -d ' ')" = "4"
test "$(find "$TEST_ROOT/receipts/records" -name 'judge_output-*.json' | wc -l | tr -d ' ')" = "1"
test "$(jq -r '.claim.subcommand' "$TEST_ROOT"/receipts/records/lead_call-*.json | grep -c '^record-lead-decision$')" = "1"
test "$(jq -r '.claim.subcommand' "$TEST_ROOT"/receipts/records/lead_call-*.json | grep -c '^record-approval$')" = "1"

jq -e '
  (.hooks.UserPromptSubmit | length == 1) and
  (.hooks.SubagentStop | length == 1) and
  ([.hooks.PreToolUse[].hooks[].command | contains("codex-workflow-receipts.py")] | any)
' "$SCRIPT_DIR/codex-hooks.json" >/dev/null

printf '%s\n' '{"status":"pass","receipts":6}'
